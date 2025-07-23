import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional, Type

import nest_asyncio
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# LangChain imports
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

# Judgeval imports for tracing - TEMPORARILY DISABLED
# from judgeval.tracer import Tracer, wrap

# Apply nest_asyncio to allow nested event loops (needed for Jupyter/IPython)
nest_asyncio.apply()

# Load environment variables
load_dotenv(".env")

# Initialize Judgeval tracer - TEMPORARILY DISABLED
# judgment = Tracer(project_name="mcp-integration-hub")

# Dummy decorator to replace @judgment.observe
def dummy_observe(span_type=None):
    def decorator(func):
        return func
    return decorator

# Replace judgment with dummy
class DummyJudgment:
    def observe(self, span_type=None):
        return dummy_observe(span_type)

judgment = DummyJudgment()


def create_pydantic_model_from_schema(name: str, schema: Dict[str, Any]) -> Type[BaseModel]:
    """Create a Pydantic model from a JSON schema."""
    fields = {}
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    for field_name, field_info in properties.items():
        field_type = str  # Default to string
        description = field_info.get("description", "")
        
        # Map JSON schema types to Python types
        if field_info.get("type") == "string":
            field_type = str
        elif field_info.get("type") == "integer":
            field_type = int
        elif field_info.get("type") == "number":
            field_type = float
        elif field_info.get("type") == "boolean":
            field_type = bool
        elif field_info.get("type") == "array":
            field_type = List[str]  # Simplified - assume list of strings
        
        # Create field with optional/required handling
        if field_name in required:
            fields[field_name] = (field_type, Field(..., description=description))
        else:
            fields[field_name] = (Optional[field_type], Field(None, description=description))
    
    return create_model(f"{name}Arguments", **fields)


