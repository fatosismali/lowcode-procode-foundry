# VF Billing Team

Three-agent sequential billing workflow:

1. `vf-billing-profile-agent` resolves the account.
2. `vf-billing-investigation-agent` retrieves billing evidence.
3. `vf-billing-response-agent` writes the customer response.

Run from the repository root:

```powershell
python orchestrator.py --team-yaml generated_agents/vf_billing_team/team.yaml
```

To exercise the complete mock-data path when multiple profiles exist:

```powershell
python orchestrator.py `
  --team-yaml generated_agents/vf_billing_team/team.yaml `
  --task '{"userQuery":"How much is my latest bill and has it been paid?","selectedAccountReference":"personal"}'
```

Agent behavior is defined under `agents/`. Billing mock tools and `TOOL_REGISTRY` are in `src/tools.py`. No code generation is required after YAML changes.
