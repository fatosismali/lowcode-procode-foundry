# VF Billing Team

Three-agent sequential billing workflow:

1. `vf-billing-profile-agent` resolves the account.
2. `vf-billing-investigation-agent` retrieves billing evidence.
3. `vf-billing-response-agent` writes the customer response.

Run from the repository root:

```powershell
python orchestrator.py --team-yaml agent_teams/vf_billing_team/team.yaml
```

The first response asks you to choose an account because the mock backend has
personal and business profiles. Enter `personal` or `business` at `You>` to
continue the same chat, and enter `exit` to stop.

To exercise the complete mock-data path when multiple profiles exist:

```powershell
python orchestrator.py `
  --team-yaml agent_teams/vf_billing_team/team.yaml `
  --task '{"userQuery":"How much is my latest bill and has it been paid?","selectedAccountReference":"personal"}' `
  --once
```

Agent behavior is defined under `agents/`. Billing mock tools and `TOOL_REGISTRY` are in `src/tools.py`. No code generation is required after YAML changes.

## Evaluations

This team's evaluation manifest, datasets, thresholds, and generated reports
live under `evals/`. Run all configured sets from the repository root:

```powershell
python -m evals.run_evals `
  --team agent_teams/vf_billing_team `
  --no-publish
```

Use `--set <name>` for one set, `--no-judge` for deterministic graders only,
and `--limit 2` for a quick smoke run. Set the Foundry project and judge model
in the shared `evals/.env` file or pass their command-line options.
