# Foundry YAML → Agent Framework SDK Template

Transform low-code YAML agent definitions from Microsoft Foundry Agent Service into production-ready Python code using the Agent Framework SDK.

## Overview

This cookie cutter template bridges the gap between:
- **Low Code**: YAML agent definitions from Foundry Agent Service (declarative, UI-driven)
- **Pro Code**: Python Agent Framework SDK implementations (programmatic, runtime control)

## Quick Start

```bash
# 1. Extract your agent YAML from Foundry Agent Service
# 2. Place it in: agent_definitions/your_agent.yaml

# 3. Generate Python code
python -m yaml_to_sdk \
    --agent-yaml agent_definitions/your_agent.yaml \
    --output-dir generated_agents

# 4. Install dependencies
cd generated_agents/your_agent
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env
# Edit .env with your Foundry credentials and model deployment info

# 6. Run the agent
python src/orchestrator.py
```

## Project Structure

```
{{cookiecutter.project_slug}}/
├── agent_definitions/          # Source YAML files from Foundry
│   └── example_agent.yaml      # Sample agent definition
├── generated_agents/           # Generated Python projects
│   └── example_agent/
│       ├── src/
│       │   ├── __init__.py
│       │   ├── orchestrator.py    # Main agent entry point
│       │   ├── tools/             # Tool implementations
│       │   ├── models.py          # Pydantic models for type safety
│       │   └── config.py          # Configuration & env loading
│       ├── tests/
│       ├── pyproject.toml
│       ├── uv.lock
│       ├── requirements.txt
│       ├── .env.example
│       └── README.md
├── yaml_to_sdk/                # Template generator logic
│   ├── __init__.py
│   ├── loader.py               # YAML parser & validator
│   ├── generator.py            # Python code generator
│   ├── schema.py               # YAML schema definitions
│   └── templates/              # Jinja2 code templates
│       ├── orchestrator.py.j2
│       ├── tools_base.py.j2
│       ├── models.py.j2
│       ├── config.py.j2
│       ├── pyproject.toml.j2
│       └── test_agent.py.j2
├── examples/                   # Reference implementations
│   ├── vf_triage_agent.yaml    # Vodafone example
│   └── README.md
├── README.md
├── pyproject.toml
└── requirements.txt
```

## Key Features

✅ **Type-Safe Code Generation** — Generates Pydantic models for tool inputs/outputs  
✅ **Tool Orchestration** — Creates tool execution layer with proper error handling  
✅ **Environment Management** — Handles secrets, credentials, model deployment configs  
✅ **Azure Foundry Integration** — Direct integration with Foundry credentials & models  
✅ **Logging & Observability** — Structured logging, OpenTelemetry instrumentation ready  
✅ **Test Scaffolding** — Generated pytest tests for tool validation  
✅ **Deployment Ready** — Generates Dockerfile, pyproject.toml, uv.lock, requirements.txt  

## YAML Agent Definition Format

The template expects YAML following the Foundry Agent Service schema:

```yaml
metadata:
  description: "Agent description"
object: agent.version
id: agent-name:1
name: agent-name
version: "1"
definition:
  kind: prompt  # or 'hosted' for container agents
  model: gpt-5  # Model family
  instructions: |
    System prompt with detailed instructions...
  reasoning:
    effort: low  # low, medium, high
  tools:
    - type: function
      name: tool_name
      description: "What this tool does"
      parameters:
        type: object
        properties:
          param1:
            type: string
            description: "Parameter description"
        required: [param1]
        additionalProperties: false
      strict: true
    - type: mcp
      server_label: kb_example
      server_url: "https://..."
      project_connection_id: kb-example
status: active
```

## Generated Agent Structure

Each generated agent includes:

### `orchestrator.py` — Main entry point
- `FoundryChatClient` initialization
- `Agent` with tools and system instructions
- Conversation loop with streaming responses
- Tool binding and invocation logic
- Error handling and retry patterns

### `tools/` — Tool implementations
- Base tool class with validation
- Type-safe tool functions using Pydantic
- MCP server client integration
- Error handling per tool

### `models.py` — Type definitions
- Pydantic models for all tool I/O
- Request/response validation
- Serialization helpers

### `config.py` — Configuration
- Environment variable loading
- Secrets management (Azure Key Vault ready)
- Model deployment configuration

### `tests/` — Automated tests
- Tool execution tests
- End-to-end agent flow tests
- Mock Foundry client for offline testing

## Supported YAML Features

| Feature | Status | Notes |
|---------|--------|-------|
| Function tools | ✅ Full | Strict schema, auto-generates types |
| MCP servers | ✅ Full | Integrated client setup |
| System instructions | ✅ Full | Multi-line, variable interpolation |
| Reasoning parameters | ✅ Full | Effort level guidance |
| Model selection | ✅ Full | GPT-5, GPT-4, custom deployments |
| Tool-use instructions | ✅ Full | Per-tool descriptions & constraints |
| Metadata & versioning | ✅ Full | Used for deployment & tracking |
| Instance identity (UAMI) | ✅ Full | RBAC role bindings automated |

## Best Practices

1. **Keep YAML definitions focused** — One agent = one YAML file
2. **Use strict tool schemas** — Set `strict: true` for all function tools
3. **Version your agents** — Bump the YAML `version` field for tracking
4. **Document tool descriptions** — Generator uses these for code comments
5. **Test generated code locally** — Run with `--verify` flag before deployment
6. **Use MCP for knowledge** — Leverage knowledge indexes for grounding/RAG

## Examples

See `examples/vf_triage_agent.yaml` for a full Vodafone network triage agent example.

## Development

### Adding a new code template

1. Add Jinja2 template to `yaml_to_sdk/templates/`
2. Update `generator.py` to reference it
3. Test with `python -m yaml_to_sdk --agent-yaml examples/vf_triage_agent.yaml --output-dir test_out --verify`

### Extending the YAML schema

1. Edit `yaml_to_sdk/schema.py`
2. Update `yaml_to_sdk/loader.py` validation logic
3. Add corresponding template changes

## Related Resources

- [Agent Framework SDK Docs](https://github.com/microsoft/agent-framework)
- [Foundry Agent Service API](https://aka.ms/foundry-agent-service)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [Azure Identity](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/identity/azure-identity)

## License

MIT - See LICENSE file for details
