"""
Billing MCP Agent Client
========================

A minimal *agent* that takes a natural-language query (e.g. "What billing
accounts do I have?"), connects to the deployed Billing Mock MCP server, lets the
LLM decide which billing tool to call, and prints a plain-language answer.

    User query ──► LLM (function calling) ──► MCP tools on Azure Container Apps
                        ▲                          │
                        └────── tool results ──────┘

Model configuration (pick ONE):

  Azure OpenAI (recommended — uses your `az login`, no keys):
      set AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
      set AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<your-chat-deployment>   # e.g. gpt-4o
      # optional: set AZURE_OPENAI_API_VERSION=2024-10-21

  OpenAI:
      set OPENAI_API_KEY=sk-...
      set OPENAI_MODEL=gpt-4o           # optional, defaults to gpt-4o

MCP endpoint (defaults to the deployed Container App):
      set BILLING_MCP_URL=https://billing-mock-mcp.lemonisland-dc9bf8c5.uksouth.azurecontainerapps.io/mcp

Usage:
    python agent_client.py "What billing accounts do I have?"
    python agent_client.py            # interactive mode (type queries, 'exit' to quit)
"""

from __future__ import annotations

import asyncio
import os
import sys

from agent_framework import Agent, MCPStreamableHTTPTool

DEFAULT_MCP_URL = (
    "https://billing-mock-mcp.lemonisland-dc9bf8c5.uksouth.azurecontainerapps.io/mcp"
)

# A demo customer so the agent has something to look up. In a real app this would
# come from the authenticated session, not a constant.
DEMO_MSISDN = os.getenv("DEMO_MSISDN", "447700900123")
DEMO_ACCOUNT = os.getenv("DEMO_ACCOUNT", "0123456789")

SYSTEM_PROMPT = f"""
You are Vodafone's billing assistant. Answer the customer's billing questions by
calling the available tools, then reply in clear, friendly, plain English.

The signed-in customer:
  - mobile number (msisdn): {DEMO_MSISDN}
  - billing account number: {DEMO_ACCOUNT}
Always pass these to the tools unless the user gives different details.

Tool guidance:
  - "What billing accounts do I have?" / account questions -> get_billing_profiles
  - This month's / latest bill, amount, status, due date        -> get_month_bill_summary
  - Past bills / bill history                                    -> get_previous_bills
  - Plan, allowances, add-ons, out-of-plan charges              -> get_subscription_details

Scenario selection (IMPORTANT — set the tool's `scenario` argument from the user's words):
  Each tool accepts a `scenario` that picks which situation to return. Read the
  user's phrasing and pass the matching value. If they don't imply one, use the
  default shown in [brackets].

  get_billing_profiles.scenario:
    - single_account  [default]  -> one account
    - multi_account              -> "multiple accounts", "business account too", "more than one"
    - no_response                -> "simulate an outage/failure", "backend down"
  get_month_bill_summary.scenario:
    - paid        [default]      -> "paid", "settled"
    - pending                    -> "pending", "not taken yet", "upcoming Direct Debit"
    - unpaid                     -> "unpaid", "overdue", "owe", "outstanding"
    - first_bill                 -> "first bill", "new customer", "why is my first bill higher"
  get_previous_bills.scenario:        default
  get_subscription_details.scenario:  default

Summarise the JSON you get back — never show raw JSON to the customer. If a tool
returns a non-200 httpStatus, apologise and say the billing system is temporarily
unavailable.
""".strip()


def build_chat_client():
    """Create a chat client from environment configuration.

    Prefers Azure OpenAI (token auth via AzureCliCredential); falls back to OpenAI.
    """
    if os.getenv("AZURE_OPENAI_ENDPOINT"):
        from agent_framework.openai import OpenAIChatCompletionClient
        from azure.identity import AzureCliCredential, get_bearer_token_provider
        from openai import AsyncAzureOpenAI

        deployment = (
            os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
            or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        )
        if not deployment:
            sys.exit("Set AZURE_OPENAI_CHAT_DEPLOYMENT_NAME to your chat deployment name.")

        # Force Entra ID (CLI) auth — no API keys. Works even when the resource
        # has key-based authentication disabled. Drop any stray key env vars so the
        # OpenAI SDK can't silently fall back to key auth.
        os.environ.pop("AZURE_OPENAI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        token_provider = get_bearer_token_provider(
            AzureCliCredential(), "https://cognitiveservices.azure.com/.default"
        )
        async_client = AsyncAzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            azure_ad_token_provider=token_provider,
        )
        return OpenAIChatCompletionClient(model=deployment, async_client=async_client)

    if os.getenv("OPENAI_API_KEY"):
        from agent_framework.openai import OpenAIChatClient

        return OpenAIChatClient(model_id=os.getenv("OPENAI_MODEL", "gpt-4o"))

    sys.exit(
        "No model configured.\n"
        "  Azure OpenAI:  set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_CHAT_DEPLOYMENT_NAME "
        "(then `az login`)\n"
        "  or OpenAI:     set OPENAI_API_KEY"
    )


async def ask(agent: Agent, query: str) -> str:
    result = await agent.run(query)
    return getattr(result, "text", None) or str(result)


async def main() -> None:
    mcp_url = os.getenv("BILLING_MCP_URL", DEFAULT_MCP_URL)
    query = " ".join(sys.argv[1:]).strip()

    print(f"MCP server: {mcp_url}")
    chat_client = build_chat_client()

    # MCPStreamableHTTPTool discovers the server's tools and exposes them to the LLM.
    async with MCPStreamableHTTPTool(name="billing", url=mcp_url) as billing_tools:
        agent = Agent(
            client=chat_client,
            name="BillingAssistant",
            instructions=SYSTEM_PROMPT,
            tools=billing_tools,
        )

        if query:
            print(f"\n🧑 {query}")
            print(f"\n🤖 {await ask(agent, query)}")
            return

        print("Interactive mode — ask a billing question ('exit' to quit).")
        while True:
            try:
                q = input("\n🧑 You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Bye")
                break
            if q.lower() in ("exit", "quit"):
                print("👋 Bye")
                break
            if not q:
                continue
            print(f"\n🤖 {await ask(agent, q)}")


if __name__ == "__main__":
    asyncio.run(main())
