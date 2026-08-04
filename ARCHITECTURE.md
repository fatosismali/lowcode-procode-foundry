# Architecture & System Design

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FOUNDRY YAML → AGENT FRAMEWORK SDK                   │
│                         Cookie Cutter Template                          │
└─────────────────────────────────────────────────────────────────────────┘

Input Layer (Low Code)
├─ YAML Agent Definitions (from Foundry Agent Service)
└─ JSON configurations (optional)

Processing Layer (Automatic)
├─ [Loader] YAML/JSON parsing and loading
├─ [Validator] Pydantic schema validation
├─ [Generator] Context extraction and preparation
└─ [Templates] Jinja2 rendering to Python code

Output Layer (Pro Code)
├─ Python orchestrator (Agent Framework SDK)
├─ Type-safe models (Pydantic)
├─ Configuration management
├─ Tool implementations
├─ Test suite (pytest)
├─ Deployment files (Docker, pyproject.toml)
└─ Documentation (auto-generated README)

Deployment Layer (Production)
├─ Docker containers
├─ Azure Container Apps
├─ Microsoft Foundry Agent Service
└─ Kubernetes (AKS)
```

---

## Component Architecture

### 1. Loader Module (`yaml_to_sdk/loader.py`)

**Responsibilities:**
- Load YAML/JSON files from filesystem
- Parse raw data into Python dictionaries
- Handle file errors gracefully

**Key Methods:**
- `load_yaml_file(path)` → Dict
- `load_json_file(path)` → Dict
- `validate_and_parse(data)` → FoundryAgentDefinition
- `load_agent_definition(path)` → FoundryAgentDefinition

**Error Handling:**
- FileNotFoundError → Clear message
- YAML parsing errors → Detailed context
- Validation errors → Structured report

### 2. Schema Module (`yaml_to_sdk/schema.py`)

**Responsibilities:**
- Define Pydantic models for all YAML structures
- Provide type validation and conversion
- Generate helpful validation errors

**Key Models:**
- `FoundryAgentDefinition` — Root schema
- `AgentDefinition` — Agent config
- `FunctionTool` — Function tool definition
- `MCPTool` — MCP/knowledge base tool
- `FunctionToolParameters` — Parameter schema
- `ReasoningConfig` — Reasoning parameters

**Features:**
- Field validators (log_level, reasoning_effort, etc.)
- Custom properties (project_slug, class_name)
- Polymorphic tool parsing
- Config classes for Pydantic behavior

### 3. Generator Module (`yaml_to_sdk/generator.py`)

**Responsibilities:**
- Extract context from validated agent definition
- Render Jinja2 templates with context
- Generate complete Python projects

**Key Methods:**
- `generate_context(agent_def)` → Dict[str, Any]
- `render_template(name, context)` → str
- `generate_orchestrator(agent_def)` → str
- `generate_models(agent_def)` → str
- `generate_config(agent_def)` → str
- And 5+ others for all project components

**Custom Filters:**
- `snake_case` — Convert to snake_case
- `camel_case` — Convert to camelCase
- `pascal_case` — Convert to PascalCase
- `safe_identifier` — Make valid Python identifier

**Context Extraction:**
- Parses tool definitions (function + MCP)
- Generates Pydantic model names
- Extracts parameter information
- Builds tool execution templates

### 4. CLI Module (`yaml_to_sdk/__main__.py`)

**Responsibilities:**
- Command-line interface
- Project generation workflow
- Error handling and reporting
- Progress indication

**Key Functions:**
- `main()` → Entry point
- `generate_agent_project()` → Orchestrates generation
- `create_directory_structure()` → Creates files
- `verify_generated_code()` → Validates output
- `print_generation_summary()` → User feedback

**Features:**
- Argument parsing with argparse
- Logging at all stages
- Verification mode (syntax checking)
- Force overwrite option
- Verbose mode for debugging

---

## Template Architecture

### Jinja2 Templates (`yaml_to_sdk/templates/`)

#### 1. `orchestrator.py.j2` (400+ lines)

**Purpose:** Main agent class with tool orchestration

**Key Components:**
- `{{agent_class}}` class definition
- FoundryChatClient initialization
- Tool binding via @Tool decorators
- Conversation loop (run_conversation)
- Interactive mode (run_interactive)
- Tool execution methods (one per tool)

**Generated Variables:**
```
{{agent_name}}              Agent display name
{{agent_class}}             PascalCase class name
{{agent_description}}       Agent description
{{model}}                   Model name (gpt-5, etc.)
{{instructions}}            System prompt
{{function_tools}}          List of function tool contexts
{{has_mcp_tools}}          Boolean flag for MCP tools
{{mcp_tools}}              List of MCP tool contexts
{{reasoning_effort}}        Reasoning level
```

#### 2. `models.py.j2` (100+ lines)

**Purpose:** Type-safe Pydantic models for all tools

**Generated Classes per Tool:**
- `{{ToolName}}Request` — Tool input with Field descriptions
- `{{ToolName}}Response` — Tool output with status/data/error

**Utilities:**
- `parse_tool_response()` — Convert various types to dict
- Type aliases for common patterns

#### 3. `config.py.j2` (150+ lines)

**Purpose:** Configuration management with environment variables

**Generated Configuration:**
- Required: `foundry_project_connection_string`
- Optional: `model_name`, `model_endpoint`, `log_level`
- Per-tool: Enable/disable flags
- Per-MCP: Server URLs and connection IDs
- Runtime: Timeouts, limits, reasoning effort

**Validation:**
- `log_level` must be valid (DEBUG, INFO, WARNING, ERROR)
- `reasoning_effort` must be low/medium/high
- Type validation for all fields

#### 4. `tools_base.py.j2` (150+ lines)

**Purpose:** Base classes and utilities for tool implementations

**Key Classes:**
- `ToolBase` — Abstract base class
- `ToolHandler` — Decorator for tool functions
- `ToolExecutor` — Manages execution and timeouts
- Tool registry system

**Features:**
- Automatic error handling decorator
- Timeout management
- Logging wrapper
- Tool discovery mechanism

#### 5. `pyproject.toml.j2` (100+ lines)

**Purpose:** Project metadata and build configuration

**Sections:**
- Build system (hatchling)
- Project metadata (name, version, description)
- Dependencies (agent-framework, azure, etc.)
- Optional dependencies (dev, observability)
- Tool configuration (pytest, black, mypy, ruff)

#### 6. `test_agent.py.j2` (200+ lines)

**Purpose:** Comprehensive pytest test suite

**Test Classes:**
- `TestAgentInitialization` — Init and config
- `TestToolExecution` — Per-tool execution tests
- `TestConversation` — Conversation flow tests
- `TestConfiguration` — Config validation
- `TestAgentModels` — Model validation
- `TestIntegration` — End-to-end tests

**Per-Tool Tests:**
- Success case
- Error handling
- Validation

#### 7. `env.example.j2` (80+ lines)

**Purpose:** Environment configuration template

**Sections:**
- Required Foundry configuration
- Model selection
- Agent configuration
- Per-tool enable/disable
- Per-MCP server configuration
- Logging and observability
- Azure credentials
- Runtime limits

#### 8. `Dockerfile.j2` (50+ lines)

**Purpose:** Production container build

**Stages:**
- Builder stage (Python 3.11 slim, builds dependencies)
- Runtime stage (minimal, copies only what's needed)

**Security:**
- Non-root user (agent:agent)
- Health checks
- Minimal base image
- No caching of pip files

#### 9. `README.md.j2` (300+ lines)

**Purpose:** Complete generated documentation

**Sections:**
- Overview and architecture
- Quick start (4 steps)
- Installation instructions
- Configuration reference
- Tool documentation (per tool)
- Development guide
- Testing instructions
- Deployment patterns
- Troubleshooting
- Related resources

---

## Data Flow

### Generation Flow

```
User Input (YAML File)
    ↓
