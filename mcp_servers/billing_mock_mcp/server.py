"""
Billing Mock MCP Server
=======================

A Model Context Protocol (MCP) server that mocks the Vodafone care-billing
APIs an AI agent invokes during a billing conversation. It returns canned
responses shaped exactly like the upstream `/care-billing/v2/...` calls found in
`data/extracted_billing_actions.json`, so a Foundry agent can be built and tested
end to end without the real backend.

Tools exposed to the agent:
  - get_billing_profiles      (upstream: getBillingProfiles)
  - get_month_bill_summary    (upstream: getMonthBillSummary)
  - get_previous_bills        (upstream: getPreviousBills)
  - get_subscription_details  (upstream: getSubscriptionDetails)

Every response uses the envelope the workflow expects:
    { "status": { "httpStatus": 200 }, "output": { ... } }

Run (remote / streamable HTTP — use this from a Foundry hosted agent):
    python server.py                      # serves http://localhost:8000/mcp

Run (local stdio — for MCP Inspector / desktop clients):
    MCP_TRANSPORT=stdio python server.py

Quick self-test (no transport):
    python server.py selftest
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP

FIXTURES_PATH = Path(__file__).parent / "mock_data" / "billing_fixtures.json"
_FIXTURES: dict[str, Any] = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))

HOST = os.getenv("MCP_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_PORT", "8000"))

mcp = FastMCP("billing-mock", host=HOST, port=PORT, stateless_http=True)


def _forced_scenario(tool: str, requested: str) -> str:
    """Allow the scenario to be forced server-side, overriding the caller.

    Precedence (highest first):
      1. Per-tool env var, e.g. MOCK_SCENARIO_GET_BILLING_PROFILES=multi_account
      2. Global env var, MOCK_SCENARIO=multi_account (applies to every tool)
      3. The scenario the caller/agent passed

    This is how you force a scenario when the LLM keeps omitting the argument.
    """
    return (
        os.getenv(f"MOCK_SCENARIO_{tool.upper()}")
        or os.getenv("MOCK_SCENARIO")
        or requested
    )


def _respond(tool: str, scenario: str, echo: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a deep copy of the fixture for a tool/scenario, with request echo.

    The effective scenario may be overridden server-side (see `_forced_scenario`).
    Falls back to the first available scenario if the requested one is unknown,
    so the mock never hard-fails on an unexpected scenario name.
    """
    requested = scenario
    scenario = _forced_scenario(tool, scenario)
    scenarios = _FIXTURES.get(tool, {})
    body = scenarios.get(scenario)
    if body is None:
        # graceful fallback to the first defined scenario
        first_key = next(iter(scenarios), None)
        body = scenarios.get(first_key, {"status": {"httpStatus": 404}, "output": {}})
    result = copy.deepcopy(body)
    result["_mock"] = {
        "tool": tool,
        "scenario": scenario,
        "requested_scenario": requested,
        "forced": scenario != requested,
        "request": echo or {},
    }
    return result


@mcp.tool()
def get_billing_profiles(
    msisdn: Annotated[str, "Customer mobile number (MSISDN), e.g. 447700900123"],
    account_no: Annotated[str, "Billing account number (optional)"] = "",
    scenario: Annotated[
        str,
        "Mock scenario: 'single_account' (one billing profile), 'multi_account' "
        "(more than one), or 'no_response' (backend failure).",
    ] = "single_account",
) -> dict[str, Any]:
    """Mock of `getBillingProfiles`. Returns the customer's billing profile list
    so the agent can decide between a single-account and multi-account journey."""
    return _respond(
        "get_billing_profiles",
        scenario,
        {"msisdn": msisdn, "accountNo": account_no},
    )


@mcp.tool()
def get_month_bill_summary(
    msisdn: Annotated[str, "Customer mobile number (MSISDN)"],
    account_no: Annotated[str, "Billing account number (optional)"] = "",
    month: Annotated[str, "Bill month as YYYY-MM, e.g. 2026-07 (optional)"] = "",
    scenario: Annotated[
        str,
        "Mock scenario: 'paid', 'pending', 'unpaid', or 'first_bill'.",
    ] = "paid",
) -> dict[str, Any]:
    """Mock of `getMonthBillSummary`. Returns the monthly bill summary — total,
    status, date range, in-plan vs out-of-plan charges, and payment message."""
    return _respond(
        "get_month_bill_summary",
        scenario,
        {"msisdn": msisdn, "accountNo": account_no, "month": month},
    )


@mcp.tool()
def get_previous_bills(
    msisdn: Annotated[str, "Customer mobile number (MSISDN)"],
    account_no: Annotated[str, "Billing account number (optional)"] = "",
    month: Annotated[str, "Reference month as YYYY-MM (optional)"] = "",
    scenario: Annotated[str, "Mock scenario: 'default'."] = "default",
) -> dict[str, Any]:
    """Mock of `getPreviousBills`. Returns a short history of previous bill
    summaries and the subscriptions billed in that period."""
    return _respond(
        "get_previous_bills",
        scenario,
        {"msisdn": msisdn, "accountNo": account_no, "month": month},
    )


@mcp.tool()
def get_subscription_details(
    msisdn: Annotated[str, "Customer mobile number (MSISDN)"],
    account_no: Annotated[str, "Billing account number (optional)"] = "",
    scenario: Annotated[str, "Mock scenario: 'default'."] = "default",
) -> dict[str, Any]:
    """Mock of `getSubscriptionDetails`. Returns per-subscription plan, allowances,
    add-ons, and out-of-plan charges for the account."""
    return _respond(
        "get_subscription_details",
        scenario,
        {"msisdn": msisdn, "accountNo": account_no},
    )


def _selftest() -> None:
    """Print one sample response per tool/scenario without starting a server."""
    samples = [
        ("get_billing_profiles", get_billing_profiles("447700900123", scenario="single_account")),
        ("get_billing_profiles/multi", get_billing_profiles("447700900123", scenario="multi_account")),
        ("get_month_bill_summary/paid", get_month_bill_summary("447700900123", scenario="paid")),
        ("get_month_bill_summary/unpaid", get_month_bill_summary("447700900123", scenario="unpaid")),
        ("get_previous_bills", get_previous_bills("447700900123")),
        ("get_subscription_details", get_subscription_details("447700900123")),
    ]
    for label, resp in samples:
        print(f"\n===== {label} =====")
        print(json.dumps(resp, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        _selftest()
    else:
        transport = os.getenv("MCP_TRANSPORT", "streamable-http")
        mcp.run(transport=transport)
