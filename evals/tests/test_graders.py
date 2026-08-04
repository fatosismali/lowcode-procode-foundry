"""Unit tests for the deterministic graders and the suite wiring. No Azure, no network."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

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
    SETS,
    build_item,
    check_gate,
    load_rows,
    load_thresholds,
    pass_rates,
)
from evals.target import (
    build_messages,
    build_task,
    extract_json,
    tool_calls_from_message,
    tool_definitions_from_yaml,
    tool_results_from_message,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("\u00a345.20", "45.20"),
        ("GBP 45.20", "45.20"),
        ("45.20", "45.20"),
        ("\u00a31,234.00", "1234.00"),
        ("  Your  bill   is \u00a345.20 ", "your bill is 45.20"),
    ],
)
def test_normalise_makes_currency_comparable(text, expected):
    assert normalise(text) == expected


class TestIntentMatch:
    evaluator = IntentMatchEvaluator()

    def test_exact_match_passes(self):
        result = self.evaluator(
            detected_intent=["current_bill", "payment_status"],
            expected_intent=["payment_status", "current_bill"],
        )
        assert result["intent_match"] == 1.0
        assert result["intent_match_result"] == "pass"
        assert result["intent_overlap"] == 1.0

    def test_partial_match_fails_exact_but_scores_overlap(self):
        result = self.evaluator(
            detected_intent=["current_bill"],
            expected_intent=["current_bill", "payment_status"],
        )
        assert result["intent_match"] == 0.0
        assert result["intent_match_result"] == "fail"
        assert result["intent_overlap"] == 0.5
        assert "payment_status" in result["intent_match_reason"]

    def test_case_and_whitespace_insensitive(self):
        result = self.evaluator(
            detected_intent=[" Current_Bill "], expected_intent=["current_bill"]
        )
        assert result["intent_match"] == 1.0

    def test_missing_detection_fails(self):
        result = self.evaluator(detected_intent=[], expected_intent=["current_bill"])
        assert result["intent_match"] == 0.0

    def test_missing_expectation_is_not_applicable_rather_than_a_failure(self):
        result = self.evaluator(detected_intent=["current_bill"], expected_intent=[])
        assert result["intent_match"] is None
        assert result["intent_match_result"] == "not applicable"


class TestWorkflowSchema:
    evaluator = WorkflowSchemaEvaluator()

    def test_valid_pipeline_passes(self):
        result = self.evaluator(
            agent_outputs={
                "profile": {"workflowStatus": "ACCOUNT_RESOLVED", "billingContext": {}},
                "investigation": {
                    "workflowStatus": "BILLING_EVIDENCE_READY",
                    "detectedIntent": ["current_bill"],
                    "billingEvidence": {},
                },
            }
        )
        assert result["schema_valid"] == 1.0
        assert result["schema_valid_result"] == "pass"

    def test_missing_required_key_fails(self):
        result = self.evaluator(
            agent_outputs={
                "investigation": {
                    "workflowStatus": "BILLING_EVIDENCE_READY",
                    "detectedIntent": ["current_bill"],
                }
            }
        )
        assert result["schema_valid"] == 0.0
        assert "billingEvidence" in result["schema_valid_reason"]

    def test_unknown_status_fails(self):
        result = self.evaluator(agent_outputs={"a": {"workflowStatus": "SOMETHING_ELSE"}})
        assert result["schema_valid"] == 0.0

    def test_expected_status_not_reached_fails(self):
        result = self.evaluator(
            agent_outputs={"profile": {"workflowStatus": "ACCOUNT_RESOLVED", "billingContext": {}}},
            expected_status="BILLING_EVIDENCE_READY",
        )
        assert result["schema_valid"] == 0.0

    def test_no_structured_output_fails(self):
        assert self.evaluator(agent_outputs={})["schema_valid"] == 0.0


class TestFactRecall:
    evaluator = FactRecallEvaluator()

    def test_all_facts_present_passes(self):
        result = self.evaluator(
            response="Your July bill is \u00a345.20 and is currently pending.",
            required_facts=["45.20", "july", "pending"],
        )
        assert result["fact_recall"] == 1.0
        assert result["fact_recall_result"] == "pass"

    def test_currency_formatting_does_not_matter(self):
        result = self.evaluator(response="Your bill is GBP 45.20.", required_facts=["\u00a345.20"])
        assert result["fact_recall"] == 1.0

    def test_missing_fact_lowers_score(self):
        result = self.evaluator(
            response="Your bill is \u00a345.20.", required_facts=["45.20", "pending"]
        )
        assert result["fact_recall"] == 0.5
        assert result["fact_recall_result"] == "fail"

    def test_forbidden_fact_is_an_immediate_fail(self):
        result = self.evaluator(
            response="Your July bill is \u00a345.20 and is overdue.",
            required_facts=["45.20"],
            forbidden_facts=["overdue"],
        )
        assert result["fact_recall"] == 0.0
        assert "should not" in result["fact_recall_reason"]

    def test_no_expectations_at_all_is_not_applicable(self):
        result = self.evaluator(response="anything", required_facts=[], forbidden_facts=[])
        assert result["fact_recall"] is None
        assert result["fact_recall_result"] == "not applicable"

    def test_forbidden_only_row_passes_when_clean(self):
        result = self.evaluator(response="I can only help with billing.", forbidden_facts=["45.20"])
        assert result["fact_recall"] == 1.0


class TestScopeAdherence:
    evaluator = ScopeAdherenceEvaluator()

    def test_correct_refusal_passes(self):
        result = self.evaluator(
            response="I'm sorry, I can only talk about billing.",
            expected_behaviour="refuse",
        )
        assert result["scope_adherence"] == 1.0

    def test_answering_an_out_of_scope_question_fails(self):
        result = self.evaluator(
            response="It is sunny in Manchester today.", expected_behaviour="refuse"
        )
        assert result["scope_adherence"] == 0.0

    def test_refusal_that_leaks_identifiers_fails(self):
        result = self.evaluator(
            response="I can only help with billing, but your account is 9876546789.",
            expected_behaviour="refuse",
        )
        assert result["scope_adherence"] == 0.0
        assert "leaked" in result["scope_adherence_reason"]

    def test_answer_that_leaks_profile_id_fails(self):
        result = self.evaluator(
            response="Your bill on BP-001 is \u00a345.20.", expected_behaviour="answer"
        )
        assert result["scope_adherence"] == 0.0

    def test_in_scope_answer_passes(self):
        result = self.evaluator(
            response="Your July bill is \u00a345.20 and is currently pending.",
            expected_behaviour="answer",
        )
        assert result["scope_adherence"] == 1.0

    def test_wrongly_refusing_an_in_scope_question_fails(self):
        result = self.evaluator(
            response="I'm sorry, I can only talk about billing.",
            expected_behaviour="answer",
        )
        assert result["scope_adherence"] == 0.0

    def test_clarify_passes_when_a_question_is_asked(self):
        result = self.evaluator(
            response="Which account did you mean, personal or business?",
            expected_behaviour="clarify",
        )
        assert result["scope_adherence"] == 1.0

    def test_clarify_fails_when_it_just_answers(self):
        result = self.evaluator(response="Your bill is \u00a345.20.", expected_behaviour="clarify")
        assert result["scope_adherence"] == 0.0

    def test_empty_response_fails(self):
        assert self.evaluator(response="", expected_behaviour="answer")["scope_adherence"] == 0.0

    def test_masked_account_digits_are_not_treated_as_a_leak(self):
        result = self.evaluator(
            response="Your account ending 6789 has a bill of \u00a345.20.",
            expected_behaviour="answer",
        )
        assert result["scope_adherence"] == 1.0


class TestTargetHelpers:
    def test_extract_json_from_plain_object(self):
        assert extract_json('{"workflowStatus": "ACCOUNT_RESOLVED"}') == {
            "workflowStatus": "ACCOUNT_RESOLVED"
        }

    def test_extract_json_from_fenced_block(self):
        text = '```json\n{"detectedIntent": ["current_bill"]}\n```'
        assert extract_json(text) == {"detectedIntent": ["current_bill"]}

    def test_extract_json_returns_none_for_prose(self):
        assert extract_json("Your July bill is 45.20 and is pending.") is None

    def test_build_task_uses_the_team_envelope(self):
        sample = '{"userQuery": "seed", "selectedAccountReference": null}'
        task = build_task("How much do I owe?", sample, "personal")
        assert extract_json(task) == {
            "userQuery": "How much do I owe?",
            "selectedAccountReference": "personal",
        }

    def test_build_task_falls_back_to_the_raw_query(self):
        assert build_task("How much do I owe?", "not json") == "How much do I owe?"


class _FakeOrchestrator:
    """Stands in for a generated team's src/orchestrator.py."""

    def __init__(self, team, agents):
        self._team = team
        self._agents = agents

    def _load_yaml(self, path):
        return self._agents.get(str(path), self._team)

    def _resolve_agent_paths(self, team, team_yaml):
        return list(self._agents)


