"""
CLI entry point for YAML to SDK code generator.

Orchestrates the full pipeline: load → validate → generate → write → verify
"""

import argparse
import ast
import logging
import sys
from pathlib import Path
from typing import List, Optional

from .loader import load_agent_definition, load_team_definition, LoadedTeam
from .generator import AgentCodeGenerator
from .schema import TeamDefinition


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = logging.getLogger(__name__)


def create_directory_structure(
    project_dir: Path,
    agent_def,
    generator: AgentCodeGenerator
) -> None:
    """
    Create the complete project directory structure with generated files.
    
    Args:
        project_dir: Base project directory
        agent_def: Validated agent definition
        generator: Code generator instance
    """
    # Create directories
    src_dir = project_dir / "src"
    tests_dir = project_dir / "tests"
    tools_dir = src_dir / "tools"
    
    src_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)
    tools_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate and write files
    files_to_create = {
        # Source files
        "src/__init__.py": "",
        "src/orchestrator.py": generator.generate_orchestrator(agent_def),
        "src/models.py": generator.generate_models(agent_def),
        "src/config.py": generator.generate_config(agent_def),
        "src/tools_base.py": generator.generate_tools_base(agent_def),
        "src/tools/__init__.py": "",
        
        # Test files
        "tests/__init__.py": "",
        "tests/test_agent.py": generator.generate_test_agent(agent_def),
        
        # Configuration files
        "pyproject.toml": generator.generate_pyproject(agent_def),
        ".env.example": generator.generate_env_example(agent_def),
        "Dockerfile": generator.generate_dockerfile(agent_def),
        "README.md": generator.generate_readme(agent_def),
        ".gitignore": _generate_gitignore(),
        "requirements.txt": _generate_requirements(),
    }
    
    for file_path, content in files_to_create.items():
        full_path = project_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info(f"  ✓ {file_path}")


def _generate_gitignore() -> str:
    """Generate standard Python .gitignore."""
    return """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# PyInstaller
*.manifest
*.spec

# Unit test / coverage reports
htmlcov/
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/
.pytest_cache/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
target/

# Jupyter Notebook
.ipynb_checkpoints

# pyenv
.python-version

# celery beat schedule file
celerybeat-schedule

# SageMath parsed files
.sagemath-parsed-files

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Generated projects
generated_agents/
"""


def _generate_requirements() -> str:
    """Generate standard requirements.txt."""
    return """# Agent Framework SDK
agent-framework-core~=1.8.0

# Azure
azure-identity>=1.14.0
azure-ai-projects>=1.0.0

# Data validation
pydantic>=2.0.0
pydantic-settings>=2.0.0

# HTTP and async
aiohttp>=3.9.0
httpx>=0.25.0

# YAML and JSON
PyYAML>=6.0

# Logging and monitoring
python-json-logger>=2.0.0

# Development dependencies
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
black>=23.0.0
mypy>=1.5.0
ruff>=0.1.0
"""


def verify_generated_code(project_dir: Path, verbose: bool = False) -> bool:
    """
    Verify generated Python code is syntactically valid.
    
    Args:
        project_dir: Project directory to verify
        verbose: Print detailed verification info
        
    Returns:
        True if all files are valid Python, False otherwise
    """
    logger.info("\n🔍 Verifying generated code...")
    
    python_files = list(project_dir.glob("src/**/*.py")) + list(project_dir.glob("tests/**/*.py"))
    
    all_valid = True
    for py_file in python_files:
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                code = f.read()
            ast.parse(code)
            if verbose:
                logger.info(f"  ✓ {py_file.relative_to(project_dir)}")
        except SyntaxError as e:
            logger.error(f"  ✗ {py_file.relative_to(project_dir)}: {e}")
            all_valid = False
    
    if all_valid:
        logger.info(f"✅ All {len(python_files)} Python files are valid")
    else:
        logger.error("❌ Some files have syntax errors")
    
    return all_valid


