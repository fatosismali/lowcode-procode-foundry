"""
Configuration for the "vf-triage-team" multi-agent team.

Values are read from environment variables (or a local .env file).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# Project root (one level above src/), where team.yaml and agents/ live.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_TEAM_YAML = str(_PROJECT_ROOT / "team.yaml")


@dataclass
class TeamConfig:
    """Runtime configuration for the team orchestration."""

    foundry_project_endpoint: str
    model: str = "gpt-5"
    log_level: str = "INFO"
    # Path to the team spec the orchestrator loads at runtime.
    team_yaml: str = field(default=_DEFAULT_TEAM_YAML)

    @classmethod
    def from_env(cls) -> "TeamConfig":
        """Load configuration from environment variables."""
        endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        if not endpoint:
            raise ValueError(
                "FOUNDRY_PROJECT_ENDPOINT is not set. Copy .env.example to .env "
                "and fill in your Foundry project endpoint."
            )
        return cls(
            foundry_project_endpoint=endpoint,
            model=os.environ.get("FOUNDRY_MODEL", cls.model),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            team_yaml=os.environ.get("TEAM_YAML", _DEFAULT_TEAM_YAML),
        )
