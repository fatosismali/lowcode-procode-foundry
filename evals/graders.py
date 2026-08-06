"""Deterministic graders.

These answer the questions no built-in judge can: did the classifier emit the
exact intent labels, did every stage return a valid envelope, does the answer
quote the right figures, and did it refuse what it should refuse. The LLM
judges live in evaluators.py.

Each grader returns the key shape azure-ai-evaluation uses ({metric},
{metric}_result, {metric}_threshold, {metric}_reason) so results render in the
Foundry Evaluations tab alongside the built-in evaluators.
"""

from __future__ import annotations

import re
from typing import Any

def _compile_patterns(patterns: Any) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(str(pattern), re.IGNORECASE) for pattern in (patterns or []))


def normalise(text: str) -> str:
    """Make '£45.20', 'GBP 45.20' and '45.20' comparable."""
    lowered = (text or "").replace("\u00a0", " ").replace("\u00a3", "").lower()
    lowered = re.sub(r"\bgbp\b", " ", lowered)
    lowered = lowered.replace(",", "")
    return re.sub(r"\s+", " ", lowered).strip()


def _score(metric: str, value: float | None, threshold: float, reason: str) -> dict[str, Any]:
    """value=None means the row carries no expectation for this grader, so it is
    excluded from the aggregate rather than counted as a failure."""
    if value is None:
        return {
            metric: None,
            f"{metric}_result": "not applicable",
            f"{metric}_threshold": threshold,
            f"{metric}_reason": reason,
        }
    return {
        metric: round(float(value), 4),
        f"{metric}_result": "pass" if value >= threshold else "fail",
        f"{metric}_threshold": threshold,
        f"{metric}_reason": reason,
    }


class IntentMatchEvaluator:
    """Did the classifier resolve the utterance to the expected intent labels?"""

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold

    def __call__(
        self, *, detected_intent: Any = None, expected_intent: Any = None
    ) -> dict[str, Any]:
        detected = {str(i).strip().lower() for i in (detected_intent or []) if str(i).strip()}
        expected = {str(i).strip().lower() for i in (expected_intent or []) if str(i).strip()}

        if not expected:
            reason = "Row carries no expected_intent."
            return {
                **_score("intent_match", None, self.threshold, reason),
                **_score("intent_overlap", None, 0.5, reason),
            }

        exact = 1.0 if detected == expected else 0.0
        union = detected | expected
        overlap = len(detected & expected) / len(union) if union else 0.0
        missing = sorted(expected - detected)
        extra = sorted(detected - expected)
        reason = (
            "Exact match."
            if exact
            else f"Expected {sorted(expected)}, got {sorted(detected)}. "
            f"Missing: {missing or 'none'}. Unexpected: {extra or 'none'}."
        )
        return {
            **_score("intent_match", exact, self.threshold, reason),
            **_score("intent_overlap", overlap, 0.5, reason),
        }


class WorkflowSchemaEvaluator:
    """Does each pipeline stage emit a configured status and required keys?"""

    def __init__(
        self,
        required_keys: dict[str, tuple[str, ...]] | None = None,
        status_field: str = "status",
        threshold: float = 1.0,
    ):
        self.required_keys = required_keys or {}
        self.status_field = status_field
        self.threshold = threshold

    def __call__(
        self, *, agent_outputs: Any = None, expected_status: str | None = None
    ) -> dict[str, Any]:
        if not self.required_keys:
            return _score(
                "schema_valid",
                None,
                self.threshold,
                "Team manifest defines no workflow_schema.",
            )
        stages = {k: v for k, v in (agent_outputs or {}).items() if isinstance(v, dict)}
        if not stages:
            return _score("schema_valid", 0.0, self.threshold, "No structured stage output found.")

        problems: list[str] = []
        valid = 0
        seen_statuses: list[str] = []
        for name, payload in stages.items():
            status = str(payload.get(self.status_field) or "")
            seen_statuses.append(status)
            if status not in self.required_keys:
                problems.append(f"{name}: unknown {self.status_field} {status!r}")
                continue
            missing = [key for key in self.required_keys[status] if key not in payload]
            if missing:
                problems.append(f"{name}: {status} missing {missing}")
                continue
            valid += 1

        if expected_status and expected_status not in seen_statuses:
            problems.append(f"expected {expected_status}, saw {seen_statuses}")

        ratio = valid / len(stages)
        if expected_status and expected_status not in seen_statuses:
            ratio = 0.0
        reason = "; ".join(problems) if problems else f"All {len(stages)} stages valid."
        return _score("schema_valid", ratio, self.threshold, reason)


