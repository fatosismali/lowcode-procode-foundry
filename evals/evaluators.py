"""LLM judges, run locally, plus the criteria used to publish results to Foundry.

Everything is scored on this machine so you get answers without waiting on a
service. Foundry is a publishing step: each locally computed verdict is
submitted as a string_check criterion, so the other department sees one
evaluation with a pass or fail and a reason for every row.
"""

from __future__ import annotations

from typing import Any

from .auth import CachedAzureCliCredential

# Judge name -> azure.ai.evaluation class. Quality judges need a judge model.
QUALITY_JUDGES = {
    "coherence": "CoherenceEvaluator",
    "fluency": "FluencyEvaluator",
    "relevance": "RelevanceEvaluator",
    "groundedness": "GroundednessEvaluator",
    "intent_resolution": "IntentResolutionEvaluator",
    "task_adherence": "TaskAdherenceEvaluator",
    "tool_call_accuracy": "ToolCallAccuracyEvaluator",
}

# Scored by the Foundry RAI service rather than the judge model.
SAFETY_JUDGES = {
    "violence": "ViolenceEvaluator",
    "sexual": "SexualEvaluator",
    "self_harm": "SelfHarmEvaluator",
    "hate_unfairness": "HateUnfairnessEvaluator",
    "indirect_attack": "IndirectAttackEvaluator",
}

ALL_JUDGES = {**QUALITY_JUDGES, **SAFETY_JUDGES}

# Reasoning judges are supported by the quality evaluators only.
_REASONING_CAPABLE = set(QUALITY_JUDGES)


def build_local_judges(config, names: list[str]) -> dict[str, Any]:
    import azure.ai.evaluation as aieval  # noqa: PLC0415

    model_config = config.judge_model_config()
    credential = CachedAzureCliCredential()
    built: dict[str, Any] = {}

    for name in names:
        class_name = ALL_JUDGES.get(name)
        if class_name is None:
            raise ValueError(f"Unknown judge {name!r}. Known: {sorted(ALL_JUDGES)}")
        evaluator = getattr(aieval, class_name, None)
        if evaluator is None:
            raise ImportError(f"{class_name} is missing from the installed azure-ai-evaluation")

        if name in SAFETY_JUDGES:
            built[name] = evaluator(
                azure_ai_project=config.foundry_project_endpoint, credential=credential
            )
        elif config.judge_is_reasoning_model and name in _REASONING_CAPABLE:
            built[name] = evaluator(
                model_config=model_config,
                credential=credential,
                is_reasoning_model=True,
            )
        else:
            built[name] = evaluator(model_config=model_config, credential=credential)

    return built


def judge_inputs(name: str, item: dict[str, Any]) -> dict[str, Any]:
    """The agentic judges need the message form; the rest take plain strings."""
    if name == "fluency":
        return {"response": item["response"]}
    if name == "groundedness":
        return {
            "query": item["query"],
            "context": item["context"],
            "response": item["response"],
        }
    if name == "intent_resolution":
        return {
            "query": item["query"],
            "response": item["response"],
            "tool_definitions": item["tool_definitions"],
        }
    if name == "task_adherence":
        return {
            "query": item["query_messages"],
            "response": item["response_messages"],
            "tool_definitions": item["tool_definitions"],
        }
    if name == "tool_call_accuracy":
        return {
            "query": item["query_messages"],
            "response": item["response_messages"],
            "tool_calls": item["tool_calls"],
            "tool_definitions": item["tool_definitions"],
        }
    return {"query": item["query"], "response": item["response"]}


# Evaluators whose output key does not follow the {name}_* convention.
_LABEL_ALIASES = {"indirect_attack": "xpia"}


def read_verdict(name: str, result: dict[str, Any]) -> tuple[str, str]:
    """Pull a pass/fail label and a reason out of an evaluator's output."""
    alias = _LABEL_ALIASES.get(name, name)
    reason = result.get(f"{name}_reason") or result.get(f"{alias}_reason") or ""

    label = result.get(f"{name}_result")
    if label is None:
        label = result.get(f"{name}_label", result.get(f"{alias}_label"))

    # A boolean label flags a defect, so True means fail.
    if isinstance(label, bool):
        return ("fail" if label else "pass"), str(reason)
    if label is not None:
        return str(label).lower(), str(reason)

    score = result.get(name, result.get(alias))
    passed = score in (0, 0.0, False, "very low", "Very low")
    return ("pass" if passed else "fail"), str(reason)


def publish_criteria(names: list[str]) -> list[dict[str, Any]]:
    """'ne fail' rather than 'eq pass' so rows a criterion does not apply to,
    which report 'not applicable', are not counted as failures."""
    return [
        {
            "type": "string_check",
            "name": name,
            "input": f"{{{{item.{name}_result}}}}",
            "operation": "ne",
            "reference": "fail",
        }
        for name in names
    ]


# Columns carried purely so each row is readable in the portal results table.
BREAKDOWN_FIELDS = (
    "id",
    "category",
    "expected_intent",
    "detected_intent",
    "expected_behaviour",
    "expected_status",
    "workflow_status",
    "required_facts",
    "forbidden_facts",
    "error",
)


def item_schema(criteria_names: list[str]) -> dict[str, Any]:
    properties: dict[str, Any] = {
        key: {"type": "string"} for key in ("query", "response", "context", *BREAKDOWN_FIELDS)
    }
    for name in criteria_names:
        properties[f"{name}_result"] = {"type": "string"}
        properties[f"{name}_reason"] = {"type": "string"}
    return {"type": "object", "properties": properties, "required": ["query", "response"]}
