# server.py
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP(
    name="calculator",
    host="0.0.0.0",
    port=8000
)


# Simple tool (calculator)
@mcp.tool()
def calculator(a: int, b: int) -> int:
    """Calculate the sum of two numbers"""
    return a + b

# Run the server
if __name__ == "__main__":
    print("Script started")
    transport= "sse"
    print(f"Transport: {transport}")
    if transport == "stdio":
        print("Starting MCP server on stdio")
        mcp.run(transport="stdio")
    elif transport == "sse":
        print("Starting MCP server on sse")
        try:
            mcp.run(transport="sse")
        except Exception as e:
            print(f"Error starting server: {e}")
    else:
        print("Invalid transport")
        exit(1)
    print("Script ending")
        