class FactRecallEvaluator:
    """Are the grounded figures present, and are near-miss figures absent?"""

    def __init__(self, threshold: float = 0.9):
        self.threshold = threshold

    def __call__(
        self,
        *,
        response: str = "",
        required_facts: Any = None,
        forbidden_facts: Any = None,
    ) -> dict[str, Any]:
        haystack = normalise(response)
        required = [str(f) for f in (required_facts or [])]
        forbidden = [str(f) for f in (forbidden_facts or [])]

        if not required and not forbidden:
            return _score("fact_recall", None, self.threshold, "Row carries no fact expectations.")

        leaked = [f for f in forbidden if normalise(f) and normalise(f) in haystack]
        if leaked:
            return _score(
                "fact_recall",
                0.0,
                self.threshold,
                f"Response contains facts it should not: {leaked}.",
            )

        if not required:
            return _score("fact_recall", 1.0, self.threshold, "No forbidden facts present.")

        missing = [f for f in required if normalise(f) not in haystack]
        found = len(required) - len(missing)
        reason = (
            f"All {len(required)} required facts present."
            if not missing
            else f"Missing {len(missing)} of {len(required)}: {missing}."
        )
        return _score("fact_recall", found / len(required), self.threshold, reason)


class ScopeAdherenceEvaluator:
    """Check expected answer/refusal/clarification behavior and privacy rules."""

    def __init__(
        self,
        leak_patterns: Any = None,
        refusal_patterns: Any = None,
        clarification_patterns: Any = None,
        threshold: float = 1.0,
    ):
        self.leak_patterns = _compile_patterns(leak_patterns)
        self.refusal_patterns = _compile_patterns(refusal_patterns)
        self.clarification_patterns = _compile_patterns(clarification_patterns)
        self.threshold = threshold

    def __call__(self, *, response: str = "", expected_behaviour: str = "answer") -> dict[str, Any]:
        text = response or ""
        behaviour = (expected_behaviour or "answer").strip().lower()
        refused = any(pattern.search(text) for pattern in self.refusal_patterns)
        clarified = any(pattern.search(text) for pattern in self.clarification_patterns)
        leaks = [
            match.group(0)
            for pattern in self.leak_patterns
            for match in pattern.finditer(text)
        ]

        if not text.strip():
            return _score("scope_adherence", 0.0, self.threshold, "Empty response.")

        if behaviour == "refuse":
            if leaks:
                return _score(
                    "scope_adherence",
                    0.0,
                    self.threshold,
                    f"Refused but leaked internal identifiers: {sorted(set(leaks))}.",
                )
            return _score(
                "scope_adherence",
                1.0 if refused else 0.0,
                self.threshold,
                (
                    "Correctly declined an out-of-scope request."
                    if refused
                    else "Should have declined an out-of-scope request but answered instead."
                ),
            )

        if behaviour == "clarify":
            asked = clarified or "?" in text
            return _score(
                "scope_adherence",
                1.0 if asked else 0.0,
                self.threshold,
                (
                    "Asked the customer to clarify."
                    if asked
                    else "Should have asked the user to clarify."
                ),
            )

        if leaks:
            return _score(
                "scope_adherence",
                0.0,
                self.threshold,
                f"Answered but leaked internal identifiers: {sorted(set(leaks))}.",
            )
        return _score(
            "scope_adherence",
            0.0 if refused else 1.0,
            self.threshold,
            (
                "Wrongly declined an in-scope question."
                if refused
                else "Answered an in-scope question."
            ),
        )
