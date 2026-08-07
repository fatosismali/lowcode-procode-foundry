"""Drive any YAML-defined team and return per-agent output.

The shared orchestrator flattens final output for terminal use. Evaluations
re-run the same wiring here so agent messages and tool evidence remain intact.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import EvalConfig


def load_orchestrator(team_dir: Path):
    """Import the repository-level dynamic YAML orchestrator."""
    team_dir = Path(team_dir).resolve()
    orchestrator_path = next(
        (parent / "orchestrator.py" for parent in team_dir.parents if (parent / "orchestrator.py").is_file()),
        None,
    )
    if orchestrator_path is None:
        raise FileNotFoundError(f"No repository orchestrator.py found above {team_dir}")
    spec = importlib.util.spec_from_file_location("dynamic_team_orchestrator", orchestrator_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {orchestrator_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        return module
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            f"{exc.name!r} is missing, so the team under test cannot be loaded. "
            f"Install the runtime dependencies from the repository requirements.txt."
        ) from exc


@dataclass(frozen=True)
class TeamRuntimeConfig:
    team_yaml: Path


def resolve_agent_paths(orchestrator, team: dict, team_yaml: Path) -> list[Path]:
    """Resolve ordered agent references using the shared runtime's path rules."""
    team_yaml = Path(team_yaml)
    refs = (team.get("orchestration", {}) or {}).get("agents", []) or []
    return [orchestrator._resolve_path(team_yaml.parent, ref) for ref in refs]


def extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of an agent message. Never raises."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1] if "```" in cleaned[3:] else cleaned[3:]
        cleaned = cleaned.removeprefix("json").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def build_task(row: dict[str, Any], sample_task: str | None, task_config: dict[str, Any]) -> str:
    """Map a dataset row into the team's configured task envelope."""
    query = str(row.get("query") or "")
    try:
        payload = json.loads(sample_task or "")
    except ValueError:
        return query
    if not isinstance(payload, dict):
        return query
    query_field = task_config.get("query_field")
    if query_field:
        payload[str(query_field)] = query
    for dataset_field, task_field in (task_config.get("input_fields", {}) or {}).items():
        payload[str(task_field)] = row.get(str(dataset_field))
    return json.dumps(payload)


def system_message_from_yaml(orchestrator, team_config) -> str:
    """Short summary rather than the full prompts, which would swamp the judge."""
    team = orchestrator._load_yaml(team_config.team_yaml)
    lines = [team.get("description") or team.get("name", "")]
    for path in resolve_agent_paths(orchestrator, team, team_config.team_yaml):
        agent_def = orchestrator._load_yaml(path)
        name = agent_def.get("name", "agent")
        description = agent_def.get("description") or (agent_def.get("definition", {}) or {}).get(
            "description", ""
        )
        lines.append(f"- {name}: {description}")
    return "\n".join(line for line in lines if line)


def tool_definitions_from_yaml(orchestrator, team_config) -> list[dict[str, Any]]:
    """Tool schemas come from the agent YAMLs rather than runtime introspection."""
    team = orchestrator._load_yaml(team_config.team_yaml)
    definitions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in resolve_agent_paths(orchestrator, team, team_config.team_yaml):
        agent_def = orchestrator._load_yaml(path)
        for tool in (agent_def.get("definition", {}) or {}).get("tools", []) or []:
            name = tool.get("name")
            if tool.get("type", "function") != "function" or not name or name in seen:
                continue
            seen.add(name)
            definitions.append(
                {
                    "name": name,
                    "description": (tool.get("description") or "").strip(),
                    "parameters": tool.get("parameters") or {"type": "object", "properties": {}},
                }
            )
    return definitions


def tool_calls_from_message(message) -> list[dict[str, Any]]:
    """Duck-typed so it survives agent-framework content-type changes."""
    calls: list[dict[str, Any]] = []
    for content in getattr(message, "contents", None) or []:
        name = getattr(content, "name", None)
        call_id = getattr(content, "call_id", None)
        if not name or call_id is None or not hasattr(content, "arguments"):
            continue
        arguments = content.arguments
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except ValueError:
                arguments = {"raw": arguments}
        calls.append(
            {
                "type": "tool_call",
                "tool_call_id": str(call_id),
                "name": name,
                "arguments": arguments or {},
            }
        )
    return calls


def tool_results_from_message(message) -> list[dict[str, Any]]:
    """Results carry a call_id and a result but no name or arguments."""
    results: list[dict[str, Any]] = []
    for content in getattr(message, "contents", None) or []:
        call_id = getattr(content, "call_id", None)
        if call_id is None or hasattr(content, "arguments") or not hasattr(content, "result"):
            continue
        result = content.result
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except ValueError:
                pass
        results.append({"tool_call_id": str(call_id), "tool_result": result})
    return results


def build_messages(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """OpenAI agent-message format. The agentic judges need to see the tool
    calls and their results, otherwise they read a bare answer as invented."""
    messages: list[dict[str, Any]] = []
    for entry in agents:
        for call in entry["tool_calls"]:
            messages.append({"role": "assistant", "content": [call]})
        for result in entry["tool_results"]:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": result["tool_call_id"],
                    "content": [{"type": "tool_result", "tool_result": result["tool_result"]}],
                }
            )
        if entry["text"]:
            messages.append(
                {"role": "assistant", "content": [{"type": "text", "text": entry["text"]}]}
            )
    return messages


@dataclass
class TeamResult:
    final_text: str = ""
    agents: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    transcript: str = ""
    error: str = ""


async def run_team_traced(task: str, orchestrator, team_config) -> TeamResult:
    """Same wiring as run_team(), but every message is kept."""
    team_path, team, tool_registry = orchestrator.load_team(team_config.team_yaml)
    orch = team.get("orchestration", {}) or {}
    pattern = (orch.get("pattern") or "sequential").strip().lower().replace("-", "_")

    async with AsyncExitStack() as stack:
        participants = []
        by_name = {}
        for agent_path in resolve_agent_paths(orchestrator, team, team_path):
            agent_def = orchestrator._load_yaml(agent_path)
            agent = await orchestrator._build_agent(stack, agent_def, tool_registry)
            participants.append(agent)
            by_name[agent_def.get("name")] = agent

        workflow = orchestrator._wire_workflow(
            team.get("name", team_path.stem), pattern, participants, by_name, orch
        )
        events = await workflow.run(task)
        outputs = events.get_outputs()

    if not outputs:
        return TeamResult(error="Team produced no output")

    messages = getattr(outputs[-1], "messages", None) or []
    agents: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    for message in messages:
        calls = tool_calls_from_message(message)
        results = tool_results_from_message(message)
        tool_calls.extend(calls)
        author = getattr(message, "author_name", None)
        text = (getattr(message, "text", "") or "").strip()
        if not author and not calls and not results:
            continue
        agents.append(
            {
                "name": author or "",
                "text": text,
                "json": extract_json(text),
                "tool_calls": calls,
                "tool_results": results,
            }
        )

    named = [a for a in agents if a["name"] and a["text"]]
    if not named:
        return TeamResult(
            final_text=str(outputs[-1]), tool_calls=tool_calls, transcript=str(outputs[-1])
        )

    return TeamResult(
        final_text=named[-1]["text"],
        agents=named,
        tool_calls=tool_calls,
        messages=build_messages(agents),
        transcript="\n\n".join(f"[{a['name']}]\n{a['text']}" for a in named),
    )


class TeamTarget:
    """Callable passed to evaluate(); one call per dataset row."""

    def __init__(self, config: EvalConfig, row_timeout: float = 300.0):
        self.config = config
        self.row_timeout = row_timeout
        self.suite = config.suite
        os.environ["FOUNDRY_PROJECT_ENDPOINT"] = config.foundry_project_endpoint
        self.orchestrator = load_orchestrator(config.team_dir)
        self.team_config = TeamRuntimeConfig(self.suite.team_yaml)
        team = self.orchestrator._load_yaml(self.team_config.team_yaml)
        self.sample_task = (team.get("orchestration", {}) or {}).get("task")
        self.tool_definitions = tool_definitions_from_yaml(self.orchestrator, self.team_config)
        self.system_message = system_message_from_yaml(self.orchestrator, self.team_config)

    def __call__(self, row: dict[str, Any]) -> dict:
        query = str(row.get("query") or "")
        task = build_task(row, self.sample_task, self.suite.task)
        try:
            result = asyncio.run(
                asyncio.wait_for(
                    run_team_traced(task, self.orchestrator, self.team_config),
                    timeout=self.row_timeout,
                )
            )
        except TimeoutError:
            result = TeamResult(error=f"Team execution timed out after {self.row_timeout:g}s")
        except Exception as exc:  # one bad row must not kill the whole run
            result = TeamResult(error=f"{type(exc).__name__}: {exc}")

        stages = {a["name"]: a["json"] for a in result.agents}
        detected: list[str] = []
        statuses: list[str] = []
        intents_field = str(self.suite.output.get("intents_field") or "")
        status_field = str(self.suite.output.get("status_field") or "")
        for payload in stages.values():
            if not payload:
                continue
            if intents_field and isinstance(payload.get(intents_field), list):
                detected = [str(i) for i in payload[intents_field]]
            if status_field and payload.get(status_field):
                statuses.append(str(payload[status_field]))

        return {
            "response": result.final_text,
            "detected_intent": detected,
            "workflow_statuses": statuses,
            "workflow_status": statuses[-1] if statuses else "",
            "agent_outputs": stages,
            "tool_calls": result.tool_calls,
            "tool_definitions": self.tool_definitions,
            "query_messages": [
                {"role": "system", "content": self.system_message},
                {"role": "user", "content": [{"type": "text", "text": query}]},
            ],
            "response_messages": result.messages,
            "transcript": result.transcript,
            "error": result.error,
        }