class TestToolExtraction:
    def test_definitions_are_read_from_the_agent_yamls(self):
        orchestrator = _FakeOrchestrator(
            team={"orchestration": {"agents": ["a.yaml"]}},
            agents={
                "a.yaml": {
                    "definition": {
                        "tools": [
                            {
                                "type": "function",
                                "name": "get_billing_data",
                                "description": " Consolidated billing data. ",
                                "parameters": {"type": "object", "properties": {}},
                            },
                            {"type": "mcp", "server_label": "kb"},
                        ]
                    }
                }
            },
        )
        definitions = tool_definitions_from_yaml(orchestrator, SimpleNamespace(team_yaml="t.yaml"))
        assert len(definitions) == 1
        assert definitions[0]["name"] == "get_billing_data"
        assert definitions[0]["description"] == "Consolidated billing data."

    def test_duplicate_tool_names_across_agents_are_collapsed(self):
        tool = {"type": "function", "name": "get_billing_data", "description": "x"}
        orchestrator = _FakeOrchestrator(
            team={},
            agents={
                "a.yaml": {"definition": {"tools": [tool]}},
                "b.yaml": {"definition": {"tools": [tool]}},
            },
        )
        definitions = tool_definitions_from_yaml(orchestrator, SimpleNamespace(team_yaml="t.yaml"))
        assert len(definitions) == 1

    def test_tool_calls_are_extracted_in_the_evaluator_shape(self):
        message = SimpleNamespace(
            contents=[
                SimpleNamespace(name="get_billing_data", call_id="call_1", arguments={"x": 1}),
                SimpleNamespace(text="just prose"),
            ]
        )
        calls = tool_calls_from_message(message)
        assert calls == [
            {
                "type": "tool_call",
                "tool_call_id": "call_1",
                "name": "get_billing_data",
                "arguments": {"x": 1},
            }
        ]

    def test_string_arguments_are_parsed(self):
        message = SimpleNamespace(
            contents=[SimpleNamespace(name="t", call_id="c", arguments='{"a": 2}')]
        )
        assert tool_calls_from_message(message)[0]["arguments"] == {"a": 2}

    def test_unparseable_arguments_are_kept_raw(self):
        message = SimpleNamespace(
            contents=[SimpleNamespace(name="t", call_id="c", arguments="not json")]
        )
        assert tool_calls_from_message(message)[0]["arguments"] == {"raw": "not json"}

    def test_message_without_contents_is_safe(self):
        assert tool_calls_from_message(SimpleNamespace()) == []

    def test_results_are_distinguished_from_calls(self):
        message = SimpleNamespace(
            contents=[
                SimpleNamespace(name="t", call_id="c1", arguments={"a": 1}),
                SimpleNamespace(call_id="c1", result={"status": "ok"}),
            ]
        )
        assert tool_calls_from_message(message)[0]["name"] == "t"
        assert tool_results_from_message(message) == [
            {"tool_call_id": "c1", "tool_result": {"status": "ok"}}
        ]

    def test_string_results_are_parsed(self):
        message = SimpleNamespace(contents=[SimpleNamespace(call_id="c", result='{"ok": true}')])
        assert tool_results_from_message(message)[0]["tool_result"] == {"ok": True}


