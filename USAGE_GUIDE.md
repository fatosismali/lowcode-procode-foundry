# Foundry YAML → Agent Framework SDK: Usage Guide

Complete guide to using the cookie cutter template for transforming low-code Foundry YAML agent definitions into pro-code Python implementations.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Usage Workflow](#usage-workflow)
4. [YAML Schema Reference](#yaml-schema-reference)
5. [Generated Project Structure](#generated-project-structure)
6. [Customization](#customization)
7. [Deployment](#deployment)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 30-Second Start

```bash
# 1. Install the generator
pip install -r requirements.txt

# 2. Generate from example
python -m yaml_to_sdk --agent-yaml examples/vf_triage_agent.yaml --output-dir generated_agents

# 3. Setup and run
cd generated_agents/vf_triage_tool_agent
cp .env.example .env
# Edit .env with your Foundry credentials...
pip install -r requirements.txt
python src/orchestrator.py
```

That's it! Your agent is running.

---

## Installation

### Prerequisites

- Python 3.11 or higher
- pip or uv package manager
- Azure Subscription with Foundry project
- Foundry project connection string (from Azure Portal)

### Install the Template Generator

```bash
# Clone this repository
git clone https://github.com/Vodafone/foundry-yaml-to-sdk.git
cd foundry-yaml-to-sdk

# Install generator dependencies
pip install -r requirements.txt

# Or with uv (faster):
uv sync
```

### Verify Installation

```bash
python -m yaml_to_sdk --help
# Should show CLI help text
```

---

## Usage Workflow

### The Low-Code → Pro-Code Pipeline

```
┌────────────────────────────────────────────────────────────────────┐
│ YAML Agent Definition (Low Code)                                   │
│ ├─ Model selection                                                 │
│ ├─ System instructions                                             │
│ ├─ Tool definitions (function + MCP)                              │
│ └─ Configuration schema                                            │
└─────────────────────────────────┬────────────────────────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   YAML Loader & Validator  │
                    │   (validates against       │
                    │    Pydantic schema)        │
                    └─────────────┬──────────────┘
                                  │
         ┌────────────────────────▼────────────────────────┐
         │   Jinja2 Code Generator                          │
         │   ├─ orchestrator.py (main agent)               │
         │   ├─ models.py (type-safe I/O)                 │
         │   ├─ config.py (env management)                │
         │   ├─ tools/* (tool implementations)            │
         │   ├─ tests/* (pytest suite)                    │
         │   └─ deployment/* (Docker, pyproject.toml)     │
         └────────────────────────┬────────────────────────┘
                                  │
┌─────────────────────────────────▼────────────────────────────────┐
│ Python Agent Implementation (Pro Code)                            │
│ ├─ Full control over tool execution                              │
│ ├─ Type-safe Pydantic models with validation                     │
│ ├─ Structured logging and observability                          │
│ ├─ Async/await for performance                                   │
│ ├─ Ready for deployment (Docker, ACA, Foundry)                   │
│ └─ Complete test coverage with pytest                            │
└────────────────────────────────────────────────────────────────┘
```

### Step-by-Step Workflow

#### Step 1: Export Agent from Foundry

1. Go to [Azure AI Foundry](https://foundry.azure.com)
2. Navigate to your Agent Service agent
3. Click "Export" or view YAML definition
4. Save as `my_agent.yaml`

#### Step 2: Validate YAML (Optional)

```bash
python -c "from yaml_to_sdk import load_agent; load_agent('my_agent.yaml')"
# Should complete without errors
```

#### Step 3: Generate Python Project

```bash
python -m yaml_to_sdk \
    --agent-yaml my_agent.yaml \
    --output-dir generated_agents \
    --verify \
    --force

# Output:
# ✓ Agent project generated successfully
# ├── src/
# ├── tests/
# ├── pyproject.toml
# └── README.md
```

#### Step 4: Configure Environment

```bash
cd generated_agents/my_agent

# Copy template
cp .env.example .env

# Edit with your credentials
nano .env
# Set: FOUNDRY_PROJECT_CONNECTION_STRING=...
#      MODEL_NAME=gpt-5
# etc.
```

#### Step 5: Install Dependencies

```bash
pip install -r requirements.txt
# or:
uv sync
```

#### Step 6: Implement Tool Logic

Open `src/orchestrator.py` and replace tool implementations:

```python
async def _execute_my_tool(self, request: MyToolRequest) -> MyToolResponse:
    """Implement the actual tool logic."""
    # TODO: Replace this with real implementation
    # Example:
    result = await backend_api.call(request.param1)
    return MyToolResponse(status="success", data=result)
```

#### Step 7: Test Locally

```bash
# Run interactive
python src/orchestrator.py

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src
```

#### Step 8: Deploy

```bash
# Build container
docker build -t my-agent:latest .

# Push to ACR
az acr build --registry <acr> \
  --image my-agent:latest \
  -f Dockerfile .

# Deploy to Foundry
azd ai agent deploy
```

---

## YAML Schema Reference

### Complete Example

See `examples/vf_triage_agent.yaml` for a full example.

### Top-Level Schema

```yaml
# Required
name: agent-name                      # Agent identifier (becomes Python module name)
definition:                           # Agent definition block
  kind: prompt | hosted               # Agent type
  model: gpt-5                        # Model family
  instructions: |                     # Multi-line system prompt
    Agent instructions...
  tools: [...]                        # Tool definitions

# Recommended
description: "Agent description"      # Used in generated code
version: "1"                          # Agent version

# Optional
metadata:                             # Metadata
  description: "..."
  modified_at: "1234567890"
  microsoft.voice-live.enabled: false

status: active | inactive             # Agent status

# For hosted agents
instance_identity:
  principal_id: "..."                 # Managed identity principal
  client_id: "..."
```

### Tool Definition: Function

```yaml
- type: function
  name: my_tool                       # Tool name (must be valid Python identifier)
  description: "What this tool does"  # Description (appears in agent prompt)
  parameters:                         # JSON Schema
    type: object
    properties:
      param_name:
        type: string | number | boolean | object | array
        description: "Parameter description"
        enum: [...]                   # Optional: restricted values
    required: [param_name]            # Required parameters
    additionalProperties: false       # Strict: reject unknown params
  strict: true                        # Enforce strict validation
```

**Parameter Types:**

- `string` — Text parameter
- `number` — Numeric parameter
- `boolean` — True/false
- `object` — Nested object (requires `properties`)
- `array` — Array of items

**Examples:**

```yaml
# Simple string
param1:
  type: string
  description: "User input"

# Enum (restricted values)
action:
  type: string
  enum: [approve, reject, escalate]
  description: "Action to take"

# Nested object
data:
  type: object
  properties:
    nested_field:
      type: string
  required: [nested_field]

# Array
tags:
  type: array
  description: "List of tags"
```

### Tool Definition: MCP (Knowledge Base)

```yaml
- type: mcp
  server_label: kb_policies           # Knowledge base label
  server_url: "https://..."           # MCP server endpoint
  project_connection_id: kb-policies  # Foundry connection ID
```

### Reasoning Configuration

```yaml
definition:
  reasoning:
    effort: low | medium | high       # Reasoning complexity
    budget_tokens: 1000               # Optional: token budget
```

---

## Generated Project Structure

After running the generator, you get:

```
generated_agents/my_agent/
├── src/
│   ├── __init__.py
│   ├── orchestrator.py              # Main agent class (EDIT THIS)
│   ├── models.py                    # Pydantic type models (read-only)
│   ├── config.py                    # Configuration management (read-only)
│   └── tools/
│       ├── __init__.py              # Tool base classes
│       ├── tool_1.py                # Tool 1 implementation (EDIT THIS)
│       ├── tool_2.py                # Tool 2 implementation (EDIT THIS)
│       └── ...
├── tests/
│   ├── __init__.py
│   └── test_agent.py                # Pytest suite (EXTEND THIS)
├── pyproject.toml                   # Project metadata
├── requirements.txt                 # Dependencies
├── uv.lock                          # Locked dependencies (if using uv)
├── .env.example                     # Environment template (EDIT .env)
├── Dockerfile                       # Container build
├── .gitignore
└── README.md                        # Generated documentation
```

### Key Files

| File | Purpose | Edit? |
|------|---------|-------|
| `orchestrator.py` | Main agent entry point with tool binding | ✅ Yes |
| `models.py` | Pydantic request/response models | ❌ Read-only |
| `config.py` | Configuration and env loading | ❌ Read-only |
| `tools/*.py` | Tool implementations | ✅ Yes |
| `tests/test_agent.py` | Test suite | ✅ Extend |
| `.env.example` | Environment template | ✅ Copy to `.env` |
| `Dockerfile` | Container build | ✅ Customize if needed |
| `pyproject.toml` | Project metadata | ❌ Usually read-only |
| `README.md` | Documentation | ❌ Auto-generated |

---

## Customization

### Implementing Tool Logic

Each generated tool has a placeholder implementation:

```python
# src/orchestrator.py (auto-generated)
async def _execute_my_tool(self, request: MyToolRequest) -> MyToolResponse:
    """
    Execute my_tool.
    
    Tool description: "What this tool does"
    """
    self.logger.info(f"Executing tool: my_tool with request: {request}")
    
    try:
        # TODO: Implement tool logic
        # This is a placeholder that should be replaced with actual implementation
        
        result = {
            "status": "success",
            "data": {}
        }
        
        return MyToolResponse(**result)
    except Exception as e:
        self.logger.error(f"Tool execution failed: {e}", exc_info=True)
        return MyToolResponse(
            status="error",
            error=str(e)
        )
```

**Replace with real implementation:**

```python
async def _execute_my_tool(self, request: MyToolRequest) -> MyToolResponse:
    """Execute my_tool - Get incident from ITSM system."""
    self.logger.info(f"Looking up incident: {request.incident_id}")
    
    try:
        # Call real backend
        incident = await self.itsm_client.get_incident(request.incident_id)
        
        # Return typed response
        return MyToolResponse(
            status="success",
            data={
                "incident_id": incident.id,
                "site": incident.site,
                "summary": incident.summary,
                "severity": incident.severity,
            }
        )
    
    except NotFoundError as e:
        self.logger.warning(f"Incident not found: {request.incident_id}")
        return MyToolResponse(
            status="error",
            error=f"Incident {request.incident_id} not found"
        )
    
    except Exception as e:
        self.logger.error(f"ITSM lookup failed: {e}", exc_info=True)
        return MyToolResponse(
            status="error",
            error=f"Failed to look up incident: {str(e)}"
        )
```

### Adding Custom Configuration

Extend `config.py`:

```python
# src/config.py
class AgentConfig(BaseSettings):
    # Existing fields...
    
    # Add your custom fields:
    itsm_endpoint: str = Field(
        default="https://itsm.company.com",
        description="ITSM API endpoint"
    )
    
    itsm_api_key: str = Field(
        ...,  # Required
        description="ITSM API key (from Azure Key Vault)"
    )
    
    cache_ttl_seconds: int = Field(
        default=300,
        description="Cache TTL for incident lookups"
    )
    
    class Config:
        env_file = ".env"
        extra = "allow"
```

Update `.env`:

```bash
ITSM_ENDPOINT=https://itsm.company.com
ITSM_API_KEY=<your-api-key>
CACHE_TTL_SECONDS=300
```

### Adding Custom Tests

Extend `tests/test_agent.py`:

```python
# tests/test_agent.py
@pytest.mark.asyncio
async def test_get_incident_with_real_service(self):
    """Integration test with real ITSM service."""
    agent = MyAgent(config=AgentConfig.from_env())
    
    response = await agent._execute_get_incident(
        GetIncidentRequest(incident_id="INC-12345")
    )
    
    assert response.status == "success"
    assert response.data["incident_id"] == "INC-12345"
    assert "site" in response.data
```

### Adding Observability

Enable OpenTelemetry:

```python
# src/orchestrator.py
import logging
from opentelemetry import trace, metrics

tracer = trace.get_tracer(__name__)

async def _execute_my_tool(self, request: MyToolRequest) -> MyToolResponse:
    with tracer.start_as_current_span("my_tool") as span:
        span.set_attribute("incident_id", request.incident_id)
        
        try:
            # ... tool logic ...
            span.set_attribute("status", "success")
        except Exception as e:
            span.set_attribute("status", "error")
            span.set_attribute("error", str(e))
            raise
```

---

## Deployment

### Local Development

```bash
# Interactive mode
python src/orchestrator.py

# With debug logging
LOG_LEVEL=DEBUG python src/orchestrator.py

# Single message
python src/orchestrator.py "What is the status of incident INC-123?"
```

### Docker Container

```bash
# Build
docker build -t my-agent:latest .

# Run locally
docker run \
  -e FOUNDRY_PROJECT_CONNECTION_STRING=... \
  -e MODEL_NAME=gpt-5 \
  my-agent:latest

# Push to ACR
az acr build --registry <acr> \
  --image my-agent:latest \
  -f Dockerfile .
```

### Azure Container Apps

```bash
az containerapp create \
  --resource-group <rg> \
  --name my-agent \
  --image <acr>.azurecr.io/my-agent:latest \
  --environment <env> \
  --env-vars \
    FOUNDRY_PROJECT_CONNECTION_STRING="..." \
    MODEL_NAME="gpt-5" \
  --cpu 1 \
  --memory 2.0Gi
```

### Microsoft Foundry Deployment

```bash
# Using azd
azd ai agent deploy

# Or manually
az acr build --registry <acr> \
  --image my-agent:v1.0.0 \
  -f Dockerfile .

# Update agent version in Foundry portal
# or via API:
az rest --method PUT \
  --uri "/subscriptions/.../resourceGroups/.../providers/Microsoft.AI/projects/.../agents/my-agent:1" \
  --body @agent-version.json
```

---

## Troubleshooting

### Generator Issues

#### "Cannot find template"

```
FileNotFoundError: No such file or directory: 'templates/orchestrator.py.j2'
```

**Solution:** Ensure you're in the right directory:

```bash
pwd
# Should show: .../foundry-yaml-to-sdk

ls yaml_to_sdk/templates/
# Should list: *.j2 files
```

#### "Invalid YAML"

```
yaml.YAMLError: Failed to parse YAML: ...
```

**Solution:** Validate YAML syntax:

```bash
python -c "import yaml; yaml.safe_load(open('my_agent.yaml'))"

# Or use online validator:
# https://www.yamllint.com/
```

#### Pydantic validation error

```
ValidationError: Agent definition validation failed
```

**Solution:** Check YAML schema:

```bash
python -c "from yaml_to_sdk import load_agent; load_agent('my_agent.yaml', strict=True)"
# Shows detailed validation errors
```

### Runtime Issues

#### 401 Unauthorized

**Cause:** Azure authentication failed

**Solution:**

```bash
# Check current login
az account show

# Re-login
az logout
az login

# Verify Foundry connection string
echo $FOUNDRY_PROJECT_CONNECTION_STRING
# Should be: https://<project>.projects.ai.azure.com/...
```

#### Model not found

**Cause:** Model not deployed in Foundry project

**Solution:**

```bash
# List available models
az ai project list-models \
  --resource-group <rg> \
  --name <project>

# Update .env
MODEL_NAME=<available-model>
```

#### Tool timeout

**Cause:** Tool execution exceeds timeout

**Solution:**

```bash
# Increase timeout in .env
TOOL_TIMEOUT_SECONDS=60

# Or in code:
config = AgentConfig(tool_timeout_seconds=60)
```

### Docker Issues

#### "Cannot find Dockerfile"

**Solution:**

```bash
# Check path
ls generated_agents/my_agent/Dockerfile

# Build from correct directory
cd generated_agents/my_agent
docker build -t my-agent:latest .
```

#### "Port 8000 already in use"

**Solution:**

```bash
# Use different port
docker run -p 8001:8000 my-agent:latest
```

---

## Advanced Topics

### Custom MCP Server Integration

If you want to use a custom MCP server:

```python
# src/orchestrator.py
from agent_framework.tools import MCPClientTool

async def _initialize_agent(self) -> Agent:
    # ... existing code ...
    
    # Add MCP tool
    mcp_tool = MCPClientTool(
        name="custom_kb",
        server_url=self.config.mcp_server_url,
        project_connection_id=self.config.mcp_project_connection_id,
    )
    
    tools.append(mcp_tool)
    
    return Agent(...)
```

### Multi-Turn Conversations

```python
# src/orchestrator.py
async def run_multi_turn(self):
    """Multi-turn conversation with state management."""
    agent = await self._initialize_agent()
    messages = []
    
    while True:
        user_input = input("You: ")
        messages.append(ChatMessage(
            role=ChatMessageRoleType.USER,
            content=user_input
        ))
        
        response = await agent.invoke(messages=messages)
        assistant_message = response.messages[-1]
        messages.append(assistant_message)
        
        print(f"Agent: {assistant_message.content}")
```

### Batch Processing

```python
# Invoke agent on multiple inputs
import asyncio

async def batch_process(agent, incidents: list[str]):
    """Process multiple incidents in parallel."""
    tasks = [
        agent.run_conversation(f"Triage incident: {incident}")
        for incident in incidents
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

---

## Support

- **Documentation:** See `README_TEMPLATE.md` and generated `README.md`
- **Examples:** Check `examples/` directory
- **Issues:** Open issue on GitHub
- **Discord:** Join Foundry community Discord

---

**Ready to build?** Start with the [Quick Start](#quick-start) section! 🚀
