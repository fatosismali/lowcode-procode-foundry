"""Smoke tests for the "vf-triage-team" team orchestration."""

import pytest

from src import orchestrator


def test_build_workflow_importable():
    """The orchestrator module exposes build_workflow and run_team."""
    assert hasattr(orchestrator, "build_workflow")
    assert hasattr(orchestrator, "run_team")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_team_smoke():
    """End-to-end run. Requires FOUNDRY_PROJECT_ENDPOINT and `az login`.

    Marked integration so it is skipped by default:
        pytest -m integration
    """
    result = await orchestrator.run_team("Triage incident INC-4291, apply the corrective action, then notify affected customers.")
    assert isinstance(result, str)