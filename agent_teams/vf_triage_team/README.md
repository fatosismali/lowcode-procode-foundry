# VF Triage Team

Two-agent sequential incident workflow:

1. `vf-triage-tool-agent` diagnoses and applies the corrective action.
2. `vf-comms-agent` prepares and sends customer communications.

Run from the repository root:

```powershell
python orchestrator.py --team-yaml agent_teams/vf_triage_team/team.yaml
```

Agent behavior is defined under `agents/`. Incident, telemetry, impact, remediation, and notification mock tools are implemented in `src/tools.py` and exposed through `TOOL_REGISTRY`.

Changing `team.yaml` or an agent YAML takes effect on the next run. No code generation is required.
