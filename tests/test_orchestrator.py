"""Tests for the shared YAML-driven orchestrator."""

from types import SimpleNamespace

import pytest
from agent_framework import Message

import orchestrator


@pytest.mark.parametrize(
    ("team_yaml", "agent_names", "tool_names"),
    [
        (
            "generated_agents/vf_billing_team/team.yaml",
            [
                "vf-billing-profile-agent",
                "vf-billing-investigation-agent",
                "vf-billing-response-agent",
            ],
            {"get_billing_profiles", "get_billing_data"},
        ),
        (
            "generated_agents/vf_triage_team/team.yaml",
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