"""Score the billing team locally, then publish the results to Foundry.

    python -m evals.run_evals

Runs the team, scores every row on this machine with the deterministic graders
and the azure-ai-evaluation judges, prints the answer immediately, then
publishes one evaluation to Foundry for anyone else to review. Exits non-zero
if the quality gate fails.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import yaml

from .config import DATASETS_DIR, REPORTS_DIR, THRESHOLDS_FILE, EvalConfig
from .evaluators import (
    QUALITY_JUDGES,
    SAFETY_JUDGES,
    build_local_judges,
    item_schema,
    judge_inputs,
    publish_criteria,
    read_verdict,
)
from .graders import (
    FactRecallEvaluator,
    IntentMatchEvaluator,
    ScopeAdherenceEvaluator,
    WorkflowSchemaEvaluator,
)
from .target import TeamTarget

# Fatos's spec: one set for the intent classifier, one for the billing agent,
# one for the system as a whole including topic refusal.
SETS = {
    "intent_classifier": "intent_classifier.jsonl",
    "billing_agent": "billing_agent.jsonl",
    "system_e2e": "system_e2e.jsonl",
}

GRADERS = {
    "intent_match": IntentMatchEvaluator,
    "schema_valid": WorkflowSchemaEvaluator,
    "fact_recall": FactRecallEvaluator,
    "scope_adherence": ScopeAdherenceEvaluator,
}

# How each grader gets its inputs from the dataset row and the team output.
GRADER_INPUTS = {
    "intent_match": lambda row, out: {
        "detected_intent": out["detected_intent"],
        "expected_intent": row.get("expected_intent") or [],
    },
    "schema_valid": lambda row, out: {
        "agent_outputs": out["agent_outputs"],
        "expected_status": row.get("expected_status") or None,
    },
    "fact_recall": lambda row, out: {
        "response": out["response"],
        "required_facts": row.get("required_facts") or [],
        "forbidden_facts": row.get("forbidden_facts") or [],
    },
    "scope_adherence": lambda row, out: {
        "response": out["response"],
        "expected_behaviour": row.get("expected_behaviour") or "answer",
    },
}


def load_thresholds() -> dict[str, float]:
    if not THRESHOLDS_FILE.is_file():
        return {}
    loaded = yaml.safe_load(THRESHOLDS_FILE.read_text(encoding="utf-8")) or {}
    return loaded.get("criteria", {})


def load_rows(dataset: str, limit: int | None = None) -> list[dict[str, Any]]:
    path = DATASETS_DIR / dataset
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in (lines[:limit] if limit else lines)]


def build_item(row: dict[str, Any], out: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id", "")),
        "category": str(row.get("category", "")),
        "query": row["query"],
        "response": out["response"],
        "context": out["transcript"],
        "tool_calls": out["tool_calls"],
        "tool_definitions": out["tool_definitions"],
        "query_messages": out["query_messages"],
        "response_messages": out["response_messages"],
        "expected_intent": ", ".join(row.get("expected_intent") or []),
        "detected_intent": ", ".join(out["detected_intent"]),
        "expected_behaviour": str(row.get("expected_behaviour") or ""),
        "expected_status": str(row.get("expected_status") or ""),
        "workflow_status": out["workflow_status"],
        "required_facts": ", ".join(str(f) for f in row.get("required_facts") or []),
        "forbidden_facts": ", ".join(str(f) for f in row.get("forbidden_facts") or []),
        "error": out["error"],
    }


def judge_items(items: list[dict[str, Any]], judges: dict[str, Any], workers: int) -> None:
    """A full run is hundreds of judge calls, so they go out in parallel."""

    def run(task):
        item, name, judge = task
        try:
            return item, name, read_verdict(name, judge(**judge_inputs(name, item)))
        except Exception as exc:  # one judge must not sink the whole run
            return item, name, ("error", f"{type(exc).__name__}: {exc}")

    tasks = [(item, name, judge) for item in items for name, judge in judges.items()]
    print(f"  judging {len(tasks)} row/criterion pairs across {workers} workers...")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for item, name, (label, reason) in pool.map(run, tasks):
            item[f"{name}_result"] = label
            item[f"{name}_reason"] = reason


def score_locally(
    rows: list[dict[str, Any]],
    target: TeamTarget,
    judges: dict[str, Any],
    workers: int = 8,
) -> list[dict[str, Any]]:
    graders = {name: cls() for name, cls in GRADERS.items()}
    items: list[dict[str, Any]] = []

    print(f"  running the team over {len(rows)} rows...")
    for row in rows:
        out = target(row["query"], row.get("account_reference"))
        item = build_item(row, out)
        for name, grader in graders.items():
            scores = grader(**GRADER_INPUTS[name](row, out))
            item[f"{name}_result"] = str(scores.get(f"{name}_result", "not applicable"))
            item[f"{name}_reason"] = str(scores.get(f"{name}_reason", ""))
        if out["error"]:
            print(f"    ! {row.get('id', '')}: {out['error']}")
        items.append(item)

    if judges:
        judge_items(items, judges, workers)

    criteria = [*graders, *judges]
    for item in items:
        failed = [n for n in criteria if item[f"{n}_result"] in ("fail", "error")]
        print(f"    {item['id']:<6} {'PASS' if not failed else 'FAIL ' + ','.join(failed)}")

    return items


def pass_rates(items: list[dict[str, Any]], criteria: list[str]) -> dict[str, float | None]:
    rates: dict[str, float | None] = {}
    for name in criteria:
        counted = [i[f"{name}_result"] for i in items if i[f"{name}_result"] != "not applicable"]
        rates[name] = (counted.count("pass") / len(counted)) if counted else None
    return rates


def check_gate(rates: dict[str, float | None], thresholds: dict[str, float]) -> list[dict]:
    checks = []
    for name, minimum in (thresholds or {}).items():
        rate = rates.get(name)
        checks.append(
            {
                "criterion": name,
                "pass_rate": rate,
                "threshold": minimum,
                "passed": rate is not None and rate >= minimum,
                "note": "" if rate is not None else "no applicable rows",
            }
        )
    return checks


def publish(
    config: EvalConfig, items: list[dict[str, Any]], criteria: list[str], set_name: str
) -> Any:
    from azure.ai.projects import AIProjectClient  # noqa: PLC0415
    from azure.identity import DefaultAzureCredential  # noqa: PLC0415
    from openai.types.eval_create_params import DataSourceConfigCustom  # noqa: PLC0415
    from openai.types.evals.create_eval_jsonl_run_data_source_param import (  # noqa: PLC0415
        CreateEvalJSONLRunDataSourceParam,
        SourceFileContent,
        SourceFileContentContent,
    )

    # The judges already ran locally, so only the string columns are published.
    payload = [{k: v for k, v in item.items() if not isinstance(v, (list, dict))} for item in items]
    stamp = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M}"

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=config.foundry_project_endpoint, credential=credential) as project,
        project.get_openai_client() as client,
    ):
        evaluation = client.evals.create(
            name=f"vf-billing {set_name} {stamp}",
            data_source_config=DataSourceConfigCustom(
                type="custom", item_schema=item_schema(criteria)
            ),
            testing_criteria=publish_criteria(criteria),
        )
        run = client.evals.runs.create(
            eval_id=evaluation.id,
            name=f"local results {stamp}",
            data_source=CreateEvalJSONLRunDataSourceParam(
                type="jsonl",
                source=SourceFileContent(
                    type="file_content",
                    content=[SourceFileContentContent(item=item) for item in payload],
                ),
            ),
        )
        while run.status not in ("completed", "failed", "canceled"):
            time.sleep(3)
            run = client.evals.runs.retrieve(run_id=run.id, eval_id=evaluation.id)
        return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Vodafone billing evaluations.")
    parser.add_argument(
        "--set",
        default="all",
        choices=[*SETS, "all"],
        help="Which evaluation set to run.",
    )
    parser.add_argument("--team", help="Path to the generated team directory.")
    parser.add_argument("--project-endpoint", help="Foundry project endpoint for this team.")
    parser.add_argument("--judge-deployment", help="Model deployment used as LLM judge.")
    parser.add_argument(
        "--no-judge", action="store_true", help="Deterministic graders only, no LLM judges."
    )
    parser.add_argument(
        "--no-safety", action="store_true", help="Keep the quality judges but drop the safety ones."
    )
    parser.add_argument(
        "--no-publish", action="store_true", help="Score locally only, do not send to Foundry."
    )
    parser.add_argument("--limit", type=int, help="Only run the first N rows.")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Parallel judge calls. Lower it if the judge deployment rate limits.",
    )
    parser.add_argument("--ignore-thresholds", action="store_true", help="Always exit 0.")
    args = parser.parse_args(argv)

    config = EvalConfig.from_env(
        project_endpoint=args.project_endpoint,
        team_dir=args.team,
        judge_deployment=args.judge_deployment,
        use_judges=not args.no_judge,
        use_safety=not args.no_safety,
    )

    judge_names: list[str] = []
    if config.use_judges:
        judge_names = list(QUALITY_JUDGES)
        if config.use_safety:
            judge_names += list(SAFETY_JUDGES)

    rows = load_rows(args.dataset, args.limit)
    print(f"Team:    {config.team_dir}")
    print(f"Project: {config.foundry_project_endpoint}")
    print(f"Judge:   {config.judge_deployment if config.use_judges else 'disabled'}")

    target = TeamTarget(config)
    judges = build_local_judges(config, judge_names) if judge_names else {}
    criteria = [*GRADERS, *judges]
    thresholds = load_thresholds()
    set_names = list(SETS) if args.set == "all" else [args.set]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_endpoint": config.foundry_project_endpoint,
        "team_dir": str(config.team_dir),
        "sets": {},
    }
    failures = 0

    for set_name in set_names:
        rows = load_rows(SETS[set_name], args.limit)
        print(f"\n===== {set_name} ({len(rows)} rows, {len(criteria)} criteria) =====")
        items = score_locally(rows, target, judges, args.concurrency)
        rates = pass_rates(items, criteria)

        print(f"\n  local results for {set_name}:")
        for name in criteria:
            rate = rates[name]
            print(f"    {name:<20} {'n/a' if rate is None else f'{rate:.0%}'}")

        checks = check_gate(rates, thresholds)
        print("\n  gate:")
        for check in checks:
            rate = "n/a" if check["pass_rate"] is None else f"{check['pass_rate']:.0%}"
            status = "PASS" if check["passed"] else "FAIL"
            print(f"    [{status}] {check['criterion']}: {rate} (min {check['threshold']:.0%})")
            if not check["passed"]:
                failures += 1

        (REPORTS_DIR / f"{set_name}.jsonl").write_text(
            "\n".join(json.dumps(i, default=str) for i in items) + "\n", encoding="utf-8"
        )

        report_url = None
        if not args.no_publish:
            run = publish(config, items, criteria, set_name)
            report_url = getattr(run, "report_url", None)
            print(f"\n  published: {run.status}  {report_url}")

        summary["sets"][set_name] = {
            "rows": len(items),
            "pass_rates": rates,
            "checks": checks,
            "report_url": report_url,
        }

    (REPORTS_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nPer-set results and summary written to {REPORTS_DIR}")

    if failures and not args.ignore_thresholds:
        print(f"Quality gate FAILED: {failures} criteria below threshold across all sets.")
        return 1
    print("Quality gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
