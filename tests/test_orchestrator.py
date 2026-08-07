"""Tests for the shared YAML-driven orchestrator."""

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from types import SimpleNamespace

import pytest
from agent_framework import Message

import orchestrator


def test_billing_agents_use_mcp_tools_exposed_by_server():
    from mcp_servers.billing_mock_mcp.server import mcp

    team_path, team, _ = orchestrator.load_team("agent_teams/vf_billing_team/team.yaml")
    definitions = [
        orchestrator._load_yaml(orchestrator._resolve_path(team_path.parent, ref))
        for ref in team["orchestration"]["agents"]
    ]
    profile_tools = definitions[0]["definition"]["tools"]
    investigation_tools = definitions[1]["definition"]["tools"]
    response_tools = definitions[2]["definition"]["tools"]

    assert profile_tools[0]["type"] == "mcp"
    assert investigation_tools[0]["type"] == "mcp"
    assert profile_tools[0]["server_url"].endswith("/mcp")
    assert investigation_tools[0]["server_url"] == profile_tools[0]["server_url"]
    assert response_tools == []

    registered = {tool.name: tool.inputSchema for tool in asyncio.run(mcp.list_tools())}
    assert "selectedAccountReference" in registered["get_billing_profiles"]["properties"]
    assert set(registered["get_billing_data"]["required"]) == {
        "billing_profile_id",
        "data_types",
    }


@pytest.mark.asyncio
async def test_client_resources_close_with_workflow_stack():
    closed = []

    class AsyncResource:
        def __init__(self, name):
            self.name = name

        async def close(self):
            closed.append(self.name)

    class Credential:
        def close(self):
            closed.append("credential")

    client = SimpleNamespace(
        project_client=AsyncResource("project"),
        client=AsyncResource("openai"),
    )
    async with AsyncExitStack() as stack:
        orchestrator._register_client_resources(stack, client, Credential())
        assert closed == []

    assert closed == ["openai", "project", "credential"]


@pytest.mark.parametrize(
    ("team_yaml", "agent_names", "tool_names"),
    [
        (
            "agent_teams/vf_billing_team/team.yaml",
            [
                "vf-billing-profile-agent",
                "vf-billing-investigation-agent",
                "vf-billing-response-agent",
            ],
            {"get_billing_profiles", "get_billing_data"},
        ),
        (
            "agent_teams/vf_triage_team/team.yaml",
            ["vf-triage-tool-agent", "vf-comms-agent"],
            {
                "get_incident",
                "fetch_telemetry",
                "fetch_customer_impact",
                "apply_change",
                "draft_notification",
                "notify_customers",
            },
        ),
    ],
)
def test_load_team_resolves_agents_in_yaml_order(team_yaml, agent_names, tool_names):
    team_path, team, registry = orchestrator.load_team(team_yaml)
    refs = team["orchestration"]["agents"]
    loaded_names = [
        orchestrator._load_yaml(orchestrator._resolve_path(team_path.parent, ref))["name"]
        for ref in refs
    ]

    assert loaded_names == agent_names
    assert set(registry) == tool_names


def test_billing_pipeline_propagates_profile_stop_statuses():
    team_path, team, _ = orchestrator.load_team("agent_teams/vf_billing_team/team.yaml")
    definitions = {
        definition["name"]: definition["definition"]["instructions"]
        for definition in (
            orchestrator._load_yaml(orchestrator._resolve_path(team_path.parent, ref))
            for ref in team["orchestration"]["agents"]
        )
    }

    investigation = definitions["vf-billing-investigation-agent"]
    response = definitions["vf-billing-response-agent"]
    for status in ("ACCOUNT_SELECTION_REQUIRED", "PROFILE_RETRIEVAL_FAILED"):
        assert status in investigation
        assert status in response
    assert "do not call get_billing_data" in investigation


def test_sequential_workflow_passes_only_prior_agent_response(monkeypatch):
    captured = {}

    class FakeSequentialBuilder:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def build(self):
            return "workflow"

    participants = [object(), object(), object()]
    monkeypatch.setattr(orchestrator, "SequentialBuilder", FakeSequentialBuilder)

    workflow = orchestrator._wire_workflow(
        "billing",
        "sequential",
        participants,
        {},
        {"chain_only_agent_responses": True},
    )

    assert workflow == "workflow"
    assert captured == {
        "participants": participants,
        "chain_only_agent_responses": True,
        "intermediate_output_from": "all_other",
    }


@pytest.mark.asyncio
async def test_reasoning_safe_handoff_filters_cross_agent_tool_items():
    middleware = orchestrator.ReasoningSafeHandoffMiddleware("downstream")
    context = SimpleNamespace(
        messages=[
            Message(
                role="assistant",
                author_name="upstream",
                contents=[
                    {"type": "function_call"},
                    {"type": "text_reasoning"},
                    {"type": "text", "text": "stage output"},
                ],
            )
        ]
    )
    called = False

    async def call_next() -> None:
        nonlocal called
        called = True

    await middleware.process(context, call_next)

    assert called
    assert [content.type for content in context.messages[0].contents] == ["text"]


@pytest.mark.asyncio
async def test_run_chat_reuses_workflow_until_exit(monkeypatch, capsys):
    workflow = object()
    tasks = []
    replies = iter(["personal", "quit"])

    @asynccontextmanager
    async def fake_open_team(team_yaml):
        yield workflow, "initial task"

    async def fake_run_workflow(selected_workflow, task):
        assert selected_workflow is workflow
        tasks.append(task)
        return f"response to {task}"

    monkeypatch.setattr(orchestrator, "open_team", fake_open_team)
    monkeypatch.setattr(orchestrator, "_run_workflow", fake_run_workflow)
    monkeypatch.setattr("builtins.input", lambda prompt: next(replies))

    await orchestrator.run_chat("team.yaml")

    assert tasks == ["initial task", "personal"]
    output = capsys.readouterr().out
    assert "Team> response to initial task" in output
    assert "Team> response to personal" in output