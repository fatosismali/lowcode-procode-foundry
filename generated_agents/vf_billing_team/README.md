# vf-billing-team

Vodafone billing customer-support team: resolve account, investigate billing evidence, respond to the customer.

**Orchestration pattern:** `sequential` (Microsoft Agent Framework)

## Agents

| Agent | Model | Tools |
| --- | --- | --- |
| `vf-billing-profile-agent` | gpt-5 | 1 |
| `vf-billing-investigation-agent` | gpt-5 | 1 |
| `vf-billing-response-agent` | gpt-5 | 0 |

## Project structure

```
vf_billing_team/
  team.yaml                Team spec (pattern + which agents) — loaded at runtime
  agents/
    vf_billing_profile_agent.yamlDeclarative definition of "vf-billing-profile-agent"
    vf_billing_investigation_agent.yamlDeclarative definition of "vf-billing-investigation-agent"
    vf_billing_response_agent.yamlDeclarative definition of "vf-billing-response-agent"
  src/
    orchestrator.py        Single runtime loader: reads the YAMLs, builds every
                           agent in-process, wires the pattern
    tools.py               Tool implementations (one place) + TOOL_REGISTRY
    config.py              Team configuration
  tests/
    test_team.py           Smoke test
  pyproject.toml
  requirements.txt
  .env.example
  Dockerfile
```

> The orchestrator is **pattern-agnostic**: it reads `team.yaml` and each
> `agents/*.yaml` at run time and builds the agents dynamically. There are no
> per-agent Python files — change behaviour by editing the YAMLs (or the pattern
> in `team.yaml`) and implementing tools in `src/tools.py`.


## Pattern: sequential

Agents run in a fixed pipeline. Each agent processes the previous agent's output.
Best for step-by-step refinement with clear stage dependencies.

See [AI agent orchestration patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)
for guidance on choosing a pattern.

## Getting started

```bash
cp .env.example .env          # add your Foundry project endpoint
pip install -r requirements.txt
az login                      # AzureCliCredential is used for auth
python -m src.orchestrator
```

## Next steps

1. Implement the tool bodies in `src/tools.py` (one file for all agents).
2. Adjust agents by editing `agents/*.yaml`, or change the pattern in `team.yaml`.
3. Extend `tests/test_team.py`.