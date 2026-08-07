# Team Evaluations

The shared `evals` package evaluates any team selected with `--team`. It does
not define datasets, workflow statuses, tool names, domain rules, or a default
team. Each team owns those values in `evals/eval.yaml`.

## Setup

Create a Python 3.11 or 3.12 virtual environment outside the repository, then
install both runtime and evaluation dependencies:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r evals/requirements.txt
Copy-Item evals/.env.example evals/.env
az login
```

Set `FOUNDRY_PROJECT_ENDPOINT` and `EVAL_JUDGE_DEPLOYMENT` in `evals/.env`.
Select a team on every command with `--team`, or set `EVAL_TEAM_DIR`.
The judge endpoint is derived from the Foundry project by default. Use
`EVAL_JUDGE_ENDPOINT` only when the judge deployment belongs to another
resource. All Azure authentication uses the active Azure CLI session. API keys
are rejected; run `az login` before starting an evaluation.

## Team Contract

A team that supports evaluations contains:

```text
<team>/
  team.yaml
  evals/
    eval.yaml
    thresholds.yaml
    datasets/
      smoke.jsonl
```

Example `eval.yaml`:

```yaml
name: example-team
team_yaml: ../team.yaml
publish_name: example-team
sets:
  smoke: ./datasets/smoke.jsonl
thresholds: ./thresholds.yaml
reports_dir: ./reports

task:
  query_field: request
  input_fields:
    reference: selectedReference

output:
  status_field: state
  intents_field: labels

workflow_schema:
  READY: [payload]
  FAILED: [message]

scope:
  leak_patterns:
    - '\bSECRET-[0-9]+\b'
  refusal_patterns:
    - 'outside my scope'
  clarification_patterns:
    - 'which item'
```

Dataset rows must contain `id` and `query`. Optional generic expectations are
`expected_intent`, `expected_status`, `expected_behaviour`, `required_facts`,
`forbidden_facts`, and `category`. Any fields listed under `task.input_fields`
are copied into the team's initial JSON task envelope.

## Run

```powershell
python -m evals.run_evals --team agent_teams/<team-directory>
python -m evals.run_evals --team agent_teams/<team-directory> --set smoke
python -m evals.run_evals --team agent_teams/<team-directory> --no-publish
python -m evals.run_evals --team agent_teams/<team-directory> --no-judge --limit 2
python -m evals.run_evals --team agent_teams/<team-directory> --row-timeout 180
```

Results are written to the `reports_dir` configured by the selected team.
Thresholds are evaluated from that team's threshold file. Use
`--ignore-thresholds` when exploring incomplete suites. Each team row reports
its elapsed time while running and is stopped after five minutes by default.

## Shared Tests

```powershell
python -m pytest evals/tests -q
```

These tests use a temporary synthetic manifest and do not depend on a specific
team, agent, tool, status, or dataset.
