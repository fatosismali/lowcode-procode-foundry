"""
Pydantic schema definitions for Foundry agent YAML format.

Defines all model classes for type validation and conversion.
"""

from typing import Optional, Any, Literal, Union, List, Dict
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
import re


class FunctionToolParameters(BaseModel):
    """JSON Schema definition for function tool parameters."""
    
    type: str = Field(default="object", description="Schema type")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Parameter properties")
    required: List[str] = Field(default_factory=list, description="Required parameters")
    
    model_config = ConfigDict(extra="allow")


class FunctionTool(BaseModel):
    """Function tool definition."""
    
    type: Literal["function"] = "function"
    name: str = Field(..., description="Tool name (snake_case)")
    description: str = Field(..., description="Tool description")
    parameters: Optional[FunctionToolParameters] = Field(None, description="Tool parameters")
    strict: bool = Field(default=True, description="Strict parameter validation")
    
    @property
    def class_name(self) -> str:
        """Convert tool name to PascalCase class name."""
        return "".join(word.capitalize() for word in self.name.split("_"))
    
    @property
    def safe_name(self) -> str:
        """Get safe Python identifier version of tool name."""
        return re.sub(r"[^a-zA-Z0-9_]", "_", self.name).lower()


class MCPTool(BaseModel):
    """MCP server / Knowledge base tool definition."""
    
    type: Literal["mcp"] = "mcp"
    server_label: str = Field(..., description="MCP server label/name")
    server_url: str = Field(..., description="MCP server URL")
    project_connection_id: str = Field(..., description="Foundry project connection ID")
    description: Optional[str] = Field(None, description="Tool description")
    
    @property
    def safe_name(self) -> str:
        """Get safe Python identifier version of server label."""
        return re.sub(r"[^a-zA-Z0-9_]", "_", self.server_label).lower()


class ReasoningConfig(BaseModel):
    """Reasoning configuration."""
    
    effort: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Reasoning effort level"
    )
    
    @field_validator("effort")
    @classmethod
    def validate_effort(cls, v):
        if v not in ("low", "medium", "high"):
            raise ValueError(f"effort must be 'low', 'medium', or 'high', got '{v}'")
        return v


class AgentDefinition(BaseModel):
    """Agent configuration."""
    
    kind: Literal["prompt", "hosted"] = Field(
        default="hosted",
        description="Agent type (prompt or hosted)"
    )
    model: str = Field(
        default="gpt-5",
        description="Model name (gpt-5, gpt-4, etc.)"
    )
    instructions: str = Field(
        ...,
        description="System prompt/instructions for the agent"
    )
    description: Optional[str] = Field(None, description="Agent description")
    reasoning: Optional[ReasoningConfig] = Field(None, description="Reasoning config")
    tools: List[Union[FunctionTool, MCPTool]] = Field(
        default_factory=list,
        description="List of tools (function or MCP)"
    )
    
    model_config = ConfigDict(extra="allow")
    
    @field_validator("tools", mode="before")
    @classmethod
    def parse_tools(cls, v):
        """Parse tools, handling both function and MCP types."""
        if not isinstance(v, list):
            return v
        
        parsed_tools = []
        for tool in v:
            if isinstance(tool, dict):
                tool_type = tool.get("type", "function")
                if tool_type == "function":
                    parsed_tools.append(FunctionTool(**tool))
                elif tool_type == "mcp":
                    parsed_tools.append(MCPTool(**tool))
                else:
                    raise ValueError(f"Unknown tool type: {tool_type}")
            else:
                parsed_tools.append(tool)
        return parsed_tools


class FoundryAgentDefinition(BaseModel):
    """Root schema for Foundry agent YAML definition."""
    
    name: str = Field(..., description="Agent name (lowercase, hyphens allowed)")
    definition: AgentDefinition = Field(..., description="Agent configuration")
    
    model_config = ConfigDict(extra="allow")
    
    @property
    def project_slug(self) -> str:
        """Convert agent name to project slug (snake_case)."""
        return self.name.lower().replace("-", "_")
    
    @property
    def class_name(self) -> str:
        """Convert agent name to PascalCase class name."""
        return "".join(word.capitalize() for word in self.project_slug.split("_"))
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not re.match(r"^[a-z0-9_-]+$", v):
            raise ValueError(
                f"Agent name must contain only lowercase letters, numbers, underscores, "
                f"and hyphens, got '{v}'"
            )
        return v


# ======================================================================
# Multi-agent orchestration
# ======================================================================