class MCPLangChainClient:
    """Client for interacting with LangChain agents using MCP tools."""

    def __init__(self, model: str = "gpt-4o"):
        """Initialize the LangChain MCP client.

        Args:
            model: The OpenAI model to use.
        """
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
        # Initialize OpenAI client - TRACING DISABLED
        self.llm = ChatOpenAI(model=model, temperature=0)
        # Removed judgeval wrapping that was causing issues
        
        self.stdio: Optional[Any] = None
        self.write: Optional[Any] = None
        self.agent_executor = None

    @judgment.observe(span_type="function")
    async def connect_to_server(self, server_script_path: str = "src/server.py"):
        """Connect to an MCP server and set up LangChain tools.

        Args:
            server_script_path: Path to the server script.
        """
        # Set environment to use stdio transport
        import os
        env = os.environ.copy()
        env["TRANSPORT"] = "stdio"
        
        # Server configuration
        server_params = StdioServerParameters(
            command="python",
            args=[server_script_path],
            env=env  # Pass the environment with stdio transport
        )

        # Connect to the server
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        # Initialize the connection
        await self.session.initialize()

        # List available tools and convert to LangChain format
        tools_result = await self.session.list_tools()
        
        # Create LangChain tools from MCP tools
        langchain_tools = []
        for tool in tools_result.tools:
            
            # Create a function that calls the MCP tool - FIXED VERSION
            def create_tool_func(tool_name: str):
                async def tool_func(**kwargs) -> str:
                    try:
                        result = await self.session.call_tool(tool_name, arguments=kwargs)
                        return result.content[0].text
                    except Exception as e:
                        return f"Error executing tool {tool_name}: {str(e)}"
                return tool_func
            
            # Create the Pydantic model for arguments
            args_model = create_pydantic_model_from_schema(
                tool.name, 
                tool.inputSchema or {"properties": {}, "required": []}
            )
            
            # Create a StructuredTool - FIXED: Don't await the function creation!
            lc_tool = StructuredTool(
                name=tool.name,
                description=tool.description,
                args_schema=args_model,
                coroutine=create_tool_func(tool.name)  # Remove await here!
            )
            langchain_tools.append(lc_tool)
        
        # Create the ReAct agent
        self.agent_executor = create_react_agent(
            self.llm, 
            langchain_tools,
            state_modifier="""You are a proactive analytics assistant specializing in data analysis and dashboard creation.

IMPORTANT INSTRUCTIONS:
1. Always USE available tools to gather actual data rather than giving generic responses
2. When asked to create dashboards or analyze data, immediately start using tools to collect information
3. For Amplitude analytics, start by discovering available events using get_amplitude_events_list
4. Then proceed with specific analysis based on the user's requirements
5. Be thorough and provide actual data-driven insights, not just plans or suggestions

Available tools include Amplitude analytics, Notion, Slack, and GitHub integrations. Use them actively to fulfill user requests."""
        )

    @judgment.observe(span_type="agent_query")
    async def process_query(self, query: str) -> str:
        """Process a query using the LangChain ReAct agent with detailed tracing.

        Args:
            query: The user query.

        Returns:
            The response from the agent.
        """
        if not self.agent_executor:
            raise ValueError("Agent not initialized. Call connect_to_server first.")
        
        # Execute ReAct agent with streaming to capture reasoning steps
        agent_input = {"messages": [HumanMessage(content=query)]}
        final_response = ""
        last_agent_message = ""
        
        print("\n=== AGENT REASONING TRACE ===")
        
        # Stream the agent execution to capture reasoning steps
        async for chunk in self.agent_executor.astream(agent_input):
            # Print agent thoughts/reasoning
            if 'agent' in chunk:
                messages = chunk['agent'].get('messages', [])
                for message in messages:
                    if hasattr(message, 'content') and message.content.strip():
                        print(f"💭 THOUGHT: {message.content}")
                        # Capture the last meaningful agent message
                        if not hasattr(message, 'tool_calls') or not message.tool_calls:
                            last_agent_message = message.content
                    # Print tool calls (actions)
                    if hasattr(message, 'tool_calls') and message.tool_calls:
                        for tool_call in message.tool_calls:
                            print(f"🔧 ACTION: {tool_call['name']}({tool_call['args']})")
            
            # Print tool results (observations)
            if 'tools' in chunk:
                messages = chunk['tools'].get('messages', [])
                for message in messages:
                    if hasattr(message, 'content'):
                        print(f"📝 OBSERVATION: {message.content}")
            
            # Capture final response from __end__ chunk
            if '__end__' in chunk:
                if chunk['__end__']['messages']:
                    final_response = chunk['__end__']['messages'][-1].content
        
        print("=== END REASONING TRACE ===\n")
        
        # Use the last agent message if the __end__ chunk is empty
        if not final_response.strip() and last_agent_message:
            final_response = last_agent_message
            
        return final_response

    @judgment.observe(span_type="agent_init")
    async def _init_agent_input(self, query: str):
        """Initialize agent input with tracing"""
        messages = [HumanMessage(content=query)]
        return {"messages": messages}

    @judgment.observe(span_type="final_response")
    async def _get_final_response(self, agent_input):
        """Get final response with tracing"""
        # Simplified without duplicate execution
        result = await self.agent_executor.ainvoke(agent_input)
        return result["messages"][-1].content

    @judgment.observe(span_type="agent_reasoning")
    async def _trace_agent_reasoning(self, agent_chunk):
        """Trace agent's reasoning steps"""
        # Disabled - no tracing
        pass

    @judgment.observe(span_type="tool_execution")
    async def _trace_tool_calls(self, tools_chunk):
        """Trace individual tool calls"""
        # Disabled - no tracing
        pass

    async def _trace_individual_tool(self, tool_name: str, tool_response: str):
        """Trace a specific tool call"""
        # Disabled - no tracing
        pass

    @judgment.observe(span_type="cleanup")
    async def cleanup(self):
        """Clean up resources."""
        await self.exit_stack.aclose()


@judgment.observe(span_type="function")
async def main():
    """Main entry point for the client."""
    client = MCPLangChainClient()
    
    try:
        # Connect to the MCP server
        # Connect to the MCP server
        await client.connect_to_server("src/server.py")
        
        # Execute the GitHub PR analysis and Slack notification query
     
        # Process query
        
        # Test the new users tool
        query_test = """
        Can you give me rolling retention report for the week of 14july 2025 to 20 july 2025. 

        

            """        
        response = await client.process_query(query_test)
        print(f"\nFinal Response: {response}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up resources
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main()) 