[YAML Parser] AgentYAMLLoader.load_yaml_file()
    ↓
Dict[str, Any]
    ↓
[Pydantic Validator] FoundryAgentDefinition
    ↓
[Context Extractor] AgentCodeGenerator.generate_context()
    ↓
Dict[str, Any] (template variables)
    ↓
[Jinja2 Renderer] template.render(context)
    ↓
String (Python code)
    ↓
[File Writer] File system
    ↓
Generated Project Directory
```

### Runtime Flow (Generated Agent)

```
User Input (Conversation)
    ↓
[CLI/API] User message
    ↓
[Agent.invoke()] FoundryChatClient
    ↓
[Model] gpt-5 @ Foundry
    ↓
[Tool Selection] Which tool(s) to call?
    ↓
[Tool Execution] Execute selected tools
    ↓
[Context] Pass tool results back to model
    ↓
[Response Generation] Generate final response
    ↓
[User Output] Text response
```

---

## Key Design Patterns

### 1. Factory Pattern (Generator)

```python
class AgentCodeGenerator:
    def generate_orchestrator() → str
    def generate_models() → str
    def generate_config() → str
    # ... one method per component
```

Each method follows the same pattern:
1. Extract context
2. Render template
3. Return string

### 2. Builder Pattern (File Creation)

```python
def create_directory_structure(project_dir, agent_def, generator):
    # Build directory structure
    # Build file content (using generator)
    # Write all files
```

Builds complete project in coordinated way.

### 3. Template Method Pattern (Jinja2)

Each template:
1. Imports common sections (boilerplate)
2. Renders component-specific code
3. Integrates with other components

### 4. Decorator Pattern (Tool Handlers)

```python
@Tool(name="my_tool", description="...")
async def my_tool(param: str):
    # Tool implementation