def print_generation_summary(project_dir: Path, agent_name: str) -> None:
    """Print a summary of what was generated."""
    logger.info("\n" + "=" * 70)
    logger.info("✅ AGENT SUCCESSFULLY GENERATED!")
    logger.info("=" * 70)
    logger.info(f"\nAgent: {agent_name}")
    logger.info(f"Location: {project_dir}")
    
    logger.info("\n📁 Generated Structure:")
    logger.info(f"  src/")
    logger.info(f"    ├── orchestrator.py      (Main agent - EDIT THIS)")
    logger.info(f"    ├── models.py            (Type models)")
    logger.info(f"    ├── config.py            (Configuration)")
    logger.info(f"    ├── tools_base.py        (Tool utilities)")
    logger.info(f"    └── tools/               (Tool implementations)")
    logger.info(f"  tests/")
    logger.info(f"    └── test_agent.py        (Test suite - EXTEND THIS)")
    logger.info(f"  pyproject.toml            (Project metadata)")
    logger.info(f"  requirements.txt          (Dependencies)")
    logger.info(f"  .env.example              (Configuration template)")
    logger.info(f"  Dockerfile                (Container build)")
    logger.info(f"  README.md                 (Documentation)")
    
    logger.info("\n🚀 Next Steps:")
    logger.info(f"  1. cd {project_dir.name}")
    logger.info(f"  2. cp .env.example .env")
    logger.info(f"  3. Edit .env with your Foundry credentials")
    logger.info(f"  4. pip install -r requirements.txt")
    logger.info(f"  5. python src/orchestrator.py")
    
    logger.info("\n📚 Documentation:")
    logger.info(f"  • Read README.md in the project directory")
    logger.info(f"  • Implement tool logic in src/orchestrator.py")
    logger.info(f"  • Add tests to tests/test_agent.py")
    
    logger.info("\n" + "=" * 70 + "\n")


def generate_agent_project(
    agent_yaml: Path,
    output_dir: Path,
    verify: bool = True,
    force: bool = False,
    verbose: bool = False
) -> bool:
    """
    Complete generation pipeline: load → validate → generate → write → verify
    
    Args:
        agent_yaml: Path to agent YAML file
        output_dir: Output directory for generated project
        verify: Verify generated code
        force: Force overwrite existing project
        verbose: Print verbose output
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Step 1: Load and validate YAML
        logger.info(f"📖 Loading agent definition from {agent_yaml}...")
        agent_def = load_agent_definition(agent_yaml)
        logger.info(f"✅ Loaded: {agent_def.name}")
        
        # Step 2: Determine output directory
        project_dir = output_dir / agent_def.project_slug
        
        if project_dir.exists() and not force:
            logger.error(f"❌ Project directory already exists: {project_dir}")
            logger.info(f"   Use --force to overwrite")
            return False
        
        if project_dir.exists() and force:
            import shutil
            logger.info(f"🗑️  Removing existing project directory...")
            shutil.rmtree(project_dir)
        
        # Step 3: Initialize generator
        logger.info("🔧 Initializing code generator...")
        generator = AgentCodeGenerator()
        
        # Step 4: Generate files
        logger.info(f"📝 Generating project files...\n")
        create_directory_structure(project_dir, agent_def, generator)
        
        # Step 5: Verify (optional)
        if verify:
            if not verify_generated_code(project_dir, verbose=verbose):
                logger.warning("⚠️  Some verification issues found, but project was created")
        
        # Step 6: Print summary
        print_generation_summary(project_dir, agent_def.name)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Generation failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


# ======================================================================
# Multi-agent orchestration ("team") generation
# ======================================================================


def _team_env_example() -> str:
    return """# Microsoft Foundry project endpoint (required)
FOUNDRY_PROJECT_ENDPOINT=https://<your-project>.services.ai.azure.com/api/projects/<project>

# Default model deployment name (optional)
FOUNDRY_MODEL=gpt-5

# Logging level (optional)
LOG_LEVEL=INFO
"""


def _team_pyproject(team_slug: str, description: str) -> str:
    return f"""[project]
name = "{team_slug}"
version = "0.1.0"
description = {description!r}
requires-python = ">=3.10"
dependencies = [
    "agent-framework>=1.11.0",
    "azure-identity>=1.14.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "integration: end-to-end tests that call Foundry (deselect with '-m \\"not integration\\"')",
]
"""


def _team_requirements() -> str:
    return """# Microsoft Agent Framework (agents + orchestrations)
agent-framework>=1.11.0

# Azure authentication
azure-identity>=1.14.0

# Runtime YAML loading of the team + agent definitions
PyYAML>=6.0

# Development
pytest>=7.4.0
pytest-asyncio>=0.21.0
"""


def _team_dockerfile() -> str:
    return """FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "src.orchestrator"]