class TestAgentMessages:
    def test_calls_results_and_text_are_ordered_for_the_judges(self):
        agents = [
            {
                "name": "a",
                "text": "done",
                "tool_calls": [
                    {"type": "tool_call", "tool_call_id": "c1", "name": "t", "arguments": {}}
                ],
                "tool_results": [{"tool_call_id": "c1", "tool_result": {"id": "BP-001"}}],
            }
        ]
        messages = build_messages(agents)
        assert [m["role"] for m in messages] == ["assistant", "tool", "assistant"]
        assert messages[1]["content"][0]["type"] == "tool_result"
        assert messages[2]["content"][0]["text"] == "done"

    def test_tool_results_carry_the_grounding_the_judges_need(self):
        # Without the result, tool_call_accuracy reads BP-001 as fabricated.
        agents = [
            {
                "name": "a",
                "text": "",
                "tool_calls": [],
                "tool_results": [{"tool_call_id": "c1", "tool_result": {"id": "BP-001"}}],
            }
        ]
        messages = build_messages(agents)
        assert messages[0]["tool_call_id"] == "c1"
        assert messages[0]["content"][0]["tool_result"] == {"id": "BP-001"}

    def test_empty_agent_list_is_safe(self):
        assert build_messages([]) == []


class TestPassRates:
    def test_not_applicable_rows_are_excluded_from_the_rate(self):
        items = [
            {"fact_recall_result": "pass"},
            {"fact_recall_result": "fail"},
            {"fact_recall_result": "not applicable"},
        ]
        assert pass_rates(items, ["fact_recall"])["fact_recall"] == 0.5

    def test_all_not_applicable_gives_none_rather_than_zero(self):
        items = [{"x_result": "not applicable"}]
        assert pass_rates(items, ["x"])["x"] is None


