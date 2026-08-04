"""
YAML/JSON loader for Foundry agent definitions.

Handles file I/O, parsing, and validation.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Union, Optional, List, NamedTuple

import yaml
from pydantic import ValidationError

from .schema import FoundryAgentDefinition, TeamDefinition


class AgentYAMLLoader:
    """Load and validate Foundry agent definitions from YAML/JSON files."""
    
    @staticmethod
    def load_yaml_file(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load a YAML file and return parsed dictionary.
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            Parsed YAML content as dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"YAML file not found: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                
            if not isinstance(data, dict):
                raise ValueError(f"YAML file must contain a dictionary, got {type(data).__name__}")
                
            return data
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse YAML file {file_path}: {e}")
    
    @staticmethod
    def load_json_file(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load a JSON file and return parsed dictionary.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Parsed JSON content as dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If JSON is invalid
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"JSON file not found: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if not isinstance(data, dict):
                raise ValueError(f"JSON file must contain a dictionary, got {type(data).__name__}")
                
            return data
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Failed to parse JSON file {file_path}: {e.msg}",
                e.doc,
                e.pos
            )
    
    @staticmethod
    def validate_and_parse(
        data: Dict[str, Any],
        strict: bool = False
    ) -> FoundryAgentDefinition:
        """
        Validate dictionary against schema and return parsed agent definition.
        
        Args:
            data: Dictionary to validate
            strict: If True, raise on validation errors; if False, report all errors
            
        Returns:
            Validated FoundryAgentDefinition instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            return FoundryAgentDefinition(**data)
        except ValidationError as e:
            if strict:
                raise
            # Collect all validation errors
            print("\n❌ Validation Errors:")
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                msg = error["msg"]
                print(f"  • {loc}: {msg}")
            raise


def load_agent_definition(
    file_path: Union[str, Path],
    format: Optional[str] = None,
    strict: bool = False
) -> FoundryAgentDefinition:
    """
    Load and parse an agent definition from file.
    
    Auto-detects format if not specified.
    
    Args:
        file_path: Path to agent definition file
        format: File format ('yaml', 'json', or None for auto-detect)
        strict: If True, raise on validation errors
        
    Returns:
        Validated FoundryAgentDefinition instance
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If format can't be determined
        ValidationError: If validation fails
    """
    file_path = Path(file_path)
    
    # Auto-detect format
    if format is None:
        suffix = file_path.suffix.lower()
        if suffix == ".yaml" or suffix == ".yml":
            format = "yaml"
        elif suffix == ".json":
            format = "json"
        else:
            raise ValueError(
                f"Cannot determine file format from extension '{suffix}'. "
                f"Specify format='yaml' or format='json'"
            )
    
    # Load file
    if format.lower() == "yaml" or format.lower() == "yml":
        data = AgentYAMLLoader.load_yaml_file(file_path)
    elif format.lower() == "json":
        data = AgentYAMLLoader.load_json_file(file_path)
    else:
        raise ValueError(f"Unsupported format: {format}")
    
    # Validate and parse
    return AgentYAMLLoader.validate_and_parse(data, strict=strict)


class LoadedTeam(NamedTuple):
    """A validated team definition together with its resolved agent definitions
    and the source paths of each agent YAML (so they can be copied into the
    generated project for runtime loading)."""

    team: TeamDefinition
    agents: List[FoundryAgentDefinition]
    agent_paths: List[Path] = []


def load_team_definition(
    file_path: Union[str, Path],
    strict: bool = False,
) -> LoadedTeam:
    """Load a multi-agent orchestration ("team") definition and every agent it
    references.

    Agent paths in the team file are resolved relative to the team file's
    directory (unless they are absolute).

    Args:
        file_path: Path to the team/orchestration YAML or JSON file
        strict: If True, raise on validation errors

    Returns:
        LoadedTeam(team, agents)

    Raises:
        FileNotFoundError: If the team file or a referenced agent file is missing
        ValueError: If no agents are referenced
        ValidationError: If validation fails
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        data = AgentYAMLLoader.load_yaml_file(file_path)
    elif suffix == ".json":
        data = AgentYAMLLoader.load_json_file(file_path)
    else:
        raise ValueError(
            f"Cannot determine team file format from extension '{suffix}'."
        )

    try:
        team = TeamDefinition(**data)
    except ValidationError as e:
        if strict:
            raise
        print("\n❌ Team validation errors:")
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            print(f"  • {loc}: {error['msg']}")
        raise

    if not team.orchestration.agents:
        raise ValueError(
            "Team definition must reference at least one agent file via "
            "'orchestration.agents'."
        )

    base_dir = file_path.parent
    agents: List[FoundryAgentDefinition] = []
    agent_paths: List[Path] = []
    for agent_ref in team.orchestration.agents:
        agent_path = Path(agent_ref)
        if not agent_path.is_absolute():
            agent_path = (base_dir / agent_path).resolve()
        if not agent_path.exists():
            raise FileNotFoundError(
                f"Referenced agent file not found: {agent_path} "
                f"(from team file {file_path})"
            )
        agents.append(load_agent_definition(agent_path, strict=strict))
        agent_paths.append(agent_path)

    return LoadedTeam(team=team, agents=agents, agent_paths=agent_paths)
    # Test loader
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        try:
            agent = load_agent_definition(file_path)
            print(f"✅ Loaded agent: {agent.name}")
            print(f"   Class: {agent.class_name}")
            print(f"   Tools: {len(agent.definition.tools)}")
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    else:
        print("Usage: python -m yaml_to_sdk.loader <agent_file>")
