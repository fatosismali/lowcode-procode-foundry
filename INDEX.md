# Foundry YAML → Agent Framework SDK - Complete Documentation Index

Welcome! This document serves as a navigation guide to all documentation in this cookie cutter template system.

## 📖 Documentation Map

### Starting Out

**New to this template?** Start here:

1. **[README.md](README.md)** — Start here! Overview, quick start (30 seconds), and feature highlights
   - What the template does
   - Feature comparison (low-code vs pro-code)
   - 3-step quick start
   - File structure overview

2. **[SUMMARY.md](SUMMARY.md)** — Complete summary of what was created
   - What was built
   - How it works
   - Key design decisions
   - Next steps

### Learning the System

**Want to understand how it works?** Read in this order:

1. **[USAGE_GUIDE.md](USAGE_GUIDE.md)** — Comprehensive usage guide (2000+ lines)
   - Complete 8-step workflow
   - YAML schema reference
   - Generated project structure
   - Customization examples
   - Deployment patterns
   - Troubleshooting section

2. **[ARCHITECTURE.md](ARCHITECTURE.md)** — System design and architecture
   - Component architecture (4 modules)
   - Template structure (9 templates)
   - Data flow diagrams
   - Design patterns used
   - Extensibility points
   - Security considerations

3. **[END_TO_END_WORKFLOW.md](END_TO_END_WORKFLOW.md)** — Low-code → pro-code lifecycle
   - Foundry authoring → YAML hand-off → orchestration → code gen
   - Evaluation gates and CI/CD path to production
   - Change management, versioning, and how a low-code change propagates

3. **[README_TEMPLATE.md](README_TEMPLATE.md)** — Template overview and features
   - Features and benefits
   - Tool support matrix
   - YAML format details
   - Generated code structure

### Working with Examples

**Want to see it in action?** Check the examples:

1. **[examples/vf_triage_agent.yaml](examples/vf_triage_agent.yaml)** — Complete example from your Vodafone agent
   - Full YAML definition
   - Multi-tool orchestration
   - MCP knowledge base integration
   - Can be used with generator directly

2. **[examples/README.md](examples/README.md)** — Examples and getting started guide
   - How to use the example
   - Generating from example
   - Output structure
   - Customization walkthrough

### Configuration & Deployment

**Need to configure or deploy?** See:

