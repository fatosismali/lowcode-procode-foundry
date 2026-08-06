"""Configuration for evaluating any YAML-defined agent team.

Each team on simulation day has its own Foundry project. Set
FOUNDRY_PROJECT_ENDPOINT in evals/.env (or pass --project-endpoint) and the
judge endpoint is derived from it unless overridden.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

EVALS_ROOT = Path(__file__).resolve().parent
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


def _resolve(base: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


@dataclass(frozen=True)
class EvalSuite:
    """Team-owned evaluation configuration loaded from evals/eval.yaml."""

    path: Path
    data: dict[str, Any]

    @classmethod
    def load(cls, team_dir: str | Path) -> "EvalSuite":
        path = Path(team_dir).resolve() / "evals" / "eval.yaml"
        if not path.is_file():
            raise FileNotFoundError(f"Evaluation manifest not found: {path}")
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Evaluation manifest must contain an object: {path}")
        if not isinstance(loaded.get("sets"), dict) or not loaded["sets"]:
            raise ValueError(f"Evaluation manifest must define at least one set: {path}")
        return cls(path=path, data=loaded)

    @property
    def root(self) -> Path:
        return self.path.parent

    @property
    def name(self) -> str:
        return str(self.data.get("name") or self.path.parent.parent.name)

    @property
    def publish_name(self) -> str:
        return str(self.data.get("publish_name") or self.name)

    @property
    def team_yaml(self) -> Path:
        return _resolve(self.root, self.data.get("team_yaml", "../team.yaml"))

    @property
    def sets(self) -> dict[str, Path]:
        return {str(name): _resolve(self.root, value) for name, value in self.data["sets"].items()}

    @property
    def thresholds_file(self) -> Path:
        return _resolve(self.root, self.data.get("thresholds", "thresholds.yaml"))

    @property
    def reports_dir(self) -> Path:
        return _resolve(self.root, self.data.get("reports_dir", "reports"))

    @property
    def task(self) -> dict[str, Any]:
        return self.data.get("task", {}) or {}

    @property
    def output(self) -> dict[str, Any]:
        return self.data.get("output", {}) or {}

    @property
    def workflow_schema(self) -> dict[str, tuple[str, ...]]:
        schema = self.data.get("workflow_schema", {}) or {}
        return {str(status): tuple(str(key) for key in keys or []) for status, keys in schema.items()}

    @property
    def scope(self) -> dict[str, Any]:
        return self.data.get("scope", {}) or {}


@dataclass
class EvalConfig:
    """Everything the runner needs to drive the team and the judges."""

    foundry_project_endpoint: str
    team_dir: Path
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
        selected_team = team_dir or os.environ.get("EVAL_TEAM_DIR")
        if not selected_team:
            raise ValueError("Select a team with --team or EVAL_TEAM_DIR.")
        endpoint = project_endpoint or os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
        if not endpoint:
            raise ValueError(
                "FOUNDRY_PROJECT_ENDPOINT is not set. Copy evals/.env.example to "
                "evals/.env and point it at your team's Foundry project, or pass "
                "--project-endpoint."
            )
        return cls(
            foundry_project_endpoint=endpoint,
            team_dir=Path(selected_team),
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
    def suite(self) -> EvalSuite:
        return EvalSuite.load(self.team_dir)

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
