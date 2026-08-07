"""Unit tests for generic evaluation infrastructure. No Azure or network calls."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from azure.core.credentials import AccessToken

from evals.auth import CachedAzureCliCredential
from evals.config import EvalConfig, EvalSuite
from evals.evaluators import (
    ALL_JUDGES,
    QUALITY_JUDGES,
    SAFETY_JUDGES,
    judge_inputs,
    publish_criteria,
    read_verdict,
)
from evals.graders import (
    FactRecallEvaluator,
    IntentMatchEvaluator,
    ScopeAdherenceEvaluator,
    WorkflowSchemaEvaluator,
    normalise,
)
from evals.run_evals import (
    GRADER_INPUTS,
    GRADERS,
    build_graders,
    build_item,
    check_gate,
    load_rows,
    load_thresholds,
    pass_rates,
)
from evals.target import (
    TeamTarget,
    build_messages,
    build_task,
    extract_json,
    tool_calls_from_message,
    tool_definitions_from_yaml,
    tool_results_from_message,
)


@pytest.fixture
def suite(tmp_path: Path) -> EvalSuite:
    team_dir = tmp_path / "sample_team"
    eval_dir = team_dir / "evals"
    datasets = eval_dir / "datasets"
    datasets.mkdir(parents=True)
    (team_dir / "team.yaml").write_text("name: sample-team\n", encoding="utf-8")
    (datasets / "smoke.jsonl").write_text(
        json.dumps({"id": "row-1", "query": "Find item", "reference": "A-1"}) + "\n",
        encoding="utf-8",
    )
    (eval_dir / "thresholds.yaml").write_text(
        "criteria:\n  schema_valid: 1.0\n", encoding="utf-8"
    )
    (eval_dir / "eval.yaml").write_text(
        """name: sample-team
team_yaml: ../team.yaml
sets:
  smoke: ./datasets/smoke.jsonl
thresholds: ./thresholds.yaml
reports_dir: ./reports
task:
  query_field: request
  input_fields:
    reference: selectedReference
output:
  status_field: state
  intents_field: labels
workflow_schema:
  READY: [payload]
scope:
  leak_patterns: ['\\bSECRET-[0-9]+\\b']
  refusal_patterns: ['outside my scope']
  clarification_patterns: ['which item']
