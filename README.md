# Foundry YAML → Agent Framework SDK

A cookie cutter template system for transforming **low-code** YAML agent definitions from Microsoft Foundry Agent Service into **pro-code** Python implementations using the Microsoft Agent Framework SDK.

**Low Code** → **Pro Code** →  **Production**

```
YAML Agent Definition    Python Agent Implementation    Deployed Agent
    (Foundry)                (Agent Framework)           (Production)
         │                           │                         │
    Model selection        Type-safe tool orchestration   Scalable runtime
    Tool definitions       Pydantic data validation       Full observability
    Instructions           Async/await architecture       Enterprise features
         │                           │                         │
         └───────────────────────────┴──────────────────────────┘
              Automated Code Generation Pipeline
```

## 🎯 Quick Start

**30 seconds to a working agent:**

```bash
# 1. Install
pip install -r requirements.txt

# 2. Generate Python code from YAML
python -m yaml_to_sdk \
    --agent-yaml examples/vf_triage_agent.yaml \
    --output-dir generated_agents

# 3. Configure and run
cd generated_agents/vf_triage_tool_agent
cp .env.example .env
# Edit .env with your Foundry credentials...
pip install -r requirements.txt
python src/orchestrator.py

# 4. You have a working agent!
```

For detailed walkthrough, see [USAGE_GUIDE.md](USAGE_GUIDE.md).

---

## ✨ Features

### Low-Code ← → Pro-Code Bridge

| Aspect | Low-Code (YAML) | Pro-Code (Python) |
|--------|-----------------|-------------------|
| **Definition** | Declarative YAML | Full programmatic control |
| **Model** | Simple string | Pluggable model client |
| **Tools** | Schema definitions | Type-safe implementations |
| **Logic** | System instructions | Full Python async code |
| **Testing** | Manual | Comprehensive pytest suite |
| **Deployment** | Portal UI | Container + Infrastructure as Code |

### Generated Agent Features

✅ **Type Safety** — Pydantic models for all tool I/O  
✅ **Async/Await** — Full async support for performance  
✅ **Observability** — Structured logging + OpenTelemetry ready  
✅ **Error Handling** — Comprehensive exception handling  
✅ **Configuration** — Environment-driven, flexible  
✅ **Testing** — Auto-generated pytest suite  
✅ **Deployment** — Docker + Foundry ready  
✅ **Documentation** — Auto-generated README  

### Supported YAML Features

| Feature | Status | Notes |
|---------|--------|-------|
| Function tools | ✅ Full | Strict schema, auto type generation |
| MCP servers | ✅ Full | Knowledge base integration |
| System instructions | ✅ Full | Multi-line, variable support |
| Model selection | ✅ Full | GPT-5, GPT-4, custom deployments |
| Tool orchestration | ✅ Full | Sequential + parallel execution |
| Reasoning params | ✅ Full | Effort levels (low/medium/high) |
| Instance identity | ✅ Full | UAMI for hosted agents |
| Metadata | ✅ Full | Versioning, descriptions |

---

## 📁 Directory Structure

```
foundry-yaml-to-sdk/
├── yaml_to_sdk/                     # Template generator
│   ├── __init__.py
│   ├── __main__.py                  # CLI entry point
│   ├── loader.py                    # YAML loader & validator
│   ├── generator.py                 # Python code generator
│   ├── schema.py                    # Pydantic schema definitions
│   └── templates/                   # Jinja2 templates
│       ├── orchestrator.py.j2       # Main agent implementation
│       ├── models.py.j2             # Type definitions
│       ├── config.py.j2             # Configuration management
│       ├── tools_base.py.j2         # Tool base classes
│       ├── pyproject.toml.j2        # Project metadata
│       ├── test_agent.py.j2         # Test suite
│       ├── env.example.j2           # Environment template
│       ├── Dockerfile.j2            # Container build
│       └── README.md.j2             # Generated README
├── examples/                        # Example YAML definitions
│   ├── vf_triage_agent.yaml        # Vodafone triage agent example
│   └── README.md                   # Examples documentation
├── README.md                        # This file
├── README_TEMPLATE.md               # Template overview
├── USAGE_GUIDE.md                   # Comprehensive usage guide
├── cookiecutter.json                # Cookie cutter config
├── pyproject.toml                   # Generator project metadata
└── requirements.txt                 # Generator dependencies
```

---

## 🔄 The Three-Step Workflow

### Step 1: Export YAML (Low Code)

Export your agent from Foundry Agent Service:

```yaml
# my_agent.yaml
name: my-triage-agent
definition:
  kind: prompt
  model: gpt-5
  instructions: |
    You are an expert network triage agent.
    For each incident:
      1. Get incident details
      2. Fetch telemetry
      3. Decide root cause
      4. Apply fix
  tools:
    - type: function
      name: get_incident
      description: Get ITSM incident details
      parameters: { ... }
    - type: function
      name: fetch_telemetry
      description: Get RAN telemetry
      parameters: { ... }
    - type: mcp
      server_label: kb_policies
      server_url: "https://..."
```

