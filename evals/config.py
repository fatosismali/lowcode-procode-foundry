"""Configuration for the evaluation suite.

Each team on simulation day has its own Foundry project. Set
FOUNDRY_PROJECT_ENDPOINT in evals/.env (or pass --project-endpoint) and the
judge endpoint is derived from it unless overridden.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

EVALS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EVALS_ROOT.parent
DATASETS_DIR = EVALS_ROOT / "datasets"
REPORTS_DIR = EVALS_ROOT / "reports"
THRESHOLDS_FILE = EVALS_ROOT / "thresholds.yaml"

DEFAULT_TEAM_DIR = REPO_ROOT / "agent_teams" / "vf_billing_team"
DEFAULT_JUDGE_DEPLOYMENT = "gpt-5-mini"
DEFAULT_JUDGE_API_VERSION = "2024-10-21"

# Judge deployments whose names start with these need is_reasoning_model=True.
_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5")


def load_dotenv(path: Path | None = None) -> None:
    """Read KEY=VALUE lines into os.environ without adding a dependency."""
    env_file = path or (EVALS_ROOT / ".env")
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _derive_judge_endpoint(project_endpoint: str) -> str:
    """Strip /api/projects/<name> to leave the account endpoint."""
    parts = urlsplit(project_endpoint)
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}"


@dataclass
class EvalConfig:
    """Everything the runner needs to drive the team and the judges."""

    foundry_project_endpoint: str
    team_dir: Path = DEFAULT_TEAM_DIR
    judge_deployment: str = DEFAULT_JUDGE_DEPLOYMENT
    judge_endpoint: str = ""
    judge_api_version: str = DEFAULT_JUDGE_API_VERSION
    judge_api_key: str | None = None
    upload_to_foundry: bool = True
    use_judges: bool = True
    use_safety: bool = True

    def __post_init__(self) -> None:
        self.team_dir = Path(self.team_dir).resolve()
        if not self.judge_endpoint:
            self.judge_endpoint = _derive_judge_endpoint(self.foundry_project_endpoint)

    @classmethod
    def from_env(
        cls,
        project_endpoint: str | None = None,
        team_dir: str | Path | None = None,
        judge_deployment: str | None = None,
        upload_to_foundry: bool = True,
        use_judges: bool = True,
        use_safety: bool = True,
    ) -> "EvalConfig":
        load_dotenv()
        endpoint = project_endpoint or os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
        if not endpoint:
            raise ValueError(
                "FOUNDRY_PROJECT_ENDPOINT is not set. Copy evals/.env.example to "
                "evals/.env and point it at your team's Foundry project, or pass "
                "--project-endpoint."
            )
        return cls(
            foundry_project_endpoint=endpoint,
            team_dir=Path(team_dir or os.environ.get("EVAL_TEAM_DIR", DEFAULT_TEAM_DIR)),
            judge_deployment=(
                judge_deployment
                or os.environ.get("EVAL_JUDGE_DEPLOYMENT", DEFAULT_JUDGE_DEPLOYMENT)
            ),
            judge_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
            judge_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_JUDGE_API_VERSION),
            judge_api_key=os.environ.get("AZURE_OPENAI_API_KEY") or None,
            upload_to_foundry=upload_to_foundry,
            use_judges=use_judges,
            use_safety=use_safety,
        )

    @property
    def judge_is_reasoning_model(self) -> bool:
        return self.judge_deployment.lower().startswith(_REASONING_PREFIXES)

    def judge_model_config(self) -> dict[str, str]:
        """Model config for the azure-ai-evaluation LLM judges."""
        config = {
            "azure_endpoint": self.judge_endpoint,
            "azure_deployment": self.judge_deployment,
            "api_version": self.judge_api_version,
        }
        if self.judge_api_key:
            config["api_key"] = self.judge_api_key
        return config
