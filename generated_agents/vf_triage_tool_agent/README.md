# VfTriageToolAgent - Agent Framework SDK

Agent: vf-triage-tool-agent

## Overview

This is a production-ready Agent Framework SDK implementation of the **vf-triage-tool-agent** agent.

- **Model**: gpt-5
- **Tools**: 5
- **Reasoning**: low

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Foundry credentials
```

### 3. Run the Agent

```bash
python src/orchestrator.py
```

## Architecture

```
src/
├── orchestrator.py      Main agent implementation
├── models.py            Type-safe Pydantic models
├── config.py            Configuration management
├── tools_base.py        Tool base classes
└── tools/               Tool implementations

tests/
└── test_agent.py        Comprehensive test suite
```

## Configuration

See `.env.example` for all available configuration options.

### Required Settings

- `FOUNDRY_PROJECT_CONNECTION_STRING` - Your Foundry project connection string

### Optional Settings

- `MODEL_NAME` - Model to use (default: gpt-5)
- `REASONING_EFFORT` - Reasoning level: low|medium|high (default: low)
- `LOG_LEVEL` - Logging level (default: INFO)

## Tools

### Function Tools

- **get_incident** - Look up an ITSM incident by ID and return its site and summary.
  - Location: `src/orchestrator.py::_execute_get_incident`
  - Status: TODO - needs implementation

- **fetch_telemetry** - Fetch the latest RAN telemetry snapshot for a cell site.
  - Location: `src/orchestrator.py::_execute_fetch_telemetry`
  - Status: TODO - needs implementation

- **fetch_customer_impact** - Return CRM impact (affected customers by tier) for a cell site.
  - Location: `src/orchestrator.py::_execute_fetch_customer_impact`
  - Status: TODO - needs implementation

- **apply_change** - Apply a corrective change to the network. Refuses unless approved=true. Use this once you have decided the action.
  - Location: `src/orchestrator.py::_execute_apply_change`
  - Status: TODO - needs implementation


### Knowledge Base / MCP Tools

- **kb_regulationpolciies_ziw96** - Knowledge base: kb_regulationpolciies_ziw96
  - Server: `https://msagthack-search-mzloe6z4nnwoc.search.windows.net/knowledgebases/regulationpolciies/mcp?api-version=2025-11-01-Preview`
  - Connection: `kb-regulationpolciies-ziw96`


## Development

### Run Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### Format Code

```bash
# Black
black src/ tests/

# isort
isort src/ tests/

# Ruff
ruff check --fix src/ tests/
```

### Type Checking

```bash
mypy src/
```

## Implementing Tools

To implement a tool, edit the corresponding method in `src/orchestrator.py`:

```python
async def _execute_my_tool(self, param1: str = None, param2: str = None) -> dict:
    """Implementation for: my_tool"""
    # Add your implementation here
    return {
        "status": "success",
        "data": {"result": "..."}
    }
```

## Deployment

### Docker

```bash
# Build
docker build -t vf_triage_tool_agent:latest .

# Run
docker run \
    --env-file .env \
    -p 8000:8000 \
    vf_triage_tool_agent:latest
```

### Azure Container Apps

```bash
# Build and push to ACR
az acr build \
    --registry <acr-name> \
    --image vf_triage_tool_agent:latest \
    -f Dockerfile .

# Deploy to ACA
azd ai agent deploy
```

### Foundry Agent Service

1. Build Docker image
2. Push to ACR
3. Create Foundry agent from container image
4. Configure environment variables
5. Deploy

## Monitoring & Logging

The agent uses structured logging with JSON output.

View logs:

```bash
# Local
python src/orchestrator.py

# Container
docker logs <container-id>

# Azure Container Apps
az containerapp logs show \
    --resource-group <rg> \
    --name vf_triage_tool_agent
```

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'agent_framework'`

**Solution**: Install dependencies

```bash
pip install -r requirements.txt
```

### Issue: `FOUNDRY_PROJECT_CONNECTION_STRING not found`

**Solution**: Create and populate `.env` file

```bash
cp .env.example .env
# Edit with your credentials
```

### Issue: Authentication fails

**Solution**: Check Foundry credentials and ensure proper Azure authentication

```bash
# Verify Azure login
az account show
```

## Testing

The generated test suite includes:

- Agent initialization tests
- Configuration validation
- Tool execution tests (with mocks)
- Model validation
- Integration tests

To run tests:

```bash
pytest tests/ -v
```

To add custom tests, edit `tests/test_agent.py`.

## Related Documentation

- [Agent Framework Documentation](https://github.com/microsoft/agent-framework)
- [Azure AI Foundry](https://learn.microsoft.com/azure/ai-studio)
- [Pydantic Docs](https://docs.pydantic.dev)

## Support

For issues or questions:

1. Check troubleshooting section above
2. Review test suite for examples
3. Check logs for detailed error messages
4. Open an issue in your repository

## License

MIT