1. **[USAGE_GUIDE.md#yaml-schema-reference](USAGE_GUIDE.md#yaml-schema-reference)** — Complete YAML schema documentation
2. **[USAGE_GUIDE.md#deployment](USAGE_GUIDE.md#deployment)** — Deployment patterns and examples
3. **[USAGE_GUIDE.md#troubleshooting](USAGE_GUIDE.md#troubleshooting)** — Troubleshooting guide

---

## 🗂️ Project Structure

### Core Generator

```
foundry-yaml-to-sdk/
├── yaml_to_sdk/                    # Main generator module
│   ├── __init__.py                 # Package init
│   ├── __main__.py                 # CLI entry point
│   ├── loader.py                   # YAML/JSON loader
│   ├── schema.py                   # Pydantic schemas
│   ├── generator.py                # Code generator
│   └── templates/                  # Jinja2 templates
│       ├── orchestrator.py.j2      # Main agent
│       ├── models.py.j2            # Type models
│       ├── config.py.j2            # Configuration
│       ├── tools_base.py.j2        # Tool base classes
│       ├── pyproject.toml.j2       # Project metadata
│       ├── test_agent.py.j2        # Test suite
│       ├── env.example.j2          # Environment template
│       ├── Dockerfile.j2           # Container
│       └── README.md.j2            # Documentation
```

### Documentation

```
Documentation Files
├── README.md                       # Main overview (START HERE)
├── README_TEMPLATE.md              # Template features
├── USAGE_GUIDE.md                  # Comprehensive guide (2000+ lines)
├── ARCHITECTURE.md                 # System design
├── SUMMARY.md                      # What was created
├── cookiecutter.json               # Cookie cutter config
├── pyproject.toml                  # Generator metadata
├── requirements.txt                # Generator dependencies
└── .gitignore                      # Git ignore patterns
```

### Examples

```
examples/
├── vf_triage_agent.yaml            # Vodafone example
└── README.md                       # Examples guide
```

---

## 🚀 Common Tasks

### Task: Generate an Agent

**Goal:** Transform YAML into Python code

1. Prepare YAML file from Foundry Agent Service
2. Run: `python -m yaml_to_sdk --agent-yaml my_agent.yaml --output-dir generated_agents`
3. See: [USAGE_GUIDE.md#step-by-step-workflow](USAGE_GUIDE.md#step-by-step-workflow)

### Task: Understand the Generated Code

**Goal:** Learn what was generated

1. Review: [USAGE_GUIDE.md#generated-project-structure](USAGE_GUIDE.md#generated-project-structure)
2. Check: Generated `generated_agents/my_agent/README.md`
3. See: [ARCHITECTURE.md#template-architecture](ARCHITECTURE.md#template-architecture)

### Task: Implement Tool Logic

**Goal:** Add real implementations to generated code

1. Open: `generated_agents/my_agent/src/orchestrator.py`
2. Find: `async def _execute_my_tool(...)`
3. Replace: TODO with real implementation
4. Reference: [USAGE_GUIDE.md#customization](USAGE_GUIDE.md#customization)

### Task: Add Tests

**Goal:** Extend test coverage

1. Open: `generated_agents/my_agent/tests/test_agent.py`
2. Add: Your test cases (extends existing tests)
3. Run: `pytest tests/ -v`
4. Reference: [USAGE_GUIDE.md#adding-custom-tests](USAGE_GUIDE.md#adding-custom-tests)

### Task: Deploy to Production

**Goal:** Get agent running in production

1. Build: `docker build -t my-agent:latest .`
2. Push: `az acr build --registry <acr> --image my-agent:latest -f Dockerfile .`
3. Deploy: `azd ai agent deploy` (or ACA/Foundry)
4. Reference: [USAGE_GUIDE.md#deployment](USAGE_GUIDE.md#deployment)

### Task: Extend the Generator

**Goal:** Add new templates or customize

1. Review: [ARCHITECTURE.md#extensibility-points](ARCHITECTURE.md#extensibility-points)
2. Add: New template to `yaml_to_sdk/templates/`
3. Update: `generator.py` to call new template
4. Reference: [USAGE_GUIDE.md#advanced-topics](USAGE_GUIDE.md#advanced-topics)

---

## 📚 Complete Documentation Reading Order

### For End Users (Non-Technical)

1. README.md (5 min)
2. examples/README.md (10 min)
3. USAGE_GUIDE.md - Quick Start (5 min)
4. USAGE_GUIDE.md - Deployment (10 min)

**Total: ~30 minutes** to understand the system

### For Developers

1. README.md (5 min)
2. USAGE_GUIDE.md - Complete (30 min)
3. ARCHITECTURE.md - Full (30 min)
4. Source code review (30 min)

**Total: ~90 minutes** to understand and modify

### For DevOps/Infrastructure

1. README.md - Deployment section (5 min)
2. USAGE_GUIDE.md - Deployment section (10 min)
3. Generated Dockerfile review (5 min)
4. examples/vf_triage_agent.yaml (5 min)

**Total: ~25 minutes** to understand deployment

---

## 🔍 Quick Reference

### Command Quick Reference

```bash
# Install generator
pip install -r requirements.txt

# Generate from example
python -m yaml_to_sdk --agent-yaml examples/vf_triage_agent.yaml --output-dir generated_agents

# Generate from your YAML
python -m yaml_to_sdk --agent-yaml my_agent.yaml --output-dir generated_agents --verify

# Get help
python -m yaml_to_sdk --help
```

### Directory Quick Reference

```
To understand...                     Read...
─────────────────────────────────────────────────────────────────
The overall project                  README.md
How the YAML→Python flow works       ARCHITECTURE.md → Data Flow
How to use the generator             USAGE_GUIDE.md → Workflow
YAML schema (fields, types)          USAGE_GUIDE.md → YAML Schema Reference
Generated project structure          USAGE_GUIDE.md → Generated Project Structure
Tool implementation                  USAGE_GUIDE.md → Customization
Testing                              USAGE_GUIDE.md → Testing
Deployment                           USAGE_GUIDE.md → Deployment
Troubleshooting                      USAGE_GUIDE.md → Troubleshooting
System design                        ARCHITECTURE.md
Extending the generator              ARCHITECTURE.md → Extensibility Points
```

### YAML Schema Quick Reference

See [USAGE_GUIDE.md#yaml-schema-reference](USAGE_GUIDE.md#yaml-schema-reference) for complete YAML reference:

```yaml
name: agent-name
definition:
  kind: prompt | hosted
  model: gpt-5 | gpt-4
  instructions: |
    Multi-line system prompt...
  reasoning:
    effort: low | medium | high
  tools:
    - type: function
      name: tool_name
      description: "..."
      parameters: {...}
      strict: true
    - type: mcp
      server_label: kb_name
      server_url: "https://..."
      project_connection_id: kb-id
```

---

## 🎯 At a Glance

| Aspect | Details | Location |
|--------|---------|----------|
| **What is it?** | Cookie cutter for YAML→Python agent generation | README.md |
| **How to start?** | `python -m yaml_to_sdk --agent-yaml ... --output-dir ...` | README.md, USAGE_GUIDE.md |
| **System components** | Loader, Schema, Generator, Templates | ARCHITECTURE.md |
| **YAML format** | Structured agent definition | USAGE_GUIDE.md#yaml-schema-reference |
| **Generated code** | Python Agent Framework SDK implementation | USAGE_GUIDE.md#generated-project-structure |
| **Customization** | Implement tool logic, extend tests | USAGE_GUIDE.md#customization |
| **Deployment** | Docker, ACA, Foundry Agent Service | USAGE_GUIDE.md#deployment |
| **Troubleshooting** | Common issues and solutions | USAGE_GUIDE.md#troubleshooting |

---

## 📞 Support & Resources

### Within This Repository

- **Issues/Questions**: Check [USAGE_GUIDE.md#troubleshooting](USAGE_GUIDE.md#troubleshooting)
- **Examples**: See [examples/](examples/) directory
- **API Reference**: Check [ARCHITECTURE.md](ARCHITECTURE.md)

### External Resources

- [Agent Framework Documentation](https://github.com/microsoft/agent-framework)
- [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-studio/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Jinja2 Template Engine](https://jinja.palletsprojects.com/)
- [Model Context Protocol](https://modelcontextprotocol.io/)

---

## 📊 Documentation Statistics

| Document | Lines | Purpose |
|----------|-------|---------|
| README.md | ~400 | Overview and quick start |
| README_TEMPLATE.md | ~350 | Template features |
| USAGE_GUIDE.md | ~2000 | Comprehensive guide |
| ARCHITECTURE.md | ~700 | System design |
| SUMMARY.md | ~300 | What was created |
| examples/README.md | ~400 | Examples guide |
| This file | ~400 | Navigation index |

**Total: ~4550 lines of documentation** to support every level of user

---

## 🎓 Learning Tracks

### Track 1: Just Want to Generate Code (15 minutes)

1. README.md - Quick Start section
2. Run the generator command
3. Explore generated code
4. Done! You have a working project

### Track 2: Want to Understand the System (1 hour)

1. README.md - Full
2. USAGE_GUIDE.md - Workflow section
3. examples/README.md
4. Look at generated code
5. Done! You understand the full pipeline

### Track 3: Want to Customize and Extend (3 hours)

1. All of Track 2
2. ARCHITECTURE.md - Full
3. USAGE_GUIDE.md - Customization & Advanced Topics
4. Review source code in `yaml_to_sdk/`
5. Implement custom templates/generators
6. Done! You can extend the system

---

## ✅ Checklist: Before You Start

- [ ] Read README.md (main overview)
- [ ] Python 3.11+ installed
- [ ] `pip install -r requirements.txt` (install generator)
- [ ] Have your agent YAML from Foundry (or use example)
- [ ] Azure Subscription with Foundry project (for running)
- [ ] Ready to generate!

---

## 🚀 Next Steps

1. **Read** — Start with README.md
2. **Explore** — Check examples/vf_triage_agent.yaml
3. **Generate** — Run `python -m yaml_to_sdk --agent-yaml examples/vf_triage_agent.yaml --output-dir generated_agents`
4. **Understand** — Review generated code
5. **Customize** — Implement your tool logic
6. **Deploy** — Ship to production

---

**Happy agent building! 🎉**

For questions or issues, refer to [USAGE_GUIDE.md#troubleshooting](USAGE_GUIDE.md#troubleshooting) or check the examples.
