# Billing Mock MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server that **mocks the Vodafone
care-billing APIs** an AI agent calls during a billing conversation. It lets you build and test a
Foundry billing agent end to end **without the real backend**.

The mocked responses are shaped from the client actions in
[`../../data/extracted_billing_actions.json`](../../data/extracted_billing_actions.json) and use the
same response envelope the workflow reads:

```json
{ "status": { "httpStatus": 200 }, "output": { /* ... */ } }
```

## Tools

| MCP tool | Upstream API | Returns |
| --- | --- | --- |
| `get_billing_profiles` | `getBillingProfiles` | `output.billProfileList[]` — drives single- vs multi-account journeys |
| `get_billing_data` | Consolidated workflow tool | current bill, previous bills, and subscriptions keyed by requested data type |
| `get_month_bill_summary` | `getMonthBillSummary` | total, `billStatus`, `billType`, `billMonth`, date range, in/out-of-plan charges, payment message |
| `get_previous_bills` | `getPreviousBills` | previous bill summaries + billed subscriptions |
| `get_subscription_details` | `getSubscriptionDetails` | per-subscription plan, allowances, add-ons, out-of-plan charges |

Each tool takes `msisdn` (and optional `account_no` / `month`) plus a **`scenario`** argument so the
agent — or your tests — can exercise different paths:

| Tool | Scenarios |
| --- | --- |
| `get_billing_profiles` | `single_account` (default), `multi_account`, `no_response` |
| `get_month_bill_summary` | `paid` (default), `pending`, `unpaid`, `first_bill` |
| `get_previous_bills` | `default` |
| `get_subscription_details` | `default` |

The mock data lives in [`mock_data/billing_fixtures.json`](mock_data/billing_fixtures.json) — edit that
file to change what the server returns; no code changes needed.

## Run it

```bash
pip install -r requirements.txt

# Remote / streamable HTTP (use this from a Foundry hosted agent)
python server.py                 # -> http://localhost:8000/mcp

# Local stdio (MCP Inspector / desktop clients)
$env:MCP_TRANSPORT="stdio"; python server.py     # PowerShell
MCP_TRANSPORT=stdio python server.py             # bash

# Sanity check without a transport
python server.py selftest
```

Inspect interactively:

```bash
npx @modelcontextprotocol/inspector python server.py
```

## Test with a natural-language query (agent client)

[`agent_client.py`](agent_client.py) is a small **agent** that takes a plain-English question,
connects to this MCP server, lets an LLM pick and call the right tool, and answers in natural
language.

```powershell
pip install -r requirements-client.txt

# Configure a model — Azure OpenAI (uses your az login, no keys):
$env:AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com/"
$env:AZURE_OPENAI_CHAT_DEPLOYMENT_NAME="gpt-4o"      # your chat deployment
az login

# Ask a question (defaults to the deployed Container Apps endpoint)
python agent_client.py "What billing accounts do I have?"

# Or interactive mode
python agent_client.py
```

Point it at a different MCP server with `BILLING_MCP_URL`. Model authentication
always uses the active Azure CLI session; API keys are not supported.

Example:

```
🧑 What billing accounts do I have?
🤖 You have one billing account: 0123456789 (J. Smith, consumer) —
   billing address 1 High Street, Manchester, M1 1AA.
```

## Connect it to a Foundry agent

This repo's generator wires remote MCP tools via `MCPStreamableHTTPTool`. Point an agent at the
server's `/mcp` endpoint, or declare it in an agent YAML:

```yaml
tools:
  - type: mcp
    server_label: billing_mock
    server_url: http://localhost:8000/mcp        # or your deployed URL
    project_connection_id: billing-mock-mcp
```

## Deploy (optional)

The included `Dockerfile` serves the streamable-HTTP transport on port 8000 and is ready for Azure
Container Apps or any container host:

```bash
docker build -t billing-mock-mcp .
docker run -p 8000:8000 billing-mock-mcp
```

### Live deployment (Azure Container Apps)

Deployed to resource group `rg-faismali-2540` (UK South), environment `faismaliacaenv`:

```
MCP endpoint:  https://billing-mock-mcp.lemonisland-dc9bf8c5.uksouth.azurecontainerapps.io/mcp
```

Deployed with (build in ACR, then create the app):

```bash
az acr build --registry ca5398e05564acr --image billing-mock-mcp:v1 .

az containerapp create \
  --name billing-mock-mcp \
  --resource-group rg-faismali-2540 \
  --environment faismaliacaenv \
  --image ca5398e05564acr.azurecr.io/billing-mock-mcp:v1 \
  --registry-server ca5398e05564acr.azurecr.io \
  --ingress external --target-port 8000 \
  --min-replicas 1 --max-replicas 3 \
  --env-vars MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0 MCP_PORT=8000
```

To ship a new version, rebuild and update:

```bash
az acr build --registry ca5398e05564acr --image billing-mock-mcp:v2 .
az containerapp update -n billing-mock-mcp -g rg-faismali-2540 \
  --image ca5398e05564acr.azurecr.io/billing-mock-mcp:v2
```

## Layout

```
billing_mock_mcp/
  server.py                    # FastMCP server + 4 mocked tools
  mock_data/
    billing_fixtures.json      # editable canned responses, keyed by tool + scenario
  requirements.txt
  pyproject.toml
  Dockerfile
  .env.example
```

> **Mock only.** No real customer data or backend calls — safe for demos, local dev, and CI.
