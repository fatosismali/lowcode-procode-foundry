# Getting Started with Foundry YAML → Agent Framework SDK Template

This directory contains example YAML agent definitions that can be transformed into Python Agent Framework SDK implementations.

## Files

### `vf_triage_agent.yaml`

**Vodafone Network Triage Agent** — A complete example agent that demonstrates:
- Multi-step tool orchestration (get_incident → fetch_telemetry → fetch_customer_impact → apply_change)
- Decision logic based on telemetry data
- Knowledge base integration (MCP server for regulatory policies)
- Strict parameter validation
- Complex business logic in instructions

**Use this to:**
1. Understand the YAML schema
2. Test the code generator
3. Reference for your own agent definitions

## Generating Python Code

### From `vf_triage_agent.yaml`:

```bash
cd ..  # Go to project root

# Generate the agent
python -m yaml_to_sdk \
    --agent-yaml examples/vf_triage_agent.yaml \
    --output-dir generated_agents \
    --verify

# This creates: generated_agents/vf_triage_tool_agent/
```

### Output Structure

```
generated_agents/vf_triage_tool_agent/
├── src/
│   ├── __init__.py
│   ├── orchestrator.py          # Main {{agent_class}} implementation
│   ├── models.py                # Type-safe Pydantic models
│   ├── config.py                # Configuration management
│   └── tools/
│       ├── __init__.py
│       ├── get_incident.py      # Tool implementation
│       ├── fetch_telemetry.py   # Tool implementation
│       ├── fetch_customer_impact.py  # Tool implementation
│       └── apply_change.py      # Tool implementation
├── tests/
│   ├── __init__.py
│   └── test_agent.py            # Comprehensive pytest suite
├── pyproject.toml               # Project metadata
├── requirements.txt             # Dependencies
├── .env.example                 # Environment template
├── Dockerfile                   # Container build
└── README.md                    # Full documentation
```

## Key Features in Generated Code

### Type Safety with Pydantic

All tools have strict type validation:

```python
# models.py (auto-generated)
class GetIncidentRequest(BaseModel):
    incident_id: str = Field(..., description="Incident ID, e.g. INC-4291")

class GetIncidentResponse(BaseModel):
    status: str
    data: Optional[Dict[str, Any]]
    error: Optional[str]
```

### Tool Orchestration

The orchestrator automatically binds tools:

```python
# orchestrator.py (auto-generated)
@Tool(name="get_incident", description="Look up an ITSM incident...")
async def get_incident(incident_id: str):
    request = GetIncidentRequest(incident_id=incident_id)
    return await self._execute_get_incident(request)
```

### Configuration Management

Environment-driven config with type validation:

```python
# config.py (auto-generated)
class AgentConfig(BaseSettings):
    foundry_project_connection_string: str  # Required
    model_name: str = Field(default="gpt-5")
    reasoning_effort: str = Field(default="low")
    # ... all config from YAML is generated

config = AgentConfig.from_env()  # Loads from .env
```

## Workflow: Low Code → Pro Code

### Step 1: Define Agent in YAML (Low Code)

```yaml
# my_agent.yaml
name: my-agent
definition:
  kind: prompt
  model: gpt-5
  instructions: "Agent instructions..."
  tools:
    - type: function
      name: my_tool
      description: "Tool description"
      parameters:
        type: object
        properties:
          param1: {type: string}
        required: [param1]
```

### Step 2: Generate Python Code (Automatic)

```bash
python -m yaml_to_sdk --agent-yaml my_agent.yaml --output-dir generated_agents
```

### Step 3: Implement Tool Logic (Pro Code)

```python
# generated_agents/my_agent/src/orchestrator.py
async def _execute_my_tool(self, request: MyToolRequest) -> MyToolResponse:
    # TODO: Replace with actual implementation
    # Example: Call your backend APIs, databases, etc.
    
    result = await backend.process(request.param1)
    return MyToolResponse(status="success", data=result)
```

### Step 4: Test & Deploy

```bash
cd generated_agents/my_agent

# Configure
cp .env.example .env
# Edit .env with your Foundry credentials

# Test
pytest tests/ -v

# Deploy
docker build -t my-agent:latest .
az acr build --registry <acr> --image my-agent:latest -f Dockerfile .
```

## YAML Schema Reference

### Required Top-Level Fields

