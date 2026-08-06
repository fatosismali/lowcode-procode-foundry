# Usage Guide

## Run existing teams

From the repository root:

```powershell
python -m pip install -r requirements.txt
python orchestrator.py --team-yaml agent_teams/vf_billing_team/team.yaml
python orchestrator.py --team-yaml agent_teams/vf_triage_team/team.yaml
```

The YAML task runs first, then the CLI waits at `You>` for follow-up messages
while retaining the agents' sessions. Type `exit` or `quit` to stop. Use
`--task` to override the first turn, or `--once` to run one task and exit.

## Add a team

Create a directory with this structure:

```text
my_team/
  .env.example
  team.yaml
  agents/
    first_agent.yaml
    second_agent.yaml
  src/
    tools.py
```

Define the team:

```yaml
name: my-team
description: Example sequential team
runtime:
  env_file: ./.env
  tools_file: ./src/tools.py
orchestration:
  pattern: sequential
  chain_only_agent_responses: true
  agents:
    - ./agents/first_agent.yaml
    - ./agents/second_agent.yaml
  task: Handle the default request.
```

Define each agent using the Foundry YAML shape:

```yaml
name: first-agent
description: Produces structured input for the next stage
definition:
  model: gpt-5
  instructions: |
    Return a JSON object containing result and status.
  tools:
    - type: function
      name: lookup_data
```

Implement and register every function tool:

```python
from typing import Annotated, Any

from agent_framework import tool


@tool
async def lookup_data(
    reference: Annotated[str, "Record reference"],
) -> dict[str, Any]:
    return {"reference": reference, "status": "ok"}


TOOL_REGISTRY = {
    "lookup_data": lookup_data,
}
```

Copy `.env.example` to `.env`, fill in `FOUNDRY_PROJECT_ENDPOINT`, and run:

```powershell
python orchestrator.py --team-yaml my_team/team.yaml
```

## Sequential contracts

The order under `orchestration.agents` is execution order. Each agent should document the previous stage's output in its instructions and emit the exact input contract expected by the next stage.

With `chain_only_agent_responses: true`, the next stage does not receive the original accumulated conversation. Preserve required values, such as the original user request or internal identifiers, in each intermediate structured response.

## Other patterns

- `concurrent`: all listed agents process the initial input independently.
- `group_chat`: agents take turns; configure `max_rounds`.
- `handoff`: configure `start_agent` and a `handoffs` mapping.

## Troubleshooting

`FOUNDRY_PROJECT_ENDPOINT is not configured`:

- Confirm `runtime.env_file` resolves relative to `team.yaml`.
- Confirm the file contains `FOUNDRY_PROJECT_ENDPOINT=...`.

Missing tool registration:

- Ensure the YAML tool name exactly matches a key in `TOOL_REGISTRY`.

Azure authentication errors:

```powershell
az account show --query "{tenant:tenantId, subscription:name}" -o table
```

Reasoning/function-call errors between agents should be handled by the shared middleware. Run the shared tests if that behavior changes:

```powershell
python -m pytest tests/test_orchestrator.py -q
```
