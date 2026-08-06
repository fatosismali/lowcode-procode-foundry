# Evaluations

Tests the billing agent team. Scores everything locally so you get answers in a
couple of minutes, then publishes the results to Foundry.

## Setup

Python 3.11 or 3.12 (x64) and the Azure CLI.

Create the virtual environment **outside this repository**. One of the
dependencies blocks imports that resolve from under the working directory, so a
`.venv` inside the repo fails to import.

**Windows**

```powershell
py -3.12 -m venv ..\evals-venv
..\evals-venv\Scripts\Activate.ps1
pip install -r evals\requirements.txt
pip install -r requirements.txt
az login
copy evals\.env.example evals\.env
```

**macOS**

```bash
python3.12 -m venv ../evals-venv
source ../evals-venv/bin/activate
pip install -r evals/requirements.txt
pip install -r requirements.txt
az login
cp evals/.env.example evals/.env
```

Then edit `evals/.env` and set `FOUNDRY_PROJECT_ENDPOINT` to your Foundry
project and `EVAL_JUDGE_DEPLOYMENT` to a model deployed in it.

Check it works without calling Azure:

```bash
python -m pytest evals/tests -q
```

## Running

```bash
python -m evals.run_evals                          # all three sets
python -m evals.run_evals --set intent_classifier
python -m evals.run_evals --no-publish             # local only
python -m evals.run_evals --limit 2                # quick smoke run
python -m evals.run_evals --concurrency 4          # if the judge rate limits
```

Results print to the console, land in `evals/reports/`, and the command exits 1
if anything falls below `thresholds.yaml`.

Run the team on its own first, so a failure is clearly the team and not the
evaluation:

```bash
python orchestrator.py --team-yaml generated_agents/vf_billing_team/team.yaml
```

## The three sets

| Set | Rows | What it checks |
| --- | --- | --- |
| `intent_classifier` | 9 | Utterances resolve to the right intent. One row per label. |
| `billing_agent` | 7 | Answers carry the right figures, in the right format, with nothing leaked. |
| `system_e2e` | 6 | Billing questions answered, everything else refused. |

## What gets checked

Rule-based, in `graders.py`:

- `intent_match` — the detected intent matches the expected one
- `schema_valid` — each stage returns a valid envelope
- `fact_recall` — the right figures appear, and figures from other scenarios do not
- `scope_adherence` — answers, refuses or asks, as the row expects, without
  leaking account numbers or internal IDs

Model-judged, in `evaluators.py`: coherence, fluency, relevance, groundedness,
intent resolution, task adherence, tool call accuracy, and five safety checks
covering violence, sexual content, self-harm, hate and prompt injection.

`thresholds.yaml` sets a minimum pass rate for each. Rows a check does not apply
to are skipped rather than failed.

## Test data

Synthetic, based on the mock billing fixtures. It only asserts on values that
are identical in both mock backends, so it stays valid whichever is wired up.

To use different data, replace the JSONL files in `datasets/`. The field names
are the only contract.

## Notes

- `evals/.env` holds your endpoint and must not be committed. It is gitignored.
- The agent YAMLs ask for a `gpt-5` deployment. The team will not start unless
  one exists with that exact name.
- No agent prompt currently restricts the team to billing topics, so the refusal
  rows are expected to fail until one is added.
- A full run is a few hundred model calls. They run eight at a time; lower
  `--concurrency` if you hit rate limits.