"""


def _team_yaml_document(loaded: "LoadedTeam") -> str:
    """Build the team.yaml that ships inside the project.

    Agent references are rewritten to the copied files under ./agents/, so the
    generated orchestrator can traverse them at runtime.
    """
    import yaml

    team = loaded.team
    orch = team.orchestration
    orchestration: dict = {
        "pattern": orch.pattern.value,
        "agents": [f"./agents/{a.project_slug}.yaml" for a in loaded.agents],
    }
    if orch.task:
        orchestration["task"] = orch.task
    if orch.pattern.value == "group_chat":
        orchestration["max_rounds"] = orch.max_rounds
    if orch.start_agent:
        orchestration["start_agent"] = orch.start_agent
    if orch.handoffs:
        orchestration["handoffs"] = orch.handoffs

    document: dict = {"name": team.name}
    if team.description:
        document["description"] = team.description
    document["orchestration"] = orchestration

    header = (
        "# Team specification for '{}'.\n"
        "# The orchestrator loads this file and every agent under ./agents/ at runtime.\n"
        "# pattern: sequential | concurrent | group_chat | handoff\n\n"
    ).format(team.name)
    return header + yaml.safe_dump(document, sort_keys=False, allow_unicode=True)


def create_team_directory_structure(
    project_dir: Path,
    loaded: LoadedTeam,
    generator: AgentCodeGenerator,
) -> None:
    """Create the complete multi-agent project structure.

    A single ``src/orchestrator.py`` loads the team + agent YAMLs at runtime and
    builds every agent in-process — no per-agent Python files are generated.
    """
    import shutil

    team, agents = loaded.team, loaded.agents

    src_dir = project_dir / "src"
    agents_dir = project_dir / "agents"
    tests_dir = project_dir / "tests"

    for d in (src_dir, agents_dir, tests_dir):
        d.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {
        "src/__init__.py": "",
        "src/orchestrator.py": generator.generate_team_orchestrator(team, agents),
        "src/tools.py": generator.generate_team_tools(team, agents),
        "src/config.py": generator.generate_team_config(team, agents),
        "tests/__init__.py": "",
        "tests/test_team.py": generator.generate_team_test(team, agents),
        "team.yaml": _team_yaml_document(loaded),
        "pyproject.toml": _team_pyproject(
            team.project_slug,
            team.description or f"Multi-agent team: {team.name}",
        ),
        "requirements.txt": _team_requirements(),
        ".env.example": _team_env_example(),
        "Dockerfile": _team_dockerfile(),
        "README.md": generator.generate_team_readme(team, agents),
        ".gitignore": _generate_gitignore(),
    }

    for file_path, content in files.items():
        full_path = project_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"  ✓ {file_path}")

    # Copy each source agent YAML into ./agents/<slug>.yaml for runtime loading.
    for agent_def, src_path in zip(agents, loaded.agent_paths):
        dest = agents_dir / f"{agent_def.project_slug}.yaml"
        shutil.copyfile(src_path, dest)
        logger.info(f"  ✓ agents/{agent_def.project_slug}.yaml")



def generate_team_project(
    loaded: LoadedTeam,
    output_dir: Path,
    verify: bool = True,
    force: bool = False,
    verbose: bool = False,
) -> bool:
    """Generate a multi-agent orchestration project."""
    try:
        team = loaded.team
        project_dir = output_dir / team.project_slug

        if project_dir.exists() and not force:
            logger.error(f"❌ Project directory already exists: {project_dir}")
            logger.info("   Use --force to overwrite")
            return False
        if project_dir.exists() and force:
            import shutil
            logger.info("🗑️  Removing existing project directory...")
            shutil.rmtree(project_dir)

        logger.info("🔧 Initializing code generator...")
        generator = AgentCodeGenerator()

        logger.info(
            f"📝 Generating '{team.name}' "
            f"({team.orchestration.pattern.value} orchestration, "
            f"{len(loaded.agents)} agents)...\n"
        )
        create_team_directory_structure(project_dir, loaded, generator)

        if verify:
            if not verify_generated_code(project_dir, verbose=verbose):
                logger.warning("⚠️  Some verification issues found, but project was created")

        logger.info("\n" + "=" * 70)
        logger.info("✅ TEAM SUCCESSFULLY GENERATED!")
        logger.info("=" * 70)
        logger.info(f"\nTeam: {team.name}")
        logger.info(f"Pattern: {team.orchestration.pattern.value}")
        logger.info(f"Agents: {', '.join(a.name for a in loaded.agents)}")
        logger.info(f"Location: {project_dir}")
        logger.info("\n🚀 Next Steps:")
        logger.info("  1. cd " + project_dir.name)
        logger.info("  2. cp .env.example .env  (add your Foundry endpoint)")
        logger.info("  3. pip install -r requirements.txt")
        logger.info("  4. Implement tool bodies in src/tools.py")
        logger.info("  5. python -m src.orchestrator")
        logger.info("\n" + "=" * 70 + "\n")
        return True

    except Exception as e:
        logger.error(f"❌ Team generation failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def build_team_from_args(
    agent_files: List[Path],
    pattern: str,
    name: str,
    strict: bool = False,
) -> LoadedTeam:
    """Build a LoadedTeam from a list of agent files and a pattern (CLI mode)."""
    agent_files = [Path(p).resolve() for p in agent_files]
    agents = [load_agent_definition(p, strict=strict) for p in agent_files]
    team = TeamDefinition(
        name=name,
        orchestration={
            "pattern": pattern,
            "agents": [str(p) for p in agent_files],
        },
    )
    return LoadedTeam(team=team, agents=agents, agent_paths=agent_files)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate Agent Framework SDK code from Foundry YAML definitions. "
            "Generate a single agent, or a multi-agent orchestration (team)."
        )
    )

    # --- Input modes (choose one) ---
    parser.add_argument(
        "--agent-yaml",
        type=Path,
        help="Single-agent mode: path to one agent YAML definition file",
    )
    parser.add_argument(
        "--team-yaml",
        type=Path,
        help="Team mode: path to an orchestration/team YAML file that references agents",
    )
    parser.add_argument(
        "--agents",
        nargs="+",
        type=Path,
        metavar="AGENT_YAML",
        help="Team mode: two or more agent YAML files (use with --pattern)",
    )
    parser.add_argument(
        "--pattern",
        choices=["sequential", "concurrent", "group_chat", "handoff"],
        help="Team mode: orchestration pattern (optional; defaults to sequential)",
    )
    parser.add_argument(
        "--name",
        help="Team mode: team name (default: derived from the pattern)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./generated_agents"),
        help="Output directory for generated projects (default: ./generated_agents)",
    )

    parser.add_argument(
        "--verify",
        action="store_true",
        default=True,
        help="Verify generated Python code (default: True)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_false",
        dest="verify",
        help="Skip code verification",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing project directory",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    modes_selected = sum(
        bool(x) for x in (args.agent_yaml, args.team_yaml, args.agents)
    )
    if modes_selected == 0:
        parser.error(
            "Provide one of: --agent-yaml, --team-yaml, or --agents (with --pattern)."
        )
    if modes_selected > 1:
        parser.error(
            "Choose only one input mode: --agent-yaml, --team-yaml, or --agents."
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # --- Team mode: team YAML file ---
    if args.team_yaml:
        if not args.team_yaml.exists():
            logger.error(f"❌ Team YAML file not found: {args.team_yaml}")
            sys.exit(1)
        try:
            logger.info(f"📖 Loading team definition from {args.team_yaml}...")
            loaded = load_team_definition(args.team_yaml)
        except Exception as e:
            logger.error(f"❌ Failed to load team: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
        success = generate_team_project(
            loaded=loaded,
            output_dir=args.output_dir,
            verify=args.verify,
            force=args.force,
            verbose=args.verbose,
        )
        sys.exit(0 if success else 1)

    # --- Team mode: agent files + pattern ---
    if args.agents:
        # Pattern is optional; the codebase defaults to sequential.
        pattern = args.pattern or "sequential"
        missing = [str(p) for p in args.agents if not p.exists()]
        if missing:
            logger.error(f"❌ Agent file(s) not found: {', '.join(missing)}")
            sys.exit(1)
        team_name = args.name or f"{pattern.replace('_', '-')}-team"
        try:
            loaded = build_team_from_args(args.agents, pattern, team_name)
        except Exception as e:
            logger.error(f"❌ Failed to build team: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
        success = generate_team_project(
            loaded=loaded,
            output_dir=args.output_dir,
            verify=args.verify,
            force=args.force,
            verbose=args.verbose,
        )
        sys.exit(0 if success else 1)

    # --- Single-agent mode ---
    if not args.agent_yaml.exists():
        logger.error(f"❌ Agent YAML file not found: {args.agent_yaml}")
        sys.exit(1)

    success = generate_agent_project(
        agent_yaml=args.agent_yaml,
        output_dir=args.output_dir,
        verify=args.verify,
        force=args.force,
        verbose=args.verbose,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
