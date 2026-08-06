"""
Tool implementations for "vf-triage-team".

Every function tool declared across the team's agent YAMLs has a stub here.
Implement the bodies — the orchestrator wires them to agents by tool name via
TOOL_REGISTRY. MCP / knowledge-base tools are attached automatically from the
YAML and need no code here.
"""

import logging
from typing import Annotated, Any

from agent_framework import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock backends (replace these dicts with real ITSM / RAN / CRM API calls).
# Seeded so INC-4291 -> site MAN-372 -> ran_congestion -> reroute_traffic.
# ---------------------------------------------------------------------------

_INCIDENTS: dict[str, dict[str, Any]] = {
    "INC-4291": {
        "site_id": "MAN-372",
        "summary": "Customers in Manchester city centre report slow data and dropped calls.",
    },
    "INC-5002": {
        "site_id": "LDN-118",
        "summary": "Intermittent total loss of service in central London.",
    },
}

# Root-cause rules the triage agent applies:
#   reachable=false            -> backhaul_outage
#   prb_utilisation > 0.85     -> ran_congestion
#   handover_failure_rate>0.10 -> neighbour_misconfig
#   otherwise                  -> no_fault
_TELEMETRY: dict[str, dict[str, Any]] = {
    "MAN-372": {"reachable": True, "prb_utilisation": 0.92, "handover_failure_rate": 0.04, "rrc_conn_users": 812},
    "LDN-118": {"reachable": False, "prb_utilisation": 0.10, "handover_failure_rate": 0.02, "rrc_conn_users": 0},
}

_CUSTOMER_IMPACT: dict[str, dict[str, int]] = {
    "MAN-372": {"gold": 120, "silver": 430, "bronze": 900},
    "LDN-118": {"gold": 60, "silver": 210, "bronze": 540},
}


def _total_impact(tiers: dict[str, int]) -> int:
    return sum(int(v) for v in tiers.values())


@tool
async def get_incident(
    incident_id: Annotated[str, "Incident ID, e.g. INC-4291"],
) -> dict[str, Any]:
    """Look up an ITSM incident by ID and return its site and summary."""
    incident = _INCIDENTS.get(
        incident_id,
        {"site_id": "UNKNOWN", "summary": f"No ITSM record found for {incident_id}."},
    )
    logger.info("get_incident(%s) -> site=%s", incident_id, incident["site_id"])
    return {
        "status": "ok",
        "incident_id": incident_id,
        "site_id": incident["site_id"],
        "summary": incident["summary"],
    }


@tool
async def fetch_telemetry(
    site_id: Annotated[str, "Cell site ID, e.g. MAN-372"],
) -> dict[str, Any]:
    """Fetch the latest RAN telemetry snapshot for a cell site."""
    telemetry = _TELEMETRY.get(
        site_id,
        {"reachable": True, "prb_utilisation": 0.20, "handover_failure_rate": 0.01, "rrc_conn_users": 100},
    )
    logger.info("fetch_telemetry(%s) -> %s", site_id, telemetry)
    return {"status": "ok", "site_id": site_id, **telemetry}


@tool
async def fetch_customer_impact(
    site_id: Annotated[str, "Cell site ID, e.g. MAN-372"],
) -> dict[str, Any]:
    """Return CRM impact (affected customers by tier) for a cell site."""
    tiers = _CUSTOMER_IMPACT.get(site_id, {"gold": 0, "silver": 0, "bronze": 0})
    total = _total_impact(tiers)
    logger.info("fetch_customer_impact(%s) -> total=%d", site_id, total)
    return {"status": "ok", "site_id": site_id, "affected_customers": total, "by_tier": tiers}


@tool
async def apply_change(
    incident_id: Annotated[str, "ITSM incident ID"],
    site_id: Annotated[str, "Cell site ID"],
    action: Annotated[str, "Corrective action to apply"],
    rationale: Annotated[str, "Reason for choosing this action"],
    approved: Annotated[bool, "Must be true to apply change"],
    approver: Annotated[str, "Approver identifier"],
) -> dict[str, Any]:
    """Apply a corrective change to the network. Refuses unless approved=true. Use this once you have decided the action."""
    if not approved:
        logger.warning("apply_change refused for %s: not approved", incident_id)
        return {"status": "refused", "applied": False, "reason": "approval required"}
    change_id = f"CHG-{abs(hash((incident_id, site_id, action))) % 100000:05d}"
    logger.info("apply_change(%s, %s, %s) approved by %s -> %s", incident_id, site_id, action, approver, change_id)
    return {
        "status": "applied",
        "applied": True,
        "change_id": change_id,
        "incident_id": incident_id,
        "site_id": site_id,
        "action": action,
        "rationale": rationale,
        "approver": approver,
    }


@tool
async def draft_notification(
    site_id: Annotated[str, "Cell site ID, e.g. MAN-372"],
    root_cause: Annotated[str, "Root cause identified by triage"],
    affected_customers: Annotated[int, "Number of affected customers"],
) -> dict[str, Any]:
    """Draft a short, plain-language customer notification for an incident."""
    friendly = {
        "ran_congestion": "high network demand in your area",
        "backhaul_outage": "a connection outage affecting your local mast",
        "neighbour_misconfig": "a configuration issue on a nearby mast",
        "no_fault": "a brief service check",
    }
    reason = friendly.get(root_cause, "a temporary network issue")
    message = (
        f"We're aware that some customers near site {site_id} are experiencing issues "
        f"due to {reason}. Our engineers have taken action to restore normal service. "
        f"Thank you for your patience."
    )
    logger.info("draft_notification(%s, %s) for %s customers", site_id, root_cause, affected_customers)
    return {
        "status": "ok",
        "site_id": site_id,
        "message": message,
        "root_cause": root_cause,
        "affected_customers": affected_customers,
    }


@tool
async def notify_customers(
    site_id: Annotated[str, "Cell site ID"],
    message: Annotated[str, "Notification body to send"],
    channel: Annotated[str, "Delivery channel"],
) -> dict[str, Any]:
    """Send a customer notification over the chosen channel."""
    recipients = _total_impact(_CUSTOMER_IMPACT.get(site_id, {}))
    logger.info("notify_customers(%s) via %s -> %d recipients", site_id, channel, recipients)
    return {
        "status": "sent",
        "sent": True,
        "site_id": site_id,
        "channel": channel,
        "recipients": recipients,
        "message_preview": message[:80],
    }

# Maps the tool name (as declared in the agent YAML) to its implementation.
# The orchestrator looks up each agent's function tools here at build time.
TOOL_REGISTRY: dict[str, Any] = {
    "get_incident": get_incident,
    "fetch_telemetry": fetch_telemetry,
    "fetch_customer_impact": fetch_customer_impact,
    "apply_change": apply_change,
    "draft_notification": draft_notification,
    "notify_customers": notify_customers,
}