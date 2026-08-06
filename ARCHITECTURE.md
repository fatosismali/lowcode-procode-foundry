# Architecture

## Runtime model

`orchestrator.py` is the only orchestration implementation. It does not emit Python projects or transform YAML into source code.

```text
CLI / run_team(team_yaml)
        |
        v
team.yaml -----------------------> pattern + ordered agent paths + task
        |                                      |
        |                                      v
        +--> runtime.env_file              Workflow builder
        +--> runtime.tools_file                 |
                     |                          v
                     v                  sequential/concurrent/
              TOOL_REGISTRY             group_chat/handoff
                     |                          |
                     +------> Agent <-----------+
                                ^
                                |
                         agents/*.yaml
```

## Loading sequence

1. Resolve `team.yaml` from `--team-yaml`.
2. Load the team-local `.env` without overwriting existing process variables.
3. Import the team-local `src/tools.py` and read `TOOL_REGISTRY`.
4. Read `orchestration.pattern`, task, and ordered agent references.
5. Load each agent YAML and construct an Agent Framework `Agent`.
6. Bind function tools by exact name and MCP tools from their URLs.
7. Build and run the workflow.

Missing function implementations fail before model execution. This prevents an agent from silently running without a declared capability.

## Sequential handoff

Sequential teams default to `chain_only_agent_responses: true`. Agent Framework then sends `prior.agent_response.messages` to the next stage rather than the accumulated conversation.

The runtime also applies `ReasoningSafeHandoffMiddleware`. It removes cross-agent `function_call`, `function_result`, and `text_reasoning` content before the next Foundry Responses API call. This prevents orphaned reasoning references while preserving user-visible text and the current agent's own tool loop.

## Code ownership

- `orchestrator.py`: shared runtime behavior.
- `agent_teams/*/team.yaml`: team topology and runtime paths.
- `agent_teams/*/agents/*.yaml`: agent behavior and tool declarations.
- `agent_teams/*/src/tools.py`: executable tool implementations.
- `tests/test_orchestrator.py`: shared runtime contract tests.

Adding or changing an agent requires editing YAML. Adding or changing a function tool requires editing the team tool registry. No regeneration is required.
