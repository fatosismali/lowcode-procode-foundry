# Running `vf-triage-team` from a fresh machine

End-to-end setup for someone starting with nothing installed. Follow top to bottom.

The team runs two agents in sequence:

1. **`vf-triage-tool-agent`** — looks up an incident, fetches RAN telemetry and
   customer impact, decides root cause, applies a corrective change.
2. **`vf-comms-agent`** — takes the triage result and drafts customer notifications.

Both agents are defined declaratively in [`team.yaml`](team.yaml) +
[`agents/*.yaml`](agents/). The runtime loader is [`src/orchestrator.py`](src/orchestrator.py).

---

## 1. Prerequisites — install once per machine

You need three things on the box.

### 1.1 Python 3.10 or newer

**Windows**

```powershell
winget install --id Python.Python.3.12 -e
# open a new shell so PATH updates take effect
python --version   # should print 3.10+
```

**macOS**

```bash
brew install python@3.12
python3 --version
```

**Linux (Debian/Ubuntu)**

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
python3 --version
```

### 1.2 Azure CLI

Authentication uses `AzureCliCredential`, so `az login` must succeed before the
orchestrator will run.

**Windows**

```powershell
winget install --id Microsoft.AzureCLI -e
```

**macOS**

```bash
brew install azure-cli
```

**Linux**

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

Verify:

```bash
az version
```

### 1.3 Git (only if you're cloning the repo)

```powershell
winget install --id Git.Git -e            # Windows
brew install git                           # macOS
sudo apt install -y git                    # Linux
```

---

## 2. Get the code

If you already have the folder, skip this step.

```powershell
git clone <your-repo-url>
cd <repo>/generated_agents/vf_triage_team
```

You should be in the folder that contains `team.yaml`, `src/`, `agents/`,
`requirements.txt`, and `.env.example`. Confirm:

```powershell
ls        # PowerShell
# or: ls -la   # bash
```

---

## 3. Create and activate a virtual environment

Isolates the project's dependencies from anything else on the machine.

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, run once per user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt should now show `(.venv)`.

---

## 4. Install Python dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

This pulls in:

- `agent-framework` — Microsoft Agent Framework (agents + orchestrations)
- `azure-identity` — `AzureCliCredential`
- `PyYAML` — runtime YAML loader
- `pytest` + `pytest-asyncio` — for the smoke tests

---

## 5. Sign in to Azure

The orchestrator uses your CLI identity to call Microsoft Foundry. Log in to the
**tenant that owns the Foundry project**:

```powershell
az login --tenant <your-tenant-id-or-domain>