### Step 2: Generate Python Code (Automatic)

The generator transforms YAML into production-ready Python:

```bash
python -m yaml_to_sdk \
    --agent-yaml my_agent.yaml \
    --output-dir generated_agents \
    --verify
```

Generated structure:

```
generated_agents/my_triage_agent/
├── src/orchestrator.py              # Agent main class
├── src/models.py                    # Pydantic types
├── src/config.py                    # Configuration
├── src/tools/__init__.py            # Tool base classes
├── tests/test_agent.py              # Test suite
├── pyproject.toml
├── Dockerfile
└── README.md
```

### Step 3: Implement & Deploy (Pro Code)

Customize tool logic and deploy:

```python
# src/orchestrator.py (PRO CODE - your implementation)
async def _execute_get_incident(self, request: GetIncidentRequest):
    # Your backend integration
    incident = await self.itsm_client.get_incident(request.incident_id)
    return GetIncidentResponse(
        status="success",
        data={...}
    )
```

Then deploy:

```bash
docker build -t my-agent:latest .
az acr build --registry <acr> --image my-agent:latest -f Dockerfile .
azd ai agent deploy
```

---

## 🛠️ How It Works

### The Code Generation Pipeline

```
YAML File
    ↓
┌───────────────────┐
│  YAML Loader      │  ← Validates against Pydantic schema
│  (loader.py)      │  ← Handles YAML/JSON
└────────┬──────────┘
         ↓
┌───────────────────────────────┐
│  FoundryAgentDefinition       │  ← Fully typed, validated
│  (Pydantic model)             │
└────────┬──────────────────────┘
         ↓
┌───────────────────────────────┐
│  AgentCodeGenerator           │  ← Extracts context
│  (generator.py)               │  ← Prepares template vars
└────────┬──────────────────────┘
         ↓
┌───────────────────────────────┐
│  Jinja2 Templates             │  ← Renders Python code
│  (templates/*.j2)             │  ← Creates project structure
└────────┬──────────────────────┘
         ↓
    Python Project
    (ready to run)
```

### Schema Validation

Pydantic models validate:
- ✅ Required fields are present
- ✅ Field types are correct
- ✅ Tool definitions are valid
- ✅ Parameter schemas are well-formed
- ✅ Naming conventions are followed

```python
# If YAML is invalid, you get clear errors:
ValidationError: Agent definition validation failed
├── definition.tools.0.name: value must be a valid Python identifier
├── definition.tools.0.parameters.properties.param1.type: unsupported type 'foo'
└── ...
```

---

## 📚 Documentation

1. **[USAGE_GUIDE.md](USAGE_GUIDE.md)** — Complete usage walkthrough
2. **[README_TEMPLATE.md](README_TEMPLATE.md)** — Template overview
3. **[examples/README.md](examples/README.md)** — Example reference
4. **[examples/vf_triage_agent.yaml](examples/vf_triage_agent.yaml)** — Complete example

---

## 🚀 Getting Started

### Installation

```bash
# Clone repository
git clone https://github.com/Vodafone/foundry-yaml-to-sdk.git
cd foundry-yaml-to-sdk

# Install generator
pip install -r requirements.txt

# Verify
python -m yaml_to_sdk --help
```

### Generate Your First Agent

```bash
# Use example
python -m yaml_to_sdk \
    --agent-yaml examples/vf_triage_agent.yaml \
    --output-dir generated_agents

# Setup generated agent
cd generated_agents/vf_triage_tool_agent
pip install -r requirements.txt
cp .env.example .env

# Configure
nano .env
# Set FOUNDRY_PROJECT_CONNECTION_STRING=...

# Run
python src/orchestrator.py
```

### Customize for Your Agent

1. **Export your YAML** from Foundry Agent Service
2. **Generate Python code** with the generator
3. **Implement tool logic** in `src/orchestrator.py`
4. **Write tests** in `tests/test_agent.py`
5. **Deploy** as container or to Foundry

---

## 🔧 Configuration

### CLI Options

```bash
python -m yaml_to_sdk [OPTIONS]

Input modes (choose one):
  --agent-yaml PATH              Single agent: path to one agent YAML
  --team-yaml PATH               Team: orchestration YAML referencing agents
  --agents A.yaml B.yaml ...     Team: agent files (use with --pattern)
  --pattern PATTERN              sequential | concurrent | group_chat | handoff
  --name NAME                    Team name (with --agents)

Options:
  --output-dir PATH              Output directory (default: ./generated_agents)
  --verify                       Verify generated code syntax
  --force                        Overwrite existing output
  -v, --verbose                  Enable verbose logging
  --help                         Show help
```

### Multi-agent orchestration (teams)