```

### 5. Strategy Pattern (Tool Execution)

```python
class ToolExecutor:
    async def execute_tool(tool_func, *args, **kwargs):
        # Handle timeouts
        # Handle errors
        # Return standardized response
```

---

## Error Handling Strategy

### At Load Time

```
YAML Parse Error
    ↓
Catch with try/except
    ↓
Reraise with context
    ↓
User sees: "Failed to parse YAML {path}: {error}"
```

### At Validation Time

```
Pydantic ValidationError
    ↓
Catch with try/except
    ↓
Extract all error paths
    ↓
User sees: Structured validation errors with field paths
```

### At Generation Time

```
Template Render Error
    ↓
Catch with try/except
    ↓
Report template name and error
    ↓
User can debug template or context
```

### At Generated Code Runtime

```
Tool Execution Error
    ↓
Catch in try/except
    ↓
Log with structured logging
    ↓
Return error response
    ↓
Agent can handle gracefully
```

---

## Performance Considerations

### Generation Phase

- **Pydantic parsing:** O(n) where n = YAML fields
- **Template rendering:** O(m) where m = template lines
- **File I/O:** Minimal (creates ~10 files)

**Total time:** ~100-500ms for typical agent

### Runtime (Generated Agent)

- **Model invocation:** Network I/O (dominant)
- **Tool execution:** Depends on tool implementation
- **Async execution:** Non-blocking (scalable)

**Throughput:** Limited by model concurrency, not generator

---

## Extensibility Points

### 1. Add New Templates

Create `yaml_to_sdk/templates/my_component.j2`

Update `generator.py`:
```python
def generate_my_component(self, agent_def) -> str:
    context = self.generate_context(agent_def)
    return self.render_template("my_component.j2", context)
```

### 2. Extend YAML Schema

Update `schema.py`:
```python
class AgentDefinition(BaseModel):
    new_field: Optional[str] = None
```

Generator automatically supports new field.

### 3. Add Custom Filters

In `generator.py`:
```python
self.env.filters['my_filter'] = my_filter_impl
```

Use in templates:
```jinja2
{{ value|my_filter }}
```

### 4. Add Validators

In `schema.py`:
```python
@field_validator('my_field')
@classmethod
def validate_my_field(cls, v):
    # Validation logic
    return v
```

---

## Testing Strategy

### Generator Tests

```
test_loader.py
├─ Load YAML files
├─ Parse invalid YAML
├─ Load JSON files
└─ Validation errors

test_schema.py
├─ Pydantic model validation
├─ Polymorphic tool parsing
├─ Field validators
└─ Config generation

test_generator.py
├─ Context extraction
├─ Template rendering
├─ File generation
└─ Project structure
```

### Generated Agent Tests

```
test_agent.py (auto-generated)
├─ Agent initialization
├─ Configuration loading
├─ Tool execution (mocked)
├─ Error handling
├─ Integration tests
└─ Model validation
```

---

## Security Considerations

### Input Validation

- ✅ Pydantic validates all YAML input
- ✅ Tool parameters validated at runtime
- ✅ No code injection possible (Jinja2 context)

### Secrets Management

- ✅ No secrets in generated code
- ✅ All secrets via environment variables
- ✅ Azure Key Vault integration ready
- ✅ .gitignore protects .env files

### Container Security

- ✅ Non-root user execution
- ✅ Minimal base image (python:3.11-slim)
- ✅ Health checks
- ✅ No sudo/build tools in runtime

### Code Generation

- ✅ Jinja2 autoescaping enabled
- ✅ No dynamic code execution
- ✅ AST validation of generated Python

---

## Deployment Architecture

### Local Development

```
orchestrator.py
    ↓
Async event loop
    ↓
FoundryChatClient (Foundry endpoint)
    ↓
Azure OpenAI (gpt-5 model)
```

### Docker Container

```
Dockerfile
    ↓
Multi-stage build
    ↓
Runtime image (minimal)
    ↓
Python app (non-root user)
    ↓
Health checks enabled
```

### Azure Container Apps

```
ACR (image registry)
    ↓
Container Apps
    ↓
Network: Private/Public
    ↓
Secrets: Azure Key Vault
    ↓
Observability: App Insights
```

### Foundry Agent Service

```
Agent Version (container)
    ↓
Foundry control plane
    ↓
Model access (cross-resource capable)
    ↓
Tool invocation via Activity protocol
    ↓
Response streaming (SSE or Responses API)
```

---

## Conclusion

The architecture provides:

1. **Clean Separation of Concerns** — Loader, schema, generator, templates
2. **Type Safety Throughout** — Pydantic at every step
3. **Extensibility** — Easy to add templates, schema, validators
4. **Error Handling** — Clear messages at every stage
5. **Production Readiness** — Security, logging, testing, deployment
6. **Documentation** — Auto-generated + comprehensive guides

**Result:** One command transforms low-code YAML into production-ready Python with enterprise features.