```yaml
name: agent-name                    # Agent identifier
definition:                         # Agent definition
  kind: prompt                      # Type: 'prompt' or 'hosted'
  model: gpt-5                      # Model family
  instructions: |                   # System prompt (multi-line)
    Agent instructions...
  tools: [...]                      # Tool definitions
```

### Optional Top-Level Fields

```yaml
metadata:                           # Metadata
  description: "..."               # Description
version: "1"                        # Version number
status: active                      # Status: active/inactive
instance_identity:                  # UAMI identity info
  principal_id: "..."
  client_id: "..."
```

### Tool Definition: Function

```yaml
- type: function
  name: tool_name                   # Unique tool identifier
  description: "What it does"       # User-facing description
  parameters:
    type: object
    properties:
      param1:
        type: string                # JSON schema type
        description: "Parameter description"
    required: [param1]              # Required parameters
    additionalProperties: false     # Strict validation
  strict: true                      # Enforce strict schema
```

### Tool Definition: MCP (Knowledge Base)

```yaml
- type: mcp
  server_label: kb_example          # Knowledge base label
  server_url: "https://..."         # MCP endpoint URL
  project_connection_id: kb-example # Foundry connection ID
```

## Customization Guide

### Adding Custom Tool Logic

1. Open generated `orchestrator.py`
2. Find `_execute_<tool_name>()` method
3. Replace TODO with actual implementation:

```python
async def _execute_get_incident(self, request: GetIncidentRequest) -> GetIncidentResponse:
    """Real implementation of get_incident tool."""
    try:
        # Call your ITSM API
        incident = await self.itsm_client.get_incident(request.incident_id)
        
        return GetIncidentResponse(
            status="success",
            data={
                "incident_id": incident.id,
                "site": incident.site,
                "summary": incident.summary,
            }
        )
    except Exception as e:
        return GetIncidentResponse(status="error", error=str(e))
```

### Adding Observability

The generated code is already instrumented for OpenTelemetry:

```bash
# Enable tracing
ENABLE_TRACING=true \
APPINSIGHTS_CONNECTION_STRING=... \
python src/orchestrator.py
```

Traces automatically capture:
- Tool invocations and results
- Conversation turns
- Errors and exceptions
- Latency metrics

### Adding Custom Tests

```python
# tests/test_agent.py
@pytest.mark.asyncio
async def test_get_incident_happy_path(self, agent):
    """Test get_incident with valid input."""
    response = await agent._execute_get_incident(
        GetIncidentRequest(incident_id="INC-123")
    )
    assert response.status == "success"
    assert response.data["site"] == "MAN-372"
```

## Troubleshooting

### Generator Error: "Cannot find template"

**Cause:** Template files not in correct location

**Fix:** Ensure templates are in `yaml_to_sdk/templates/`:
```bash
ls yaml_to_sdk/templates/
# Should show: orchestrator.py.j2, models.py.j2, config.py.j2, etc.
```

### Generated Code Won't Import

**Cause:** Missing dependencies

**Fix:**
```bash
cd generated_agents/vf_triage_tool_agent
pip install -r requirements.txt
```

### Tool Returns 401 Unauthorized

**Cause:** Azure authentication failure

**Fix:**
```bash
# Verify login
az account show

# Reset credentials
az logout && az login
```

## Performance Tips

### For High-Throughput Agents

1. **Increase connection pool:**
   ```python
   # config.py
   http_connection_pool_size = 100
   ```

2. **Enable async batching:**
   ```python
   # orchestrator.py
   tasks = [self._execute_tool1(...), self._execute_tool2(...)]
   results = await asyncio.gather(*tasks)
   ```

3. **Use LRU caching:**
   ```python
   from functools import lru_cache
   
   @lru_cache(maxsize=1000)
   def _cache_lookup(key: str) -> str:
       return lookup(key)
   ```

## Next Steps

1. **Review the generated code** — Start with generated `README.md`
2. **Implement tool logic** — Replace TODO in `orchestrator.py`
3. **Add tests** — Extend `tests/test_agent.py`
4. **Deploy** — Use Dockerfile or `azd ai agent deploy`
5. **Monitor** — Check Application Insights for traces

## Related Resources

- [Agent Framework Documentation](https://github.com/microsoft/agent-framework)
- [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-studio/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

---

**Questions?** Check the generated `README.md` in your project or the main template README.
