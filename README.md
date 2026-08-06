# Foundry YAML Orchestrator

Run Microsoft Agent Framework teams directly from YAML. There is no YAML-to-Python generation step: one root `orchestrator.py` loads a team definition, loads each referenced agent definition in order, binds Python tools, and runs the selected orchestration pattern.

## Setup

```powershell
python -m pip install -r requirements.txt
az account show --query "{tenant:tenantId, subscription:name}" -o table
```

If Azure CLI is not authenticated, sign in to the tenant that owns the Foundry project before running a team.

## Run a team

Billing:

```powershell
python orchestrator.py --team-yaml generated_agents/vf_billing_team/team.yaml
```

Triage:

```powershell
python orchestrator.py --team-yaml generated_agents/vf_triage_team/team.yaml
```

Override the task without editing YAML:

```powershell
python orchestrator.py `
  --team-yaml generated_agents/vf_billing_team/team.yaml `
  --task '{"userQuery":"Show my current bill","selectedAccountReference":"personal"}'
```

After installing the project, the equivalent console command is:

```powershell
foundry-team --team-yaml generated_agents/vf_billing_team/team.yaml
```

## Team contract

Each team directory contains:

```text
team.yaml               Orchestration pattern, ordered agents, default task
.env.example             Foundry endpoint and model settings
agents/*.yaml            Agent model, instructions, and tool declarations
src/tools.py             Python implementations exposed through TOOL_REGISTRY
```

The directory is still named `generated_agents/` for compatibility with the existing repository, but these are now source-controlled runtime definitions rather than generated SDK projects.

A team file declares its runtime files and orchestration:

```yaml
name: example-team
runtime:
  env_file: ./.env
  tools_file: ./src/tools.py
orchestration:
  pattern: sequential
  chain_only_agent_responses: true
  agents:
    - ./agents/first_agent.yaml
    - ./agents/second_agent.yaml
  task: Process the request.
```

For `sequential`, agents execute in the listed order. With `chain_only_agent_responses: true`, each agent receives only the immediately preceding agent response. Agent prompts should therefore define a stable output contract for the next stage.

Function tools declared in agent YAML must have matching entries in `TOOL_REGISTRY`. MCP tools are constructed directly from their YAML declarations.

Supported patterns are `sequential`, `concurrent`, `group_chat`, and `handoff`.

## Configuration

Copy the team example file and set its Foundry endpoint:

```powershell
Copy-Item generated_agents/vf_billing_team/.env.example generated_agents/vf_billing_team/.env
```

The runtime loads the `.env` adjacent to `team.yaml`. Real `.env` files are ignored by Git.

## Tests

```powershell
python -m pytest tests/test_orchestrator.py -q
```

See `ARCHITECTURE.md` for runtime internals and `USAGE_GUIDE.md` for adding a team.
