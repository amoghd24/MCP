import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Import the LangChain client from app.py
from app import MCPLangChainClient

# Load environment variables
load_dotenv(".env")

# Create FastAPI app
app = FastAPI(
    title="MCP Integration Hub API",
    description="API for processing natural language queries with MCP tools",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modify this in production to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a global client instance
mcp_client = MCPLangChainClient()
client_initialized = False

class QueryRequest(BaseModel):
    query: str
    model: Optional[str] = "gpt-4o"

class QueryResponse(BaseModel):
    response: str

class ToolInfo(BaseModel):
    name: str
    description: str
    inputSchema: Optional[Dict[str, Any]] = None

class ToolsResponse(BaseModel):
    tools: List[ToolInfo]

@app.post("/api/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Process a natural language query using the LangChain agent with MCP tools."""
    global client_initialized
    
    try:
        # Initialize the client if not already done
        if not client_initialized:
            await mcp_client.connect_to_server("src/server.py")
            client_initialized = True
        
        # Process the query
        response = await mcp_client.process_query(request.query)
        
        return {"response": response}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.get("/api/tools", response_model=ToolsResponse)
async def get_tools():
    """Get all available tools from the MCP server."""
    global client_initialized
    
    try:
        # Initialize the client if not already done
        if not client_initialized:
            await mcp_client.connect_to_server("src/server.py")
            client_initialized = True
        
        # Get available tools
        tools_result = await mcp_client.session.list_tools()
        
        # Format the tools
        tools = []
        for tool in tools_result.tools:
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema
            })
        
        return {"tools": tools}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting tools: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources when the app shuts down."""
    await mcp_client.cleanup()

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "MCP Integration Hub API",
        "version": "1.0.0",
        "status": "operational"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True) 