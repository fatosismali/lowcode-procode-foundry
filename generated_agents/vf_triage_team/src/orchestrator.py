"""
Team orchestrator for "vf-triage-team".

Pattern-agnostic runtime loader: this single file reads the team spec and every
agent definition from YAML at run time, builds one Agent per YAML in-process, and
wires them together with the orchestration pattern named in team.yaml.

No per-agent Python files are generated. To add behaviour:
  - implement the tool bodies in tools.py (wired by name via TOOL_REGISTRY)
  - edit the agent YAMLs under ./agents/ or the pattern in ./team.yaml

Vodafone incident response team: triage the fault, then notify customers.
"""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from pathlib import Path
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

from .config import TeamConfig
from .tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)

# Content types that carry cross-agent references (function-call IDs paired with
# reasoning-item IDs) which the Responses API rejects when they arrive without
# their partner. Stripping these from the *inbound* history lets any agent see a
# clean text-only view of what previous agents did.
_UNSAFE_HANDOFF_CONTENT_TYPES: set[str] = {
    "function_call",
    "function_result",
    "text_reasoning",
}


class ReasoningSafeHandoffMiddleware(ChatMiddleware):
    """Strip cross-agent function_call / function_result / text_reasoning items.

    Multi-agent patterns (Sequential / Concurrent / GroupChat / Handoff) forward
    the full conversation between participants. Reasoning models on the Azure
    Responses API (gpt-5, o-series) require every ``function_call`` item to be
    paired with its ``reasoning`` item by ID; those pairings do not survive the
    cross-agent hand-off, and the downstream request is rejected with:

        Item 'fc_...' of type 'function_call' was provided without its required
        'reasoning' item: 'rs_...'.

    The middleware is bound to a single agent (via ``agent_name``) and only
    rewrites messages authored by a *different* agent. The current agent's own
    in-turn tool-call / tool-result / reasoning items are preserved, so single
    -agent tool loops work exactly as before.
    """

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name

    async def process(
        self,
        context: ChatContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        cleaned: list[Message] = []
        stripped_items = 0
        dropped_messages = 0
        for msg in context.messages:
            author = getattr(msg, "author_name", None)
            # Preserve any message authored by the user (no author_name) or by
            # this same agent. Only cross-agent messages are candidates for
            # stripping.
            if not author or author == self.agent_name:
                cleaned.append(msg)
                continue

            contents = getattr(msg, "contents", None) or []
            kept = [
                c for c in contents
                if getattr(c, "type", None) not in _UNSAFE_HANDOFF_CONTENT_TYPES
            ]
            if len(kept) == len(contents):
                cleaned.append(msg)
                continue

            stripped_items += len(contents) - len(kept)
            if not kept:
                dropped_messages += 1
                continue
            cleaned.append(
                Message(
                    role=msg.role,
                    contents=kept,
                    author_name=author,
                    message_id=getattr(msg, "message_id", None),
                    additional_properties=getattr(msg, "additional_properties", None),
                    raw_representation=getattr(msg, "raw_representation", None),
                )
            )

        if stripped_items or dropped_messages:
            logger.debug(
                "[%s] ReasoningSafeHandoffMiddleware: stripped %d item(s), dropped %d message(s) from cross-agent history",
                self.agent_name, stripped_items, dropped_messages,
            )
            context.messages = cleaned  # type: ignore[assignment]
        await call_next()


def _load_yaml(path: "str | Path") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_agent_paths(team: dict, team_yaml_path: "str | Path") -> "list[Path]":
    base = Path(team_yaml_path).parent
    paths: "list[Path]" = []
    for ref in team.get("orchestration", {}).get("agents", []):
        p = Path(ref)
        paths.append(p if p.is_absolute() else (base / p).resolve())
    return paths


def _client(config: TeamConfig, model: "str | None"):
    """Build a chat client using Entra ID auth via ``az login``.

    Priority:
      1. ``FOUNDRY_PROJECT_ENDPOINT`` (config.foundry_project_endpoint) — always
         preferred so leaked ``AZURE_OPENAI_*`` env vars from other projects
         can't hijack the client.
      2. ``AZURE_OPENAI_ENDPOINT`` — only when no Foundry endpoint is configured.

    In both cases the Azure CLI credential is used; any ``AZURE_OPENAI_API_KEY``
    from the environment is explicitly ignored.
    """
    credential = AzureCliCredential()

    if config.foundry_project_endpoint:
        return FoundryChatClient(
            project_endpoint=config.foundry_project_endpoint,
            model=model or config.model,
            credential=credential,
        )

    aoai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if aoai_endpoint:
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            model=model or config.model,
            azure_endpoint=aoai_endpoint,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            credential=credential,
            api_key=None,  # force token auth; ignore any AZURE_OPENAI_API_KEY
        )

    raise RuntimeError(
        "No chat endpoint configured. Set FOUNDRY_PROJECT_ENDPOINT (preferred) "
        "or AZURE_OPENAI_ENDPOINT."
    )


