"""
Configuration settings for MCP Integration Server
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Server Configuration
    server_name: str = "mcp-integration-hub"
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    transport: str = "sse"  # "sse" or "stdio"
    
    # API Keys (Optional - can be provided per request)
    notion_api_key: Optional[str] = None
    slack_bot_token: Optional[str] = None
    github_token: Optional[str] = None
    openai_api_key: Optional[str] = None  # Added for MCP client testing
    
    # Judgeval Configuration (Optional - for tracing and monitoring)
    judgment_api_key: Optional[str] = None
    judgment_org_id: Optional[str] = None
    judgment_api_url: Optional[str] = None  # For self-hosted instances
    
    # Security
    encryption_key: Optional[str] = None
    enable_auth: bool = True
    
    # Rate Limiting
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 10
    
    # Caching
    cache_ttl_seconds: int = 300  # 5 minutes
    redis_url: Optional[str] = None
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Create a singleton instance
settings = Settings() 