"""
Tool implementations for "vf-billing-team".

Every function tool declared across the team's agent YAMLs has an implementation
here. The orchestrator wires them to agents by tool name via TOOL_REGISTRY. MCP
/ knowledge-base tools are attached automatically from the YAML and need no
code here.

The fixtures below are deterministic mocks for demo runs — swap them with real
billing platform calls when you're ready.
"""

import logging
from typing import Annotated, Any

from agent_framework import tool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock backend — deterministic fixtures.
#
# Two customer billing profiles are seeded so both the single-account and
# multi-account paths in Agent 1 (Profile Resolver) can be exercised:
#
#   BP-001  Consumer  J. Smith            — pending current bill, plan + add-on,
#                                            history of paid previous bills.
#   BP-002  Business  J. Smith (Business) — first bill (extended period),
#                                            no previous bills, plan only.
#
# The profile resolver decides which one to select; the investigation agent
# then calls get_billing_data(billing_profile_id, data_types=[...]).
# ---------------------------------------------------------------------------

_PROFILES: list[dict[str, Any]] = [
    {
        "accountNo": "9876546789",
        "billingProfileId": "BP-001",
        "accountName": "J. Smith",
        "accountType": "consumer",
        "currency": "GBP",
        "billingAddress": "12 High Street, Manchester M1 2AB, UK",
    },
    {
        "accountNo": "1122334321",
        "billingProfileId": "BP-002",
        "accountName": "J. Smith (Business)",
        "accountType": "business",
        "currency": "GBP",
        "billingAddress": "3 Market Square, Manchester M2 3CD, UK",
    },
]


_CURRENT_BILL: dict[str, dict[str, Any]] = {
    "BP-001": {
        "billType": "latest",
        "billStatus": "Pending",
        "billMonth": "July",
        "billDateRange": "1 July to 31 July 2026",
        "totalLabel": "Total due",
        "inPlanAmount": "£38.00",
        "outOfPlanAmount": "£7.20",
        "totalAmount": "£45.20",
        "numericTotalAmount": 45.20,
        "paymentMessage": "Your Direct Debit is scheduled for 3 August 2026.",
        "isFirstBill": False,
    },
    "BP-002": {
        "billType": "latest",
        "billStatus": "Pending",
        "billMonth": "July",
        "billDateRange": "12 June to 31 July 2026",
        "totalLabel": "Total due",
        "inPlanAmount": "£45.00",
        "outOfPlanAmount": "£16.30",
        "totalAmount": "£61.30",
        "numericTotalAmount": 61.30,
        "paymentMessage": "Your Direct Debit is scheduled for 3 August 2026.",
        "isFirstBill": True,
    },
}


_PREVIOUS_BILLS: dict[str, list[dict[str, Any]]] = {
    "BP-001": [
        {"month": "June",  "billStatus": "Paid", "totalAmount": "£41.10", "numericTotalAmount": 41.10},
        {"month": "May",   "billStatus": "Paid", "totalAmount": "£39.75", "numericTotalAmount": 39.75},
        {"month": "April", "billStatus": "Paid", "totalAmount": "£38.00", "numericTotalAmount": 38.00},
    ],
    # BP-002 is a first-bill account: no history yet.
    "BP-002": [],
}


