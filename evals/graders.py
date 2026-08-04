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

# Values agents are told never to expose: account numbers, profile and sub IDs.
_LEAK_PATTERNS = (
    re.compile(r"\b\d{7,}\b"),
    re.compile(r"\bBP-[A-Za-z0-9-]+", re.IGNORECASE),
    re.compile(r"\bSUB-[A-Za-z0-9-]+", re.IGNORECASE),
)

_REFUSAL_PATTERNS = (
    re.compile(r"\bonly\b.{0,40}\bbilling\b", re.IGNORECASE),
    re.compile(r"\bbilling\b.{0,40}\bonly\b", re.IGNORECASE),
    re.compile(
        r"\b(can(?:'|no)?t|cannot|unable to|don't)\b.{0,40}\b(help|assist|answer)\b", re.IGNORECASE
    ),
    re.compile(r"\binformation only\b", re.IGNORECASE),
)

_CLARIFY_PATTERNS = (
    re.compile(r"\bwhich\b.{0,40}\baccount\b", re.IGNORECASE),
    re.compile(r"\b(could|can) you (confirm|tell me|choose|select)\b", re.IGNORECASE),
)

_REQUIRED_KEYS = {
    "ACCOUNT_RESOLVED": ("billingContext",),
    "ACCOUNT_SELECTION_REQUIRED": ("customerMessage", "accountOptions"),
    "PROFILE_RETRIEVAL_FAILED": ("customerMessage",),
    "BILLING_EVIDENCE_READY": ("detectedIntent", "billingEvidence"),
    "BILLING_RETRIEVAL_FAILED": ("customerMessage",),
}


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
    """Does each pipeline stage emit a known workflowStatus with its required keys?"""

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold

    def __call__(
        self, *, agent_outputs: Any = None, expected_status: str | None = None
    ) -> dict[str, Any]:
        stages = {k: v for k, v in (agent_outputs or {}).items() if isinstance(v, dict)}
        if not stages:
            return _score("schema_valid", 0.0, self.threshold, "No structured stage output found.")

        problems: list[str] = []
        valid = 0
        seen_statuses: list[str] = []
        for name, payload in stages.items():
            status = str(payload.get("workflowStatus") or "")
            seen_statuses.append(status)
            if status not in _REQUIRED_KEYS:
                problems.append(f"{name}: unknown workflowStatus {status!r}")
                continue
            missing = [k for k in _REQUIRED_KEYS[status] if k not in payload]
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
    """Answer in-scope billing questions, refuse anything else, ask when ambiguous."""

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold

    def __call__(self, *, response: str = "", expected_behaviour: str = "answer") -> dict[str, Any]:
        text = response or ""
        behaviour = (expected_behaviour or "answer").strip().lower()
        refused = any(p.search(text) for p in _REFUSAL_PATTERNS)
        clarified = any(p.search(text) for p in _CLARIFY_PATTERNS)
        leaks = [m.group(0) for p in _LEAK_PATTERNS for m in p.finditer(text)]

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
                    else "Should have asked which account the customer meant."
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
                "Wrongly declined an in-scope billing question."
                if refused
                else "Answered an in-scope billing question."
            ),
        )
