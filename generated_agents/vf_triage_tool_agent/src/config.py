"""Configuration management for the agent."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class AgentConfig(BaseSettings):
    """Agent configuration from environment variables."""
    
    # Required in production, defaulted for local test bootstrap
    foundry_project_connection_string: str = Field(
        default="https://example.foundry.azure.com/projects/local-test",
        description="Foundry project connection string"
    )
    
    # Model settings
    model_name: str = Field(
        default="gpt-5",
        description="Model name"
    )
    
    reasoning_effort: str = Field(
        default="low",
        description="Reasoning effort level (low/medium/high)"
    )
    
    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # Timeouts and limits
    tool_timeout_seconds: int = Field(
        default=30,
        description="Tool execution timeout in seconds"
    )
    
    max_tool_calls: int = Field(
        default=10,
        description="Maximum tool calls per conversation"
    )
    
    # Tool enable/disable flags
    enable_get_incident: bool = Field(
        default=True,
        description="Enable get_incident tool"
    )
    enable_fetch_telemetry: bool = Field(
        default=True,
        description="Enable fetch_telemetry tool"
    )
    enable_fetch_customer_impact: bool = Field(
        default=True,
        description="Enable fetch_customer_impact tool"
    )
    enable_apply_change: bool = Field(
        default=True,
        description="Enable apply_change tool"
    )
    
    # MCP server settings
    kb_regulationpolciies_ziw96_url: str = Field(
        default="https://msagthack-search-mzloe6z4nnwoc.search.windows.net/knowledgebases/regulationpolciies/mcp?api-version=2025-11-01-Preview",
        description="kb_regulationpolciies_ziw96 server URL"
    )
    
    kb_regulationpolciies_ziw96_connection_id: str = Field(
        default="kb-regulationpolciies-ziw96",
        description="kb_regulationpolciies_ziw96 connection ID"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()
    
    @field_validator("reasoning_effort")
    @classmethod
    def validate_reasoning_effort(cls, v):
        valid_efforts = ("low", "medium", "high")
        if v.lower() not in valid_efforts:
            raise ValueError(f"reasoning_effort must be one of {valid_efforts}")
        return v.lower()
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment."""
        return cls()