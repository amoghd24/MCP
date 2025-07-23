import os
import asyncio
from slack_bolt import App
from slack_bolt.adapter.socket_mode.builtin import SocketModeHandler
from dotenv import load_dotenv
from app import MCPLangChainClient
import re

load_dotenv(".env")

# Initialize Slack app
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

def convert_to_slack_mrkdwn(text):
    """Convert HTML-style markdown to Slack mrkdwn format"""
    # Replace headers
    text = re.sub(r'^#{4}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)  # #### to bold
    text = re.sub(r'^#{3}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)  # ### to bold
    text = re.sub(r'^#{2}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)  # ## to bold
    text = re.sub(r'^#{1}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)  # # to bold
    
    # Replace bold markers
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)  # **text** to *text*
    
    # Replace numbered lists
    text = re.sub(r'^\d+\.\s+', '• ', text, flags=re.MULTILINE)  # 1. to bullet
    
    # Replace inline code
    text = re.sub(r'`([^`]+)`', r'`\1`', text)  # Keep inline code as is
    
    # Replace strikethrough
    text = re.sub(r'~~(.+?)~~', r'~\1~', text)  # ~~text~~ to ~text~
    
    # Clean up excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text

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
    text = re.sub(r'<@\w+>', '', text).strip()
    
    if not text:
        say("Hi! How can I help you?", thread_ts=event.get("ts"))
        return
    
    # Process query and respond
    response = get_mcp_response(text)
    # Convert response to Slack mrkdwn format
    slack_formatted_response = convert_to_slack_mrkdwn(response)
    say(f"<@{user_id}> {slack_formatted_response}", thread_ts=event.get("ts"))

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
    # Convert response to Slack mrkdwn format
    slack_formatted_response = convert_to_slack_mrkdwn(response)
    say(slack_formatted_response)

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start() 