Share several agent YAML files — each defining one declarative agent — and pick
an orchestration pattern. The generator wires them into the matching
[Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/)
orchestration, following the
[Azure AI agent orchestration patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns).

| Pattern | Behaviour | Best for |
| --- | --- | --- |
| `sequential` | Pipeline; each agent processes the previous output | Step-by-step refinement with clear dependencies |
| `concurrent` | All agents run in parallel; results aggregated | Independent perspectives, latency-sensitive work |
| `group_chat` | Shared conversation with a chat manager | Consensus-building, maker-checker validation |
| `handoff` | Control transfers dynamically between agents | The right specialist emerges during processing |

```bash
# From a team YAML that references the agent files
python -m yaml_to_sdk --team-yaml examples/vf_triage_team.yaml --output-dir generated_agents

# Or straight from agent files + a pattern
python -m yaml_to_sdk \
    --agents examples/vf_triage_agent.yaml examples/vf_comms_agent.yaml \
    --pattern sequential --name vf-triage-team \
    --output-dir generated_agents
```

Generated team layout:

```
<team>/
  src/
    orchestrator.py     # wires the chosen pattern (edit build_workflow)
    config.py
    agents/<agent>.py   # one factory per agent (implement tool bodies)
  tests/test_team.py
```

### Environment Variables

Generated agents read configuration from `.env`:

```bash
# Required
FOUNDRY_PROJECT_CONNECTION_STRING=<your-connection-string>

# Recommended
MODEL_NAME=gpt-5
LOG_LEVEL=INFO

# Optional
TOOL_TIMEOUT_SECONDS=30
MAX_TOOL_CALLS=10
ENABLE_TRACING=false
```

---

## 🧪 Testing

### Run Generator Tests

```bash
pytest tests/ -v

# With coverage
pytest tests/ --cov=yaml_to_sdk --cov-report=html
```

### Test Generated Agents

```bash
cd generated_agents/my_agent
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

---

## 📦 Deployment

### Local Development

```bash
# Interactive
python src/orchestrator.py

# With debug logging
LOG_LEVEL=DEBUG python src/orchestrator.py

# Single message
python src/orchestrator.py "Your message"
```

### Docker

```bash
# Build
docker build -t my-agent:latest .

# Run
docker run -e FOUNDRY_PROJECT_CONNECTION_STRING=... my-agent:latest
```

### Azure Container Apps

```bash
az containerapp create \
  --resource-group <rg> \
  --name my-agent \
  --image <acr>.azurecr.io/my-agent:latest \
  --environment <env>
```

### Microsoft Foundry

```bash
# Deploy with azd
azd ai agent deploy

# Or manually with Azure CLI
az acr build --registry <acr> \
  --image my-agent:v1.0.0 \
  -f Dockerfile .
```

---

## 🤝 Contributing

Contributions welcome! Areas for contribution:

- [ ] Additional template generators (FastAPI, Flask)
- [ ] Enhanced YAML schema support
- [ ] Performance optimizations
- [ ] Documentation improvements
- [ ] Test coverage expansion

---

## 📄 License

MIT - See LICENSE file for details

---

## 🆘 Support & Troubleshooting

### Common Issues

**Q: Generator error "Cannot find template"**  
A: Ensure you're in the correct directory. Check `yaml_to_sdk/templates/` exists.

**Q: Generated code won't import**  
A: Install dependencies: `pip install -r requirements.txt`

**Q: 401 Unauthorized when running agent**  
A: Verify Azure credentials and Foundry connection string in `.env`

**Q: Tool timeout**  
A: Increase timeout: `TOOL_TIMEOUT_SECONDS=60` in `.env`

For more, see [USAGE_GUIDE.md#troubleshooting](USAGE_GUIDE.md#troubleshooting).

---

## 📞 Contact & Community

- **Issues:** GitHub Issues
- **Discussions:** GitHub Discussions
- **Email:** ai@vodafone.com
- **Documentation:** [Agent Framework Docs](https://github.com/microsoft/agent-framework)

---

## 🎓 Learning Resources

- [Agent Framework Documentation](https://github.com/microsoft/agent-framework)
- [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-studio/)
- [Pydantic Validation](https://docs.pydantic.dev/)
- [Jinja2 Templates](https://jinja.palletsprojects.com/)
- [Model Context Protocol](https://modelcontextprotocol.io/)

---

## 🚀 Next Steps

1. **Read** [USAGE_GUIDE.md](USAGE_GUIDE.md) for complete walkthrough
2. **Try** the example: `python -m yaml_to_sdk --agent-yaml examples/vf_triage_agent.yaml --output-dir generated_agents`
3. **Export** your agent from Foundry Agent Service
4. **Generate** Python code for your agent
5. **Implement** tool logic
6. **Deploy** to production

---

**Built with ❤️ for Vodafone AI & Enterprise Agents**

Happy agent building! 🎉
