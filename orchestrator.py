"""Run an Agent Framework team directly from YAML definitions."""

import argparse
import asyncio
import importlib.util
import logging
import os
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml
from agent_framework import (
    Agent,
    ChatContext,
    ChatMiddleware,
    MCPStreamableHTTPTool,
    Message,
)
from agent_framework.foundry import FoundryChatClient
from agent_framework.orchestrations import (
    ConcurrentBuilder,
    GroupChatBuilder,
    GroupChatState,
    HandoffBuilder,
    SequentialBuilder,
)
from azure.identity import AzureCliCredential
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_UNSAFE_HANDOFF_CONTENT_TYPES = {
    "function_call",
    "function_result",
    "text_reasoning",
}


class ReasoningSafeHandoffMiddleware(ChatMiddleware):
    """Remove reasoning-model tool items from cross-agent history."""

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name

    async def process(
        self,
        context: ChatContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        cleaned: list[Message] = []
        for message in context.messages:
            author = getattr(message, "author_name", None)
            if not author or author == self.agent_name:
                cleaned.append(message)
                continue

            contents = getattr(message, "contents", None) or []
            kept = [
                content
                for content in contents
                if getattr(content, "type", None) not in _UNSAFE_HANDOFF_CONTENT_TYPES
            ]
            if len(kept) == len(contents):
                cleaned.append(message)
            elif kept:
                cleaned.append(
                    Message(
                        role=message.role,
                        contents=kept,
                        author_name=author,
                        message_id=getattr(message, "message_id", None),
                        additional_properties=getattr(message, "additional_properties", None),
                        raw_representation=getattr(message, "raw_representation", None),
                    )
                )

        context.messages = cleaned  # type: ignore[assignment]
        await call_next()


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as yaml_file:
        document = yaml.safe_load(yaml_file)
    if not isinstance(document, dict):
        raise ValueError(f"YAML file must contain an object: {path}")
    return document


def _resolve_path(base: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _load_tools_module(path: Path) -> ModuleType:
    if not path.is_file():
        raise FileNotFoundError(f"Tools module not found: {path}")
    module_name = f"team_tools_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load tools module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_team(team_yaml: str | Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """Load a team document and its Python tool registry."""
    team_path = Path(team_yaml).resolve()
    if not team_path.is_file():
        raise FileNotFoundError(f"Team YAML not found: {team_path}")

    team = _load_yaml(team_path)
    runtime = team.get("runtime", {}) or {}
    if not isinstance(runtime, dict):
        raise ValueError("team.yaml runtime must be an object")

    env_file = _resolve_path(team_path.parent, runtime.get("env_file", ".env"))
    load_dotenv(env_file, override=False)

    tools_file = _resolve_path(team_path.parent, runtime.get("tools_file", "src/tools.py"))
    tools_module = _load_tools_module(tools_file)
    registry = getattr(tools_module, "TOOL_REGISTRY", None)
    if not isinstance(registry, dict):
        raise ValueError(f"{tools_file} must define a TOOL_REGISTRY dictionary")
    return team_path, team, registry


def _create_client(model: str | None):
    credential = AzureCliCredential()
    foundry_endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    default_model = os.getenv("FOUNDRY_MODEL", "gpt-5")
    if foundry_endpoint:
        return FoundryChatClient(
            project_endpoint=foundry_endpoint,
            model=model or default_model,
            credential=credential,
        )

    azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if azure_openai_endpoint:
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            model=model or default_model,
            azure_endpoint=azure_openai_endpoint,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            credential=credential,
            api_key=None,
        )

    raise RuntimeError(
        "No chat endpoint configured. Set FOUNDRY_PROJECT_ENDPOINT in the team's .env file."
    )


async def _build_agent(
    stack: AsyncExitStack,
    agent_definition: dict[str, Any],
    tool_registry: dict[str, Any],
) -> Agent:
    definition = agent_definition.get("definition", {}) or {}
    name = agent_definition.get("name", "agent")
    tools: list[Any] = []

    for tool_definition in definition.get("tools", []) or []:
        tool_type = tool_definition.get("type", "function")
        if tool_type == "function":
            tool_name = tool_definition["name"]
            implementation = tool_registry.get(tool_name)
            if implementation is None:
                raise ValueError(
                    f"Agent '{name}' declares function tool '{tool_name}', but it is not "
                    "registered in TOOL_REGISTRY"
                )
            tools.append(implementation)
        elif tool_type == "mcp":
            mcp_tool = MCPStreamableHTTPTool(
                name=tool_definition.get("server_label", "mcp"),
                url=tool_definition["server_url"],
            )
            try:
                await stack.enter_async_context(mcp_tool)
                tools.append(mcp_tool)
            except Exception as exc:
                logger.warning(
                    "Skipping MCP tool '%s' (%s): %s",
                    tool_definition.get("server_label", "mcp"),
                    tool_definition["server_url"],
                    exc,
                )

    return Agent(
        client=_create_client(definition.get("model")),
        name=name,
        description=(
            agent_definition.get("description")
            or definition.get("description")
            or name
        ),
        instructions=definition.get("instructions", ""),
        tools=tools,
        middleware=[ReasoningSafeHandoffMiddleware(agent_name=name)],
    )


def _wire_workflow(
    team_name: str,
    pattern: str,
    participants: list[Agent],
    by_name: dict[str, Agent],
    orchestration: dict[str, Any],
):
    if pattern == "sequential":
        chain_only = orchestration.get("chain_only_agent_responses", True)
        if not isinstance(chain_only, bool):
            raise ValueError("orchestration.chain_only_agent_responses must be a boolean")
        return SequentialBuilder(
            participants=participants,
            chain_only_agent_responses=chain_only,
        ).build()
    if pattern == "concurrent":
        return ConcurrentBuilder(participants=participants).build()
    if pattern == "group_chat":
        max_rounds = int(orchestration.get("max_rounds", 6))

        def select_next(state: GroupChatState) -> str:
            names = list(state.participants.keys())
            return names[state.current_round % len(names)]

        return GroupChatBuilder(
            participants=participants,
            termination_condition=lambda conversation: len(conversation) >= max_rounds,
            selection_func=select_next,
            intermediate_output_from=participants,
        ).build()
    if pattern == "handoff":
        start = by_name.get(orchestration.get("start_agent")) or participants[0]
        builder = HandoffBuilder(
            name=team_name,
            participants=participants,
        ).with_start_agent(start)
        for source, targets in (orchestration.get("handoffs") or {}).items():
            source_agent = by_name.get(source)
            target_agents = [by_name[target] for target in targets if target in by_name]
            if source_agent is not None and target_agents:
                builder = builder.add_handoff(source_agent, target_agents)
        return builder.build()
    raise ValueError(f"Unknown orchestration pattern: {pattern!r}")


@asynccontextmanager
async def open_team(team_yaml: str | Path):
    """Build a reusable team workflow and keep its tool resources open."""
    team_path, team, tool_registry = load_team(team_yaml)
    orchestration = team.get("orchestration", {}) or {}
    configured_pattern = orchestration.get("pattern")
    if not isinstance(configured_pattern, str) or not configured_pattern.strip():
        raise ValueError("team.yaml must define orchestration.pattern")
    pattern = configured_pattern.strip().lower().replace("-", "_")

    agent_refs = orchestration.get("agents", []) or []
    if not isinstance(agent_refs, list) or not agent_refs:
        raise ValueError("team.yaml must list at least one orchestration agent")

    async with AsyncExitStack() as stack:
        participants: list[Agent] = []
        by_name: dict[str, Agent] = {}
        for agent_ref in agent_refs:
            agent_path = _resolve_path(team_path.parent, agent_ref)
            agent_definition = _load_yaml(agent_path)
            agent = await _build_agent(stack, agent_definition, tool_registry)
            participants.append(agent)
            by_name[agent.name] = agent

        logger.info(
            "Loaded %d agents (%s); pattern=%s",
            len(participants),
            ", ".join(by_name),
            pattern,
        )
        workflow = _wire_workflow(
            team.get("name", team_path.stem),
            pattern,
            participants,
            by_name,
            orchestration,
        )
        yield workflow, orchestration.get("task")


async def _run_workflow(workflow, task: str) -> str:
    events = await workflow.run(task)
    outputs = events.get_outputs()
    if not outputs:
        return ""
    final = outputs[-1]
    messages = getattr(final, "messages", None)
    if messages:
        return "\n".join(
            f"[{message.author_name or 'assistant'}] {message.text}"
            for message in messages
            if (message.text or "").strip()
        )
    return str(final)


async def run_team(team_yaml: str | Path, task: str | None = None) -> str:
    """Build and run a team once."""
    async with open_team(team_yaml) as (workflow, configured_task):
        selected_task = task if task is not None else configured_task
        if not isinstance(selected_task, str) or not selected_task.strip():
            raise ValueError(
                "No task provided. Set orchestration.task in team.yaml or pass --task."
            )
        return await _run_workflow(workflow, selected_task)


async def run_chat(team_yaml: str | Path, initial_task: str | None = None) -> None:
    """Run a persistent terminal chat against one team workflow."""
    async with open_team(team_yaml) as (workflow, configured_task):
        first_task = initial_task if initial_task is not None else configured_task
        if isinstance(first_task, str) and first_task.strip():
            result = await _run_workflow(workflow, first_task)
            print(f"\nTeam> {result}")

        print("\nChat started. Type 'exit' or 'quit' to end the session.")
        while True:
            try:
                user_input = await asyncio.to_thread(input, "\nYou> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            user_input = user_input.strip()
            if user_input.lower() in {"exit", "quit"}:
                break
            if not user_input:
                continue
            result = await _run_workflow(workflow, user_input)
            print(f"\nTeam> {result}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an Agent Framework team directly from team and agent YAML files."
    )
    parser.add_argument("--team-yaml", required=True, type=Path)
    parser.add_argument("--task", help="Override the initial task from team.yaml")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one task and exit instead of opening an interactive chat",
    )
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    if args.once:
        result = asyncio.run(run_team(args.team_yaml, args.task))
        print("\n===== Team Result =====")
        print(result)
    else:
        asyncio.run(run_chat(args.team_yaml, args.task))


if __name__ == "__main__":
    main()