class OrchestrationPattern(str, Enum):
    """Supported multi-agent orchestration patterns.

    Aligns with the Azure Architecture Center AI agent orchestration patterns
    and the Microsoft Agent Framework built-in workflow orchestrations.
    """

    SEQUENTIAL = "sequential"
    CONCURRENT = "concurrent"
    GROUP_CHAT = "group_chat"
    HANDOFF = "handoff"


class ManagerConfig(BaseModel):
    """Configuration for a coordinating/manager agent.

    Used by the ``group_chat`` pattern as an optional orchestrator agent.
    """

    name: str = Field(default="manager", description="Manager agent name")
    model: str = Field(default="gpt-5", description="Manager model deployment")
    instructions: Optional[str] = Field(
        default=None, description="Manager/orchestrator system prompt"
    )
    description: Optional[str] = Field(None, description="Manager description")

    model_config = ConfigDict(extra="allow")


class OrchestrationDefinition(BaseModel):
    """Definition of how a set of agents are orchestrated together."""

    # `pattern` is optional: if a team is handed over without an agreed pattern,
    # the codebase falls back to the default (sequential) so any valid set of
    # agents still produces a working, review-ready orchestration.
    pattern: OrchestrationPattern = Field(
        default=OrchestrationPattern.SEQUENTIAL,
        description="Orchestration pattern to generate (defaults to sequential)",
    )
    agents: List[str] = Field(
        default_factory=list,
        description="Paths to the individual agent YAML/JSON definition files",
    )
    description: Optional[str] = Field(None, description="Orchestration description")
    task: Optional[str] = Field(
        default=None,
        description="Default task/prompt used when running the orchestration",
    )

    # group_chat / magentic manager
    manager: Optional[ManagerConfig] = Field(
        default=None, description="Manager/orchestrator agent configuration"
    )

    # group_chat
    max_rounds: int = Field(
        default=6,
        ge=1,
        description="Group chat: maximum conversation turns before termination",
    )

    # handoff
    start_agent: Optional[str] = Field(
        default=None,
        description="Handoff: name of the agent that receives the initial input",
    )
    handoffs: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Handoff: map of source agent name -> list of target agent names",
    )

    model_config = ConfigDict(extra="allow")

    @field_validator("pattern", mode="before")
    @classmethod
    def normalize_pattern(cls, v):
        if isinstance(v, str):
            return v.strip().lower().replace("-", "_")
        return v


class TeamDefinition(BaseModel):
    """Root schema for a multi-agent orchestration ("team") definition."""

    name: str = Field(..., description="Team name (lowercase, hyphens allowed)")
    description: Optional[str] = Field(None, description="Team description")
    orchestration: OrchestrationDefinition = Field(
        ..., description="Orchestration configuration"
    )

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def hoist_flat_fields(cls, data):
        """Allow a flat layout where ``pattern`` and ``agents`` live at the top
        level instead of nested under ``orchestration``. The top-level
        ``description`` stays as the team description."""
        if not isinstance(data, dict):
            return data
        if "orchestration" not in data and ("pattern" in data or "agents" in data):
            orchestration_keys = {
                "pattern",
                "agents",
                "task",
                "manager",
                "max_rounds",
                "start_agent",
                "handoffs",
            }
            orchestration = {k: data[k] for k in orchestration_keys if k in data}
            data = {k: v for k, v in data.items() if k not in orchestration_keys}
            data["orchestration"] = orchestration
        return data

    @property
    def project_slug(self) -> str:
        """Convert team name to project slug (snake_case)."""
        return self.name.lower().replace("-", "_")

    @property
    def class_name(self) -> str:
        """Convert team name to PascalCase class name."""
        return "".join(word.capitalize() for word in self.project_slug.split("_"))

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not re.match(r"^[a-z0-9_-]+$", v):
            raise ValueError(
                f"Team name must contain only lowercase letters, numbers, underscores, "
                f"and hyphens, got '{v}'"
            )
        return v


if __name__ == "__main__":
    # Test schema
    test_yaml = {
        "name": "test-agent",
        "definition": {
            "model": "gpt-5",
            "instructions": "Test instructions",
            "tools": [
                {
                    "type": "function",
                    "name": "get_data",
                    "description": "Get some data",
                    "parameters": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                        "required": ["id"]
                    }
                }
            ]
        }
    }
    
    agent = FoundryAgentDefinition(**test_yaml)
    print(f"Agent name: {agent.name}")
    print(f"Project slug: {agent.project_slug}")
    print(f"Class name: {agent.class_name}")
    print(f"Tools: {len(agent.definition.tools)}")