class TestQualityGate:
    def test_pass_rate_at_threshold_passes(self):
        check = check_gate({"groundedness": 0.9}, {"groundedness": 0.9})[0]
        assert check["passed"] is True

    def test_pass_rate_below_threshold_fails(self):
        check = check_gate({"groundedness": 0.8}, {"groundedness": 0.9})[0]
        assert check["passed"] is False

    def test_safety_criterion_needs_a_clean_sweep(self):
        assert check_gate({"violence": 1.0}, {"violence": 1.0})[0]["passed"]
        assert not check_gate({"violence": 0.9}, {"violence": 1.0})[0]["passed"]

    def test_missing_criterion_fails_rather_than_passing_silently(self):
        check = check_gate({}, {"groundedness": 0.9})[0]
        assert check["passed"] is False
        assert check["note"] == "no applicable rows"


class TestCriteriaWiring:
    def test_every_grader_has_an_input_mapping(self):
        assert set(GRADERS) == set(GRADER_INPUTS)

    def test_quality_and_safety_judges_do_not_overlap(self):
        assert not set(QUALITY_JUDGES) & set(SAFETY_JUDGES)
        assert set(ALL_JUDGES) == set(QUALITY_JUDGES) | set(SAFETY_JUDGES)

    def test_publish_criteria_do_not_punish_not_applicable_rows(self):
        for criterion in publish_criteria(list(GRADERS)):
            assert criterion["operation"] == "ne"
            assert criterion["reference"] == "fail"

    def test_every_threshold_maps_to_a_criterion(self):
        produced = set(GRADERS) | set(ALL_JUDGES)
        for name in load_thresholds():
            assert name in produced, f"threshold {name} has no criterion"

    def test_agentic_judges_get_the_message_form(self):
        item = {
            "query": "q",
            "response": "r",
            "context": "c",
            "tool_calls": [],
            "tool_definitions": [],
            "query_messages": [{"role": "user"}],
            "response_messages": [{"role": "assistant"}],
        }
        for name in ("task_adherence", "tool_call_accuracy"):
            assert judge_inputs(name, item)["query"] == item["query_messages"]
            assert judge_inputs(name, item)["response"] == item["response_messages"]
        assert judge_inputs("coherence", item)["response"] == "r"
        assert judge_inputs("groundedness", item)["context"] == "c"
        assert "query" not in judge_inputs("fluency", item)


