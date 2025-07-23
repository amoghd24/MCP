import os
import asyncio
from slack_bolt import App
from slack_bolt.adapter.socket_mode.builtin import SocketModeHandler
from dotenv import load_dotenv
from app import MCPLangChainClient

load_dotenv(".env")

# Initialize Slack app
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

def get_mcp_response(query):
    """Get response from MCP client - sync wrapper"""
    async def process():
        # Create fresh client each time to avoid event loop issues
        client = MCPLangChainClient()
        await client.connect_to_server("src/server.py")
        response = await client.process_query(query)
        await client.cleanup()
        return response
    
    return asyncio.run(process())

@app.event("app_mention")
def handle_mention(event, say):
    user_id = event.get("user")
    text = event.get("text", "").strip()
    
    # Remove bot mention
    import re
    text = re.sub(r'<@\w+>', '', text).strip()
    
    if not text:
        say("Hi! How can I help you?", thread_ts=event.get("ts"))
        return
    
    # Process query and respond
    response = get_mcp_response(text)
    say(f"<@{user_id}> {response}", thread_ts=event.get("ts"))

@app.event("message")
def handle_dm(event, say):
    # Only respond to DMs
    if event.get("channel_type") != "im":
        return
    
    # Skip bot messages
    if event.get("bot_id"):
        return
        
    text = event.get("text", "").strip()
    if not text:
        return
    
    # Process query and respond
    response = get_mcp_response(text)
    say(response)

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start() 