# confirm you're on the right subscription
az account show --query "{tenant: tenantId, sub: name, id: id}" -o table
```

If the account listed here doesn't have permission on the Foundry project you'll
get a `401` / `403` at run time.

---

## 6. Configure the project

Copy the example environment file and fill in your Foundry project endpoint.

**Windows**

```powershell
Copy-Item .env.example .env
notepad .env
```

**macOS / Linux**

```bash
cp .env.example .env
${EDITOR:-nano} .env
```

Set at minimum:

```
FOUNDRY_PROJECT_ENDPOINT=https://<your-resource>.services.ai.azure.com/api/projects/<project>
FOUNDRY_MODEL=gpt-5        # or any deployment in your project
LOG_LEVEL=INFO
```

You can find the endpoint in the **Microsoft Foundry portal → your project →
Overview → Project details**.

> ⚠️ **Watch out for leaked env vars.** If you have `AZURE_OPENAI_ENDPOINT` or
> `AZURE_OPENAI_API_KEY` set from another project, unset them for this shell —
> the orchestrator prefers `FOUNDRY_PROJECT_ENDPOINT`, but stray key-auth vars
> can still confuse the underlying SDK. Check with:
>
> ```powershell
> Get-ChildItem Env: | Where-Object Name -Match 'AZURE_OPENAI|FOUNDRY|OPENAI'
> ```
>
> Remove them for the current shell:
>
> ```powershell
> Remove-Item Env:AZURE_OPENAI_ENDPOINT, Env:AZURE_OPENAI_API_KEY -ErrorAction SilentlyContinue
> ```

### 6.1 Load `.env` into the shell

Python does **not** auto-read `.env`. Do this once per new shell (before running):

**PowerShell**

```powershell
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*([^#=]+)=(.*)$') {
    [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
  }
}

# verify
$env:FOUNDRY_PROJECT_ENDPOINT
```

**bash / zsh**

```bash
set -a; source .env; set +a
echo $FOUNDRY_PROJECT_ENDPOINT
```

---

## 7. Run the orchestrator

```powershell
python -m src.orchestrator
```

The sample task in [`src/orchestrator.py`](src/orchestrator.py)'s `main()` is:

> *"Triage incident INC-4291, apply the corrective action, then notify affected customers."*

Expected log flow:

```
Running 'vf-triage-team'...
Loaded 2 agents (vf-triage-tool-agent, vf-comms-agent); pattern=sequential
[sequential] -> vf-triage-tool-agent
Function name: get_incident            → site=MAN-372
Function name: fetch_telemetry         → prb_utilisation=0.92, ...
Function name: fetch_customer_impact   → total=1450
Function name: apply_change            → CHG-26632
[sequential] -> vf-comms-agent

===== Team Result =====
[vf-triage-tool-agent] { "incident_id": "INC-4291", "root_cause": "ran_congestion", ... }
[vf-comms-agent] Dear customer, ...
```

### 7.1 Run a custom task

Create a one-off runner in the project root:

```python
# run_once.py
import asyncio
from src.orchestrator import run_team

print(asyncio.run(run_team("Triage INC-5002 and notify affected customers.")))
```

```powershell
python run_once.py
```

---

## 8. Run the tests

Unit smoke test (no network):

```powershell
pytest
```

Full end-to-end (requires `FOUNDRY_PROJECT_ENDPOINT` + `az login`):

```powershell
pytest -m integration -s
```

---

## 9. Iterating on the agents

You **do not** need to touch Python to change agent behaviour:

- Change the orchestration pattern or the agent list → edit [`team.yaml`](team.yaml).
- Change instructions, model, or tool declarations for one agent → edit its
  file under [`agents/`](agents/).
- Change what a tool actually does → edit its implementation in
  [`src/tools.py`](src/tools.py). Tools are wired by name via `TOOL_REGISTRY`.

Re-run `python -m src.orchestrator` — no rebuild needed.

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `ValueError: FOUNDRY_PROJECT_ENDPOINT is not set` | `.env` wasn't loaded into the shell | Run the loader snippet in [§ 6.1](#61-load-env-into-the-shell). |
| `403 AuthenticationTypeDisabled — Key based authentication is disabled` | A stray `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` is set and the SDK is trying key auth against a token-only resource | Clear those env vars (see [§ 6](#6-configure-the-project)) and re-run. |
| `AuthenticationRequiredError` from `AzureCliCredential` | `az login` session expired or on the wrong tenant | `az login --tenant <tenant-id>`; re-check with `az account show`. |
| `400 Item 'fc_…' of type 'function_call' was provided without its required 'reasoning' item` | Reasoning model (gpt-5) + multi-agent conversation forwarding | The `sequential` path in this repo already forwards **text only** between agents to avoid this. If it comes back, confirm you're running the version of [`src/orchestrator.py`](src/orchestrator.py) that has `_run_sequential`. |
| `Skipping MCP tool '…' (403 Forbidden)` | The agent's YAML references a hosted MCP endpoint your identity can't reach | Fine to ignore — the orchestrator skips unreachable MCP tools and keeps running. To silence, remove the tool block from the agent YAML. |
| `ModuleNotFoundError: agent_framework` | Not in the virtual environment, or deps not installed | `.\.venv\Scripts\Activate.ps1` (or `source .venv/bin/activate`), then `pip install -r requirements.txt`. |
| `PSSecurityException` activating the venv on Windows | PowerShell script execution disabled | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` (once). |

---

## 11. What the auth model actually is

- The orchestrator prefers `FOUNDRY_PROJECT_ENDPOINT` and always uses
  `AzureCliCredential` (your `az login` identity) — **no API keys**.
- If `FOUNDRY_PROJECT_ENDPOINT` is unset but `AZURE_OPENAI_ENDPOINT` is set, it
  falls back to Azure OpenAI, still with token auth (`api_key=None` is passed
  explicitly so a stray `AZURE_OPENAI_API_KEY` cannot hijack the call).
- Whichever identity you `az login` with must have RBAC on the Foundry project
  (usually **Azure AI Developer** or **Cognitive Services User**).

That's it — you're up.
