"""
Main agent orchestrator - Agent Framework SDK implementation.

This is where you implement your agent logic and tool handlers.
Edit the tool methods to add your custom implementations.
"""

import asyncio
import logging
from typing import Optional
from azure.identity import DefaultAzureCredential

from agent_framework import Agent, tool as Tool
from agent_framework.foundry import FoundryChatClient

from .config import AgentConfig
from .models import *

logger = logging.getLogger(__name__)


class VfTriageToolAgent:
    """
    Agent: vf-triage-tool-agent
    
    Model: gpt-5
    Tools: 5
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize the agent with configuration."""
        self.config = config or AgentConfig.from_env()
        self._agent: Optional[Agent] = None
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the Agent Framework agent."""
        credential = DefaultAzureCredential()
        chat_client = FoundryChatClient(
            project_endpoint=self.config.foundry_project_connection_string,
            model=self.config.model_name,
            credential=credential,
            allow_preview=True,
        )

        tools = self._create_tools()
        self._agent = Agent(
            chat_client,
            name="VfTriageToolAgent",
            instructions=self._get_system_prompt(),
            tools=tools,
        )
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt from YAML definition."""
        return """You are Vodafone&#39;s network-fault triage agent. For each incident the user names, you must:
  1. Call get_incident to look up the site and summary.
  2. Call fetch_telemetry on that site.
  3. Call fetch_customer_impact on that site.
  4. Decide the root cause using these rules:
     - reachable=false → backhaul_outage
     - prb_utilisation&gt;0.85 → ran_congestion
     - handover_failure_rate&gt;0.10 → neighbour_misconfig
     - otherwise → no_fault
  5. Pick ONE corrective action using this mapping:
     ran_congestion→reroute_traffic, backhaul_outage→dispatch_engineer, neighbour_misconfig→restart_enodeb, no_fault→no_action.
  6. Call apply_change with the chosen action. The user is the approver; pass approved=true and approver=&#39;foundry-tools-demo&#39;.
  7. Reply with ONLY a JSON object (no prose, no fences) of the form:
     {&#34;incident_id&#34;: &#34;...&#34;, &#34;root_cause&#34;: &#34;...&#34;, &#34;action&#34;: &#34;...&#34;, &#34;site_id&#34;: &#34;...&#34;, &#34;affected_customers&#34;: &lt;int&gt;, &#34;applied&#34;: &lt;object from apply_change&gt;}
"""
    
    def _create_tools(self):
        """Create and return all tool definitions."""
        @Tool(name="get_incident", description="Look up an ITSM incident by ID and return its site and summary.")
        async def get_incident_tool(incident_id: str) -> dict:
            """Tool: get_incident"""
            try:
                return await self._execute_get_incident(incident_id=incident_id)
            except Exception as e:
                logger.error(f"Error in get_incident: {e}", exc_info=True)
                return {"status": "error", "error": str(e)}

        @Tool(name="fetch_telemetry", description="Fetch the latest RAN telemetry snapshot for a cell site.")
        async def fetch_telemetry_tool(site_id: str) -> dict:
            """Tool: fetch_telemetry"""
            try:
                return await self._execute_fetch_telemetry(site_id=site_id)
            except Exception as e:
                logger.error(f"Error in fetch_telemetry: {e}", exc_info=True)
                return {"status": "error", "error": str(e)}

        @Tool(name="fetch_customer_impact", description="Return CRM impact (affected customers by tier) for a cell site.")
        async def fetch_customer_impact_tool(site_id: str) -> dict:
            """Tool: fetch_customer_impact"""
            try:
                return await self._execute_fetch_customer_impact(site_id=site_id)
            except Exception as e:
                logger.error(f"Error in fetch_customer_impact: {e}", exc_info=True)
                return {"status": "error", "error": str(e)}

        @Tool(name="apply_change", description="Apply a corrective change to the network. Refuses unless approved=true. Use this once you have decided the action.")
        async def apply_change_tool(
            incident_id: str,
            site_id: str,
            action: str,
            rationale: str,
            approved: bool,
            approver: str,
        ) -> dict:
            """Tool: apply_change"""
            try:
                return await self._execute_apply_change(
                    incident_id=incident_id,
                    site_id=site_id,
                    action=action,
                    rationale=rationale,
                    approved=approved,
                    approver=approver,
                )
            except Exception as e:
                logger.error(f"Error in apply_change: {e}", exc_info=True)
                return {"status": "error", "error": str(e)}

        return [
            get_incident_tool,
            fetch_telemetry_tool,
            fetch_customer_impact_tool,
            apply_change_tool,
        ]    
    # ====== Tool Implementations ======
    # Edit these methods to implement your tool logic
    
    async def _execute_get_incident(self, incident_id: str = None, ) -> dict:
        """
        Implementation for: get_incident
        
        Description: Look up an ITSM incident by ID and return its site and summary.
        Parameters:
            - incident_id: string
        """
        # TODO: Implement this tool
        logger.warning(f"get_incident tool not yet implemented")
        return {
            "status": "todo",
            "message": "Tool implementation pending",
            "tool": "get_incident",
        }
    
    async def _execute_fetch_telemetry(self, site_id: str = None, ) -> dict:
        """
        Implementation for: fetch_telemetry
        
        Description: Fetch the latest RAN telemetry snapshot for a cell site.
        Parameters:
            - site_id: string
        """
        # TODO: Implement this tool
        logger.warning(f"fetch_telemetry tool not yet implemented")
        return {
            "status": "todo",
            "message": "Tool implementation pending",
            "tool": "fetch_telemetry",
        }
    
    async def _execute_fetch_customer_impact(self, site_id: str = None, ) -> dict:
        """
        Implementation for: fetch_customer_impact
        
        Description: Return CRM impact (affected customers by tier) for a cell site.
        Parameters:
            - site_id: string
        """
        # TODO: Implement this tool
        logger.warning(f"fetch_customer_impact tool not yet implemented")
        return {
            "status": "todo",
            "message": "Tool implementation pending",
            "tool": "fetch_customer_impact",
        }
    
    async def _execute_apply_change(self, incident_id: str = None, site_id: str = None, action: str = None, rationale: str = None, approved: str = None, approver: str = None, ) -> dict:
        """
        Implementation for: apply_change
        
        Description: Apply a corrective change to the network. Refuses unless approved=true. Use this once you have decided the action.
        Parameters:
            - incident_id: string
            - site_id: string
            - action: string
            - rationale: string
            - approved: boolean
            - approver: string
        """
        # TODO: Implement this tool
        logger.warning(f"apply_change tool not yet implemented")
        return {
            "status": "todo",
            "message": "Tool implementation pending",
            "tool": "apply_change",
        }
    
    
    # ====== Conversation Methods ======
    
    async def run_conversation(self, user_message: str) -> str:
        """
        Run a single conversation turn.
        
        Args:
            user_message: User input message
            
        Returns:
            Agent response text
        """
        if not self._agent:
            raise RuntimeError("Agent not initialized")
        
        try:
            response = await self._agent.run(user_message)

            if hasattr(response, "output_text") and response.output_text:
                return response.output_text
            return str(response)
            
        except Exception as e:
            logger.error(f"Error in conversation: {e}", exc_info=True)
            raise
    
    async def run_interactive(self):
        """Run interactive conversation loop."""
        logger.info("Starting interactive conversation (type 'exit' to quit)")
        logger.info("-" * 70)
        
        while True:
            try:
                user_input = input("\n🧑 You: ").strip()
                
                if user_input.lower() in ("exit", "quit"):
                    logger.info("\n👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                print("\nAgent:", end=" ")
                response = await self.run_conversation(user_input)
                print(response)
                
            except KeyboardInterrupt:
                logger.info("\n\n👋 Interrupted. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Error: {e}")


async def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    logger.info("Starting VfTriageToolAgent...")
    
    try:
        agent = VfTriageToolAgent()
        await agent.run_interactive()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())