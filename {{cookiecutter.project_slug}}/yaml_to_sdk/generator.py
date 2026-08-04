"""
Code generator for Agent Framework SDK implementations.

Extracts context from agent definitions and renders Jinja2 templates.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from jinja2 import Environment, FileSystemLoader

from .schema import (
    FoundryAgentDefinition,
    FunctionTool,
    MCPTool,
    TeamDefinition,
    OrchestrationPattern,
)


# JSON Schema type -> Python annotation used for generated tool signatures.
_JSON_TO_PY_TYPE = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list",
    "object": "dict",
}


class AgentCodeGenerator:
    """Generate Python code from Foundry agent definitions."""
    
    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize the code generator.
        
        Args:
            templates_dir: Path to Jinja2 templates directory
                          (defaults to ./templates in this package)
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            # Templates render Python / Markdown / Dockerfiles, not HTML, so
            # autoescaping must stay off (it would corrupt quotes in prompts).
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        
        # Add custom filters
        self._register_filters()
    
    def _register_filters(self):
        """Register custom Jinja2 filters."""
        
        def snake_case(s: str) -> str:
            """Convert string to snake_case."""
            s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
            s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
            return s.lower().replace("-", "_")
        
        def camel_case(s: str) -> str:
            """Convert string to camelCase."""
            components = s.replace("-", "_").split("_")
            return components[0].lower() + "".join(x.title() for x in components[1:])
        
        def pascal_case(s: str) -> str:
            """Convert string to PascalCase."""
            components = s.replace("-", "_").split("_")
            return "".join(x.title() for x in components)
        
        def safe_identifier(s: str) -> str:
            """Convert to safe Python identifier."""
            s = re.sub(r"[^a-zA-Z0-9_]", "_", s)
            if s[0].isdigit():
                s = "_" + s
            return s
        
        self.env.filters["snake_case"] = snake_case
        self.env.filters["camel_case"] = camel_case
        self.env.filters["pascal_case"] = pascal_case
        self.env.filters["safe_identifier"] = safe_identifier

    @staticmethod
    def _python_params(parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build a typed parameter list for a generated tool signature.

        Returns a list of ``{name, annotation, required, description}`` dicts
        ordered with required parameters first (so they can be rendered without
        defaults before optional ones).
        """
        properties = (parameters or {}).get("properties", {}) or {}
        required = set((parameters or {}).get("required", []) or [])

        params: List[Dict[str, Any]] = []
        for raw_name, spec in properties.items():
            spec = spec or {}
            safe = re.sub(r"[^a-zA-Z0-9_]", "_", str(raw_name))
            if safe and safe[0].isdigit():
                safe = "_" + safe
            params.append({
                "name": safe,
                "annotation": _JSON_TO_PY_TYPE.get(spec.get("type", "string"), "str"),
                "required": raw_name in required,
                "description": spec.get("description", ""),
            })
        # Required params first to keep a valid Python signature.
        params.sort(key=lambda p: not p["required"])
        return params
    
    def generate_context(self, agent_def: FoundryAgentDefinition) -> Dict[str, Any]:
        """
        Extract context from agent definition for template rendering.
        
        Args:
            agent_def: Validated agent definition
            
        Returns:
            Dictionary of template variables
        """
        # Extract function tools
        function_tools = []
        mcp_tools = []
        
        for tool in agent_def.definition.tools:
            if isinstance(tool, FunctionTool):
                parameters = tool.parameters.dict() if tool.parameters else {}
                function_tools.append({
                    "name": tool.name,
                    "safe_name": tool.safe_name,
                    "class_name": tool.class_name,
                    "description": tool.description,
                    "parameters": parameters,
                    "py_params": self._python_params(parameters),
                    "strict": tool.strict,
                })
            elif isinstance(tool, MCPTool):
                mcp_tools.append({
                    "name": tool.server_label,
                    "safe_name": tool.safe_name,
                    "server_url": tool.server_url,
                    "project_connection_id": tool.project_connection_id,
                    "description": tool.description or f"Knowledge base: {tool.server_label}",
                })
        
        reasoning_effort = "medium"
        if agent_def.definition.reasoning:
            reasoning_effort = agent_def.definition.reasoning.effort
        
        context = {
            # Agent metadata
            "agent_name": agent_def.name,
            "agent_slug": agent_def.project_slug,
            "agent_class": agent_def.class_name,
            "agent_version": "0.1.0",
            "agent_description": agent_def.definition.description or f"Agent: {agent_def.name}",
            
            # Model and instructions
            "model": agent_def.definition.model,
            "instructions": agent_def.definition.instructions,
            "reasoning_effort": reasoning_effort,
            
            # Tools
            "function_tools": function_tools,
            "mcp_tools": mcp_tools,
            "has_function_tools": len(function_tools) > 0,
            "has_mcp_tools": len(mcp_tools) > 0,
            "total_tools": len(function_tools) + len(mcp_tools),
            
            # Metadata
            "year": 2026,
            "timestamp": "2026-07-07",
        }
        
        return context
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render a Jinja2 template with given context.
        
        Args:
            template_name: Name of template file (e.g., 'orchestrator.py.j2')
            context: Dictionary of variables for template
            
        Returns:
            Rendered template as string
            
        Raises:
            FileNotFoundError: If template doesn't exist
            jinja2.TemplateError: If rendering fails
        """
        template = self.env.get_template(template_name)
        return template.render(**context)
    
    def generate_orchestrator(self, agent_def: FoundryAgentDefinition) -> str:
        """Generate main orchestrator.py."""
        context = self.generate_context(agent_def)
        return self.render_template("orchestrator.py.j2", context)
    
    def generate_models(self, agent_def: FoundryAgentDefinition) -> str:
        """Generate models.py with type definitions."""
        context = self.generate_context(agent_def)
        return self.render_template("models.py.j2", context)
    
    def generate_config(self, agent_def: FoundryAgentDefinition) -> str:
        """Generate config.py with configuration management."""
        context = self.generate_context(agent_def)
        return self.render_template("config.py.j2", context)
    
    def generate_tools_base(self, agent_def: FoundryAgentDefinition) -> str:
        """Generate tools_base.py with tool utilities."""
        context = self.generate_context(agent_def)
        return self.render_template("tools_base.py.j2", context)
    
    def generate_pyproject(self, agent_def: FoundryAgentDefinition) -> str:
        """Generate pyproject.toml."""
        context = self.generate_context(agent_def)
        return self.render_template("pyproject.toml.j2", context)
    
    def generate_test_agent(self, agent_def: FoundryAgentDefinition) -> str:
        """Generate test_agent.py with pytest tests."""
        context = self.generate_context(agent_def)
        return self.render_template("test_agent.py.j2", context)
    
    def generate_env_example(self, agent_def: FoundryAgentDefinition) -> str:
        """Generate .env.example template."""
        context = self.generate_context(agent_def)
        return self.render_template("env.example.j2", context)
    
    def generate_dockerfile(self, agent_def: FoundryAgentDefinition) -> str:
        """Generate Dockerfile for containerization."""
        context = self.generate_context(agent_def)
        return self.render_template("Dockerfile.j2", context)
    
    def generate_readme(self, agent_def: FoundryAgentDefinition) -> str:
        """Generate README.md documentation."""
        context = self.generate_context(agent_def)
        return self.render_template("README.md.j2", context)

    # ==================================================================
    # Multi-agent orchestration ("team") generation
    # ==================================================================

    def generate_team_context(
        self,
        team: TeamDefinition,
        agent_defs: List[FoundryAgentDefinition],
    ) -> Dict[str, Any]:
        """Build the template context for a multi-agent orchestration."""
        orch = team.orchestration
        pattern = OrchestrationPattern(orch.pattern).value

        # Per-agent context, reusing the single-agent extractor and adding the
        # metadata needed to wire the orchestration.
        agents: List[Dict[str, Any]] = []
        name_to_slug: Dict[str, str] = {}
        for agent_def in agent_defs:
            ctx = self.generate_context(agent_def)
            slug = agent_def.project_slug
            name_to_slug[agent_def.name] = slug
            ctx.update({
                "slug": slug,
                "module": slug,
                "var_name": slug,
                "factory": f"create_{slug}",
            })
            agents.append(ctx)

        def resolve(agent_name: Optional[str]) -> Optional[str]:
            """Resolve an agent name reference to its slug/var name."""
            if agent_name is None:
                return None
            if agent_name in name_to_slug:
                return name_to_slug[agent_name]
            # Allow referencing by slug directly.
            slug = agent_name.lower().replace("-", "_")
            if slug in name_to_slug.values():
                return slug
            raise ValueError(
                f"Orchestration references unknown agent '{agent_name}'. "
                f"Known agents: {', '.join(name_to_slug)}"
            )

        # Handoff routing resolved to var names.
        handoffs = [
            {
                "source": resolve(src),
                "targets": [resolve(t) for t in targets],
            }
            for src, targets in orch.handoffs.items()
        ]
        start_agent = resolve(orch.start_agent) if orch.start_agent else (
            agents[0]["var_name"] if agents else None
        )

        # Manager (group_chat orchestrator / magentic manager).
        manager = None
        if orch.manager is not None:
            manager = {
                "name": orch.manager.name,
                "model": orch.manager.model,
                "instructions": orch.manager.instructions
                or "You coordinate a team of specialized agents to complete the task.",
                "description": orch.manager.description
                or "Coordinates the specialized agents.",
            }

        builder_imports = {
            "sequential": ["SequentialBuilder"],
            "concurrent": ["ConcurrentBuilder"],
            "group_chat": ["GroupChatBuilder", "GroupChatState"],
            "handoff": ["HandoffBuilder"],
        }[pattern]

        # De-duplicated function tools across all agents (for a single tools.py).
        function_tools: List[Dict[str, Any]] = []
        seen_tools = set()
        for a in agents:
            for t in a["function_tools"]:
                if t["name"] in seen_tools:
                    continue
                seen_tools.add(t["name"])
                function_tools.append(t)

        return {
            "team_name": team.name,
            "team_slug": team.project_slug,
            "team_class": team.class_name,
            "team_description": team.description
            or orch.description
            or f"Multi-agent team: {team.name}",
            "pattern": pattern,
            "builder_imports": builder_imports,
            "agents": agents,
            "function_tools": function_tools,
            "manager": manager,
            "max_rounds": orch.max_rounds,
            "start_agent": start_agent,
            "handoffs": handoffs,
            "default_task": orch.task or "Describe the task for the team here.",
            "year": 2026,
        }

    def generate_agent_module(
        self,
        agent_def: FoundryAgentDefinition,
    ) -> str:
        """Generate a per-agent factory module for a team member."""
        context = self.generate_context(agent_def)
        context["slug"] = agent_def.project_slug
        context["factory"] = f"create_{agent_def.project_slug}"
        return self.render_template("agent_module.py.j2", context)

    def generate_team_orchestrator(
        self,
        team: TeamDefinition,
        agent_defs: List[FoundryAgentDefinition],
    ) -> str:
        """Generate the top-level orchestrator that wires the chosen pattern."""
        context = self.generate_team_context(team, agent_defs)
        return self.render_template("team_orchestrator.py.j2", context)

    def generate_team_config(
        self,
        team: TeamDefinition,
        agent_defs: List[FoundryAgentDefinition],
    ) -> str:
        """Generate config.py for a team project."""
        context = self.generate_team_context(team, agent_defs)
        return self.render_template("team_config.py.j2", context)

    def generate_team_tools(
        self,
        team: TeamDefinition,
        agent_defs: List[FoundryAgentDefinition],
    ) -> str:
        """Generate tools.py — the single tool-implementation registry for the team."""
        context = self.generate_team_context(team, agent_defs)
        return self.render_template("team_tools.py.j2", context)

    def generate_team_readme(
        self,
        team: TeamDefinition,
        agent_defs: List[FoundryAgentDefinition],
    ) -> str:
        """Generate README.md for a team project."""
        context = self.generate_team_context(team, agent_defs)
        return self.render_template("team_README.md.j2", context)

    def generate_team_test(
        self,
        team: TeamDefinition,
        agent_defs: List[FoundryAgentDefinition],
    ) -> str:
        """Generate tests/test_team.py for a team project."""
        context = self.generate_team_context(team, agent_defs)
        return self.render_template("test_team.py.j2", context)


if __name__ == "__main__":
    from .loader import load_agent_definition
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        try:
            agent = load_agent_definition(file_path)
            gen = AgentCodeGenerator()
            context = gen.generate_context(agent)
            
            print(f"✅ Generated context for: {agent.name}")
            print(f"   Agent class: {context['agent_class']}")
            print(f"   Function tools: {len(context['function_tools'])}")
            print(f"   MCP tools: {len(context['mcp_tools'])}")
            print(f"\nContext keys:")
            for key in sorted(context.keys()):
                print(f"  • {key}")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        print("Usage: python -m yaml_to_sdk.generator <agent_file>")