_SUBSCRIPTIONS: dict[str, list[dict[str, Any]]] = {
    "BP-001": [
        {
            "subscriptionId": "SUB-1001",
            "maskedMobileNumber": "6789",
            "planName": "Unlimited Max Airtime",
            "planType": "consumer_airtime",
            "monthlyCharge": "£38.00",
            "allowances": {
                "data": "unlimited",
                "minutes": "unlimited",
                "texts": "unlimited",
            },
            "addOns": [
                {"name": "Roam Further Passport", "charge": "£0.00"},
            ],
            "outOfPlanCharges": [
                {"description": "International calls (Spain)", "charge": "£4.50"},
                {"description": "Premium-rate SMS",             "charge": "£2.70"},
            ],
        },
    ],
    "BP-002": [
        {
            "subscriptionId": "SUB-2001",
            "maskedMobileNumber": "4321",
            "planName": "Business Unlimited",
            "planType": "business_airtime",
            "monthlyCharge": "£45.00",
            "allowances": {
                "data": "unlimited",
                "minutes": "unlimited",
                "texts": "unlimited",
            },
            "addOns": [],
            "outOfPlanCharges": [
                {"description": "Prorated first-period line rental", "charge": "£16.30"},
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------

def _match_profile(reference: "str | None") -> "dict[str, Any] | None":
    """Best-effort match of a customer selection to one of the seeded profiles."""
    if not reference:
        return None
    ref = reference.strip().lower()
    if not ref:
        return None
    for profile in _PROFILES:
        acct_last4 = profile["accountNo"][-4:]
        haystacks = {
            profile["billingProfileId"].lower(),
            profile["accountName"].lower(),
            profile["accountType"].lower(),
            acct_last4,
            f"acct-ending-{acct_last4}",
            f"account ending in {acct_last4}",
        }
        if profile["accountType"] == "consumer":
            haystacks.update({"personal", "personal account"})
        if profile["accountType"] == "business":
            haystacks.update({"business", "business account"})
        if ref in haystacks or any(ref in h for h in haystacks):
            return profile
    return None


# ---------------------------------------------------------------------------
# Tools exposed to the agents.
# ---------------------------------------------------------------------------

@tool
async def get_billing_profiles(
    selectedAccountReference: Annotated[
        str,
        (
            "Optional. A stable account reference chosen by the customer in a "
            "previous turn (e.g. 'personal', 'business', 'acct-ending-4321', "
            "or a full account name). Pass an empty string when the customer "
            "has not yet chosen an account."
        ),
    ],
) -> dict[str, Any]:
    """Retrieve the customer's available billing profiles.

    Returns a list of accounts with ``accountNo``, ``billingProfileId``,
    ``accountName``, ``accountType``, ``currency`` and ``billingAddress``,
    plus a ``status`` object containing ``httpStatus``. When
    ``selectedAccountReference`` matches a single profile the response also
    includes ``matchedProfileId`` as a hint for the resolver agent.
    """
    matched = _match_profile(selectedAccountReference)
    logger.info(
        "get_billing_profiles(ref=%r) -> %d profile(s)%s",
        selectedAccountReference, len(_PROFILES),
        f", matched={matched['billingProfileId']}" if matched else "",
    )
    response: dict[str, Any] = {
        "status": {"httpStatus": 200},
        "profiles": _PROFILES,
    }
    if matched is not None:
        response["matchedProfileId"] = matched["billingProfileId"]
    return response


@tool
async def get_billing_data(
    billing_profile_id: Annotated[
        str,
        "Internal billing profile ID from the Profile Resolver (e.g. 'BP-001').",
    ],
    data_types: Annotated[
        list[str],
        (
            "One or more billing data sources to retrieve. Each entry must be "
            "one of: 'current_bill', 'previous_bills', 'subscriptions'."
        ),
    ],
) -> dict[str, Any]:
    """Consolidated billing data retrieval.

    Fetches any combination of the latest bill summary, previous bill history
    and subscription / plan details for a given billing profile in a single
    call. The response is keyed by each requested data type and always
    includes a per-source ``status`` object with ``httpStatus``.

    Behaviour:
      - Unknown ``billing_profile_id`` -> every requested source returns
        ``httpStatus: 404`` and ``available: false``.
      - Empty subscriptions / previous_bills for a known profile ->
        ``httpStatus: 200`` with an empty ``items`` list (still
        ``available: true``).
      - Unknown ``data_types`` entries are ignored.
    """
    valid_sources = {"current_bill", "previous_bills", "subscriptions"}
    requested = [d for d in (data_types or []) if d in valid_sources]
    logger.info(
        "get_billing_data(profile=%s, data_types=%s)",
        billing_profile_id, requested,
    )

    result: dict[str, Any] = {}
    profile_known = billing_profile_id in _CURRENT_BILL

    if "current_bill" in requested:
        if profile_known:
            result["current_bill"] = {
                "status": {"httpStatus": 200},
                "available": True,
                **_CURRENT_BILL[billing_profile_id],
            }
        else:
            result["current_bill"] = {
                "status": {"httpStatus": 404, "reason": "profile not found"},
                "available": False,
            }

    if "previous_bills" in requested:
        if profile_known:
            result["previous_bills"] = {
                "status": {"httpStatus": 200},
                "available": True,
                "items": _PREVIOUS_BILLS.get(billing_profile_id, []),
            }
        else:
            result["previous_bills"] = {
                "status": {"httpStatus": 404, "reason": "profile not found"},
                "available": False,
                "items": [],
            }

    if "subscriptions" in requested:
        if profile_known:
            result["subscriptions"] = {
                "status": {"httpStatus": 200},
                "available": True,
                "items": _SUBSCRIPTIONS.get(billing_profile_id, []),
            }
        else:
            result["subscriptions"] = {
                "status": {"httpStatus": 404, "reason": "profile not found"},
                "available": False,
                "items": [],
            }

    return result


# Maps the tool name (as declared in the agent YAML) to its implementation.
# The orchestrator looks up each agent's function tools here at build time.
TOOL_REGISTRY: dict[str, Any] = {
    "get_billing_profiles": get_billing_profiles,
    "get_billing_data": get_billing_data,
}