""",
        encoding="utf-8",
    )
    return EvalSuite.load(team_dir)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("\u00a345.20", "45.20"),
        ("GBP 45.20", "45.20"),
        ("1,234.00", "1234.00"),
        ("  Result   ready ", "result ready"),
    ],
)
def test_normalise(text, expected):
    assert normalise(text) == expected


def test_eval_suite_resolves_team_owned_paths(suite):
    assert suite.name == "sample-team"
    assert set(suite.sets) == {"smoke"}
    assert suite.team_yaml.name == "team.yaml"
    assert suite.reports_dir.name == "reports"
    assert suite.workflow_schema == {"READY": ("payload",)}


def test_eval_suite_requires_sets(tmp_path):
    eval_dir = tmp_path / "team" / "evals"
    eval_dir.mkdir(parents=True)
    (eval_dir / "eval.yaml").write_text("name: empty\n", encoding="utf-8")
    with pytest.raises(ValueError, match="at least one set"):
        EvalSuite.load(tmp_path / "team")


def test_eval_config_enforces_azure_cli_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://unrelated.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "unrelated-key")
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-key")
    monkeypatch.delenv("EVAL_JUDGE_ENDPOINT", raising=False)
    monkeypatch.delenv("EVAL_JUDGE_API_KEY", raising=False)

    config = EvalConfig.from_env(
        project_endpoint="https://sample.services.ai.azure.com/api/projects/demo",
        team_dir=tmp_path,
    )

    assert config.judge_endpoint == "https://sample.services.ai.azure.com"
    assert "api_key" not in config.judge_model_config()
    assert "AZURE_OPENAI_API_KEY" not in os.environ
    assert "OPENAI_API_KEY" not in os.environ


def test_eval_config_rejects_explicit_judge_key(monkeypatch, tmp_path):
    monkeypatch.setenv("EVAL_JUDGE_API_KEY", "forbidden-key")

    with pytest.raises(ValueError, match="Azure CLI authentication"):
        EvalConfig.from_env(
            project_endpoint="https://sample.services.ai.azure.com/api/projects/demo",
            team_dir=tmp_path,
        )


def test_cached_cli_credential_reuses_token(monkeypatch):
    calls = []

    class FakeAzureCliCredential:
        def get_token(self, *scopes, **kwargs):
            calls.append((scopes, kwargs))
            return AccessToken("token", 4_102_444_800)

        def close(self):
            pass

    monkeypatch.setattr("evals.auth.AzureCliCredential", FakeAzureCliCredential)
    credential = CachedAzureCliCredential()

    first = credential.get_token("https://ai.azure.com/.default")
    second = credential.get_token("https://ai.azure.com/.default")

    assert first is second
    assert len(calls) == 1


class TestIntentMatch:
    evaluator = IntentMatchEvaluator()

    def test_exact_match_is_order_insensitive(self):
        result = self.evaluator(detected_intent=["beta", "alpha"], expected_intent=["alpha", "beta"])
        assert result["intent_match_result"] == "pass"
        assert result["intent_overlap"] == 1.0

    def test_partial_match_reports_missing_label(self):
        result = self.evaluator(detected_intent=["alpha"], expected_intent=["alpha", "beta"])
        assert result["intent_match_result"] == "fail"
        assert "beta" in result["intent_match_reason"]

    def test_no_expectation_is_not_applicable(self):
        assert self.evaluator(detected_intent=["alpha"], expected_intent=[])["intent_match"] is None


class TestWorkflowSchema:
    def test_unconfigured_schema_is_not_applicable(self):
        result = WorkflowSchemaEvaluator()(agent_outputs={"worker": {"state": "READY"}})
        assert result["schema_valid_result"] == "not applicable"

    def test_configured_status_and_keys_pass(self):
        evaluator = WorkflowSchemaEvaluator({"READY": ("payload",)}, status_field="state")
        result = evaluator(agent_outputs={"worker": {"state": "READY", "payload": {}}})
        assert result["schema_valid_result"] == "pass"

    def test_missing_key_fails(self):
        evaluator = WorkflowSchemaEvaluator({"READY": ("payload",)}, status_field="state")
        result = evaluator(agent_outputs={"worker": {"state": "READY"}})
        assert result["schema_valid_result"] == "fail"
        assert "payload" in result["schema_valid_reason"]

    def test_unknown_status_and_expected_status_fail(self):
        evaluator = WorkflowSchemaEvaluator({"READY": ()}, status_field="state")
        assert evaluator(agent_outputs={"worker": {"state": "OTHER"}})["schema_valid"] == 0.0
        assert evaluator(
            agent_outputs={"worker": {"state": "READY"}}, expected_status="COMPLETE"
        )["schema_valid"] == 0.0


class TestFactRecall:
    evaluator = FactRecallEvaluator()

    def test_required_facts_present(self):
        assert self.evaluator(response="Result 42 ready", required_facts=["42", "ready"])[
            "fact_recall_result"
        ] == "pass"

    def test_missing_or_forbidden_fact_fails(self):
        assert self.evaluator(response="Result ready", required_facts=["42"])["fact_recall"] == 0.0
        assert self.evaluator(response="Result 99", forbidden_facts=["99"])["fact_recall"] == 0.0

    def test_no_expectations_is_not_applicable(self):
        assert self.evaluator(response="anything")["fact_recall"] is None


class TestScopeAdherence:
    evaluator = ScopeAdherenceEvaluator(
        leak_patterns=[r"\bSECRET-[0-9]+\b"],
        refusal_patterns=[r"outside my scope"],
        clarification_patterns=[r"which item"],
    )

    def test_answer_refusal_and_clarification(self):
        assert self.evaluator(response="The result is ready.", expected_behaviour="answer")[
            "scope_adherence_result"
        ] == "pass"
        assert self.evaluator(response="That is outside my scope.", expected_behaviour="refuse")[
            "scope_adherence_result"
        ] == "pass"
        assert self.evaluator(response="Which item do you mean?", expected_behaviour="clarify")[
            "scope_adherence_result"
        ] == "pass"

    def test_leak_fails(self):
        result = self.evaluator(response="The key is SECRET-123.", expected_behaviour="answer")
        assert result["scope_adherence_result"] == "fail"


class TestTargetHelpers:
    def test_extract_json(self):
        assert extract_json('```json\n{"state": "READY"}\n```') == {"state": "READY"}
        assert extract_json("plain text") is None

    def test_build_task_uses_manifest_mapping(self):
        row = {"query": "Find item", "reference": "A-1"}
        task = build_task(
            row,
            '{"request":"seed","selectedReference":null}',
            {"query_field": "request", "input_fields": {"reference": "selectedReference"}},
        )
        assert json.loads(task) == {"request": "Find item", "selectedReference": "A-1"}

    def test_build_task_falls_back_to_query_for_plain_task(self):
        assert build_task({"query": "Find item"}, "plain", {}) == "Find item"

    def test_team_target_reports_row_timeout(self, monkeypatch):
        async def slow_team(*args):
            import asyncio

            await asyncio.sleep(1)

        monkeypatch.setattr("evals.target.run_team_traced", slow_team)
        target = object.__new__(TeamTarget)
        target.row_timeout = 0.01
        target.orchestrator = object()
        target.team_config = object()
        target.sample_task = None
        target.suite = SimpleNamespace(task={}, output={})
        target.tool_definitions = []
        target.system_message = ""

        result = target({"query": "Find item"})

        assert result["error"] == "Team execution timed out after 0.01s"


class _FakeOrchestrator:
    def __init__(self, team, agents):
        self.team = team
        self.agents = agents

    def _load_yaml(self, path):
        return self.agents.get(str(path), self.team)

    def _resolve_path(self, base, path):
        return path


def test_tool_definitions_are_discovered_without_domain_assumptions():
    runtime = _FakeOrchestrator(
        {"orchestration": {"agents": ["worker.yaml"]}},
        {
            "worker.yaml": {
                "definition": {
                    "tools": [
                        {
                            "type": "function",
                            "name": "lookup_item",
                            "description": " Lookup an item. ",
                            "parameters": {"type": "object"},
                        }
                    ]
                }
            }
        },
    )
    definitions = tool_definitions_from_yaml(runtime, SimpleNamespace(team_yaml="team.yaml"))
    assert definitions[0]["name"] == "lookup_item"
    assert definitions[0]["description"] == "Lookup an item."


def test_tool_calls_results_and_messages_are_preserved():
    message = SimpleNamespace(
        contents=[
            SimpleNamespace(name="lookup_item", call_id="call-1", arguments='{"id":"A-1"}'),
            SimpleNamespace(call_id="call-1", result='{"state":"ready"}'),
        ]
    )
    calls = tool_calls_from_message(message)
    results = tool_results_from_message(message)
    assert calls[0]["arguments"] == {"id": "A-1"}
    assert results[0]["tool_result"] == {"state": "ready"}
    messages = build_messages(
        [{"name": "worker", "text": "done", "tool_calls": calls, "tool_results": results}]
    )
    assert [entry["role"] for entry in messages] == ["assistant", "tool", "assistant"]


def test_manifest_builds_configured_graders(suite):
    graders = build_graders(suite)
    assert set(graders) == set(GRADERS)
    result = graders["schema_valid"](agent_outputs={"worker": {"state": "READY", "payload": {}}})
    assert result["schema_valid_result"] == "pass"


def test_dataset_and_threshold_loading_are_manifest_driven(suite):
    assert load_rows(suite.sets["smoke"])[0]["reference"] == "A-1"
    assert load_rows(suite.sets["smoke"], limit=1)[0]["id"] == "row-1"
    assert load_thresholds(suite) == {"schema_valid": 1.0}


def test_pass_rates_and_gate_ignore_not_applicable():
    items = [
        {"metric_result": "pass"},
        {"metric_result": "fail"},
        {"metric_result": "not applicable"},
    ]
    rates = pass_rates(items, ["metric"])
    assert rates["metric"] == 0.5
    assert check_gate(rates, {"metric": 0.5})[0]["passed"] is True


def test_grader_wiring_is_complete():
    assert set(GRADERS) == set(GRADER_INPUTS)
    assert not set(QUALITY_JUDGES) & set(SAFETY_JUDGES)
    assert set(ALL_JUDGES) == set(QUALITY_JUDGES) | set(SAFETY_JUDGES)


def test_judge_inputs_and_publish_criteria():
    item = {
        "query": "q",
        "response": "r",
        "context": "c",
        "tool_calls": [],
        "tool_definitions": [],
        "query_messages": [{"role": "user"}],
        "response_messages": [{"role": "assistant"}],
    }
    assert judge_inputs("groundedness", item)["context"] == "c"
    assert judge_inputs("task_adherence", item)["query"] == item["query_messages"]
    assert publish_criteria(["metric"])[0]["reference"] == "fail"


def test_read_verdict_handles_result_label_and_safety_alias():
    assert read_verdict("groundedness", {"groundedness_result": "pass"})[0] == "pass"
    assert read_verdict("indirect_attack", {"xpia_label": False})[0] == "pass"


def test_build_item_carries_expected_and_actual_fields():
    row = {
        "id": "row-1",
        "query": "Find item",
        "expected_intent": ["lookup"],
        "required_facts": ["ready"],
    }
    out = {
        "response": "Item ready",
        "detected_intent": ["lookup"],
        "workflow_status": "READY",
        "agent_outputs": {},
        "transcript": "trace",
        "tool_calls": [],
        "tool_definitions": [],
        "query_messages": [],
        "response_messages": [],
        "error": "",
    }
    item = build_item(row, out)
    assert item["expected_intent"] == "lookup"
    assert item["detected_intent"] == "lookup"
    assert item["workflow_status"] == "READY"
