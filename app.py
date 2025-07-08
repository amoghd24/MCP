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

# Judgeval imports for tracing
from judgeval.tracer import Tracer, wrap

# Apply nest_asyncio to allow nested event loops (needed for Jupyter/IPython)
nest_asyncio.apply()

# Load environment variables
load_dotenv(".env")

# Initialize Judgeval tracer
judgment = Tracer(project_name="mcp-integration-hub")


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
        
        # Initialize OpenAI client with Judgeval tracing
        self.llm = ChatOpenAI(model=model, temperature=0)
        # Wrap the actual OpenAI client (not the completions resource)
        if hasattr(self.llm, '_client'):
            self.llm._client = wrap(self.llm._client)
        else:
            # Fallback: create wrapped OpenAI client directly
            from openai import OpenAI
            wrapped_client = wrap(OpenAI())
            self.llm.client = wrapped_client
        
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
        print("\nConnected to server with tools:")
        
        # Create LangChain tools from MCP tools
        langchain_tools = []
        for tool in tools_result.tools:
            print(f"  - {tool.name}: {tool.description}")
            
            # Create a function that calls the MCP tool
            async def create_tool_func(tool_name: str):
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
            
            # Create a StructuredTool
            lc_tool = StructuredTool(
                name=tool.name,
                description=tool.description,
                args_schema=args_model,
                coroutine=await create_tool_func(tool.name)
            )
            langchain_tools.append(lc_tool)
        
        # Create the ReAct agent
        self.agent_executor = create_react_agent(
            self.llm, 
            langchain_tools,
            state_modifier="You are a helpful assistant"
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
        
        print("\nExecuting ReAct agent...")
        
        # Initialize agent input
        agent_input = await self._init_agent_input(query)
        
        # Variable to store the final response
        self.final_response = None
        
        # Stream and trace each step
        async for chunk in self.agent_executor.astream(agent_input):
            if "agent" in chunk:
                await self._trace_agent_reasoning(chunk["agent"])
                # Capture the final response from the last agent message
                if chunk.get("agent", {}).get("messages"):
                    self.final_response = chunk["agent"]["messages"][-1].content
            
            if "tools" in chunk:
                await self._trace_tool_calls(chunk["tools"])
        
        # Get final response
        final_message = await self._get_final_response(agent_input)
        
        return final_message

    @judgment.observe(span_type="agent_init")
    async def _init_agent_input(self, query: str):
        """Initialize agent input with tracing"""
        messages = [HumanMessage(content=query)]
        return {"messages": messages}

    @judgment.observe(span_type="final_response")
    async def _get_final_response(self, agent_input):
        """Get final response with tracing"""
        # LEGACY: This causes a duplicate execution of the agent
        # result = await self.agent_executor.ainvoke(agent_input)
        # return result["messages"][-1].content
        
        # Return the captured final response
        if self.final_response:
            return self.final_response
        else:
            return "Task completed, but unable to capture the final response."

    @judgment.observe(span_type="agent_reasoning")
    async def _trace_agent_reasoning(self, agent_chunk):
        """Trace agent's reasoning steps"""
        for message in agent_chunk["messages"]:
            if hasattr(message, "content") and message.content:
                print(f"\nAgent: {message.content}")

    @judgment.observe(span_type="tool_execution")
    async def _trace_tool_calls(self, tools_chunk):
        """Trace individual tool calls"""
        for message in tools_chunk["messages"]:
            if hasattr(message, "name"):
                tool_name = message.name
                tool_response = message.content
                
                # Execute individual tool tracing
                await self._trace_individual_tool(tool_name, tool_response)

    async def _trace_individual_tool(self, tool_name: str, tool_response: str):
        """Trace a specific tool call"""
        # Create a dynamic span type for each tool
        @judgment.observe(span_type=f"tool_{tool_name}")
        async def execute_tool_trace():
            print(f"\nTool ({tool_name}): {tool_response[:200]}...")
        
        await execute_tool_trace()

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
        print("Connecting to MCP server...")
        await client.connect_to_server("src/server.py")
        
        # Execute the GitHub PR analysis and Slack notification query
        query = "Analyze all closed pull requests in amoghd24/MCP repo and send their titles and description on slack random channel. Your task is only complete once you send the message on slack. no need to add human in the loop"
        print(f"\nQuery: {query}")
        
        response = await client.process_query(query)
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