async def _build_agent(stack: AsyncExitStack, config: TeamConfig, agent_def: dict) -> Agent:
    """Build one Agent from a parsed agent YAML dict."""
    definition = agent_def.get("definition", {}) or {}
    name = agent_def.get("name", "agent")

    tools: "list[Any]" = []
    for tool in definition.get("tools", []) or []:
        tool_type = tool.get("type", "function")
        if tool_type == "function":
            impl = TOOL_REGISTRY.get(tool["name"])
            if impl is None:
                logger.warning("No implementation registered for tool '%s'", tool["name"])
            else:
                tools.append(impl)
        elif tool_type == "mcp":
            mcp_tool = MCPStreamableHTTPTool(
                name=tool.get("server_label", "mcp"),
                url=tool["server_url"],
            )
            try:
                await stack.enter_async_context(mcp_tool)
                tools.append(mcp_tool)
            except Exception as exc:  # MCP endpoint unreachable/unauthorized
                logger.warning(
                    "Skipping MCP tool '%s' (%s): %s",
                    tool.get("server_label", "mcp"), tool.get("server_url"), exc,
                )

    return Agent(
        client=_client(config, definition.get("model")),
        name=name,
        description=agent_def.get("description") or definition.get("description") or name,
        instructions=definition.get("instructions", ""),
        tools=tools,
        # Applied on every chat-client call. Strips cross-agent function_call /
        # function_result / text_reasoning items from the inbound conversation
        # so reasoning models (gpt-5, o-series) can be used with the Sequential
        # / Concurrent / GroupChat / Handoff builders without hitting the
        # "function_call was provided without its required 'reasoning' item" 400.
        middleware=[ReasoningSafeHandoffMiddleware(agent_name=name)],
    )


def _wire(pattern: str, participants: "list[Agent]", by_name: "dict[str, Agent]", orch: dict):
    """Wire the participants into the workflow for the chosen pattern."""
    if pattern == "sequential":
        return SequentialBuilder(participants=participants).build()

    if pattern == "concurrent":
        return ConcurrentBuilder(participants=participants).build()

    if pattern == "group_chat":
        max_rounds = int(orch.get("max_rounds", 6))

        def _select_next(state: GroupChatState) -> str:
            names = list(state.participants.keys())
            return names[state.current_round % len(names)]

        return GroupChatBuilder(
            participants=participants,
            termination_condition=lambda conversation: len(conversation) >= max_rounds,
            selection_func=_select_next,
            intermediate_output_from=participants,
        ).build()

    if pattern == "handoff":
        start = by_name.get(orch.get("start_agent")) or participants[0]
        builder = HandoffBuilder(
            name="vf_triage_team", participants=participants
        ).with_start_agent(start)
        for source, targets in (orch.get("handoffs") or {}).items():
            src = by_name.get(source)
            tgt = [by_name[t] for t in targets if t in by_name]
            if src is not None and tgt:
                builder = builder.add_handoff(src, tgt)
        return builder.build()

    raise ValueError(f"Unknown orchestration pattern: {pattern!r}")


async def run_team(task: str, config: "TeamConfig | None" = None) -> str:
    """Load the team + agents from YAML, wire the pattern, and run one task."""
    config = config or TeamConfig.from_env()
    team = _load_yaml(config.team_yaml)
    orch = team.get("orchestration", {}) or {}
    pattern = (orch.get("pattern") or "sequential").strip().lower().replace("-", "_")

    async with AsyncExitStack() as stack:
        participants: "list[Agent]" = []
        by_name: "dict[str, Agent]" = {}
        for agent_path in _resolve_agent_paths(team, config.team_yaml):
            agent_def = _load_yaml(agent_path)
            agent = await _build_agent(stack, config, agent_def)
            participants.append(agent)
            by_name[agent_def.get("name")] = agent

        logger.info(
            "Loaded %d agents (%s); pattern=%s",
            len(participants), ", ".join(by_name), pattern,
        )

        workflow = _wire(pattern, participants, by_name, orch)

        events = await workflow.run(task)
        outputs = events.get_outputs()
        if not outputs:
            return ""
        final = outputs[-1]
        messages = getattr(final, "messages", None)
        if messages:
            # Skip messages that carried only tool-call / reasoning items with
            # no user-visible text.
            return "\n".join(
                f"[{m.author_name or 'assistant'}] {m.text}"
                for m in messages
                if (m.text or "").strip()
            )
        return str(final)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    task = "Triage incident INC-4291, apply the corrective action, then notify affected customers."
    logger.info("Running 'vf-triage-team'...")
    result = await run_team(task)
    print("\n===== Team Result =====")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