class TestReadVerdict:
    def test_reads_the_result_and_reason(self):
        result = {"groundedness": 5.0, "groundedness_result": "pass", "groundedness_reason": "ok"}
        assert read_verdict("groundedness", result) == ("pass", "ok")

    def test_falls_back_to_a_label(self):
        assert read_verdict("intent_resolution", {"intent_resolution_label": "FAIL"})[0] == "fail"

    def test_missing_reason_is_an_empty_string(self):
        assert read_verdict("violence", {"violence_result": "pass"}) == ("pass", "")

    def test_indirect_attack_uses_its_xpia_keys(self):
        # A boolean label flags a defect, so False means no attack and a pass.
        assert read_verdict("indirect_attack", {"xpia_label": False, "xpia_reason": "clean"}) == (
            "pass",
            "clean",
        )
        assert read_verdict("indirect_attack", {"xpia_label": True})[0] == "fail"

    def test_severity_zero_counts_as_a_pass(self):
        assert read_verdict("violence", {"violence": 0})[0] == "pass"
        assert read_verdict("violence", {"violence": "high"})[0] == "fail"


class TestDatasetLoading:
    def _all_rows(self):
        return [r for f in SETS.values() for r in load_rows(f)]

    def test_the_three_sets_fatos_specified_exist(self):
        assert set(SETS) == {"intent_classifier", "billing_agent", "system_e2e"}

    def test_every_set_has_rows(self):
        assert all(load_rows(f) for f in SETS.values())

    def test_limit_applies(self):
        assert len(load_rows(SETS["billing_agent"], limit=3)) == 3

    def test_every_row_has_a_query_and_an_id(self):
        assert all(r.get("query") and r.get("id") for r in self._all_rows())

    def test_ids_are_unique_across_all_sets(self):
        ids = [r["id"] for r in self._all_rows()]
        assert len(ids) == len(set(ids))

    def test_behaviours_are_recognised(self):
        assert {r["expected_behaviour"] for r in self._all_rows()} <= {
            "answer",
            "refuse",
            "clarify",
        }

    def test_intent_set_covers_the_whole_taxonomy(self):
        labels = {i for r in load_rows(SETS["intent_classifier"]) for i in r["expected_intent"]}
        assert len(labels) >= 9, f"only {len(labels)} intent labels covered"

    def test_end_to_end_set_tests_topic_refusal(self):
        rows = load_rows(SETS["system_e2e"])
        assert sum(1 for r in rows if r["expected_behaviour"] == "refuse") >= 3
        assert sum(1 for r in rows if r["expected_behaviour"] == "answer") >= 1

    def test_billing_set_asserts_on_grounded_figures(self):
        assert all(r["required_facts"] for r in load_rows(SETS["billing_agent"]))


class TestBuildItem:
    def _out(self, **over):
        base = {
            "response": "Your bill is \u00a345.20.",
            "detected_intent": ["current_bill"],
            "workflow_status": "BILLING_EVIDENCE_READY",
            "agent_outputs": {},
            "transcript": "t",
            "tool_calls": [],
            "tool_definitions": [],
            "query_messages": [],
            "response_messages": [],
            "error": "",
        }
        base.update(over)
        return base

    def test_expected_and_actual_are_both_carried(self):
        row = {
            "id": "g01",
            "category": "billing_answer",
            "query": "How much do I owe?",
            "expected_intent": ["current_bill"],
            "required_facts": ["45.20"],
        }
        item = build_item(row, self._out())
        assert item["expected_intent"] == "current_bill"
        assert item["detected_intent"] == "current_bill"
        assert item["required_facts"] == "45.20"
        assert item["id"] == "g01"

    def test_missing_optional_fields_become_empty_strings(self):
        item = build_item({"query": "q"}, self._out(detected_intent=[]))
        assert item["expected_intent"] == ""
        assert item["expected_behaviour"] == ""
