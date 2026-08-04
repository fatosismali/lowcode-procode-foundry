"""
Foundry YAML → Agent Framework SDK Generator

A cookie cutter template for transforming low-code YAML agent definitions
from Microsoft Foundry Agent Service into pro-code Python implementations
using the Microsoft Agent Framework SDK.

Main entry points:
- Command line: python -m yaml_to_sdk --agent-yaml path/to/agent.yaml --output-dir ./generated
- Programmatic: from yaml_to_sdk import load_agent, AgentCodeGenerator
"""

__version__ = "1.0.0"
__author__ = "Vodafone AI Team"

from .loader import AgentYAMLLoader, load_agent
from .generator import AgentCodeGenerator
from .schema import FoundryAgentDefinition

__all__ = [
    "AgentYAMLLoader",
    "load_agent",
    "AgentCodeGenerator",
    "FoundryAgentDefinition",
]
