"""
Authentication middleware for MCP server
"""

from typing import Optional, Dict
import os
from datetime import datetime
from cryptography.fernet import Fernet
import json
import base64


class AuthManager:
    """Manage authentication and token encryption"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        # Generate or use provided encryption key
        if encryption_key:
            self.cipher_key = encryption_key.encode()
        else:
            # Generate a new key if none provided
            self.cipher_key = Fernet.generate_key()
        
        self.cipher = Fernet(self.cipher_key)
    
    def encrypt_tokens(self, user_id: str, tokens: Dict[str, str]) -> str:
        """Encrypt user tokens for secure storage"""
        data = {
            "user_id": user_id,
            "tokens": tokens,
            "timestamp": datetime.utcnow().isoformat()
        }
        json_data = json.dumps(data)
        encrypted = self.cipher.encrypt(json_data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_tokens(self, encrypted_data: str) -> Optional[Dict[str, str]]:
        """Decrypt and return user tokens"""
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(decoded)
            data = json.loads(decrypted.decode())
            return data.get("tokens", {})
        except Exception as e:
            print(f"Failed to decrypt tokens: {e}")
            return None
    
    def validate_api_key(self, api_key: str) -> bool:
        """Validate an API key for server access"""
        # TODO: Implement actual API key validation
        # For now, just check if it's not empty
        return bool(api_key and len(api_key) > 10)
    
    def generate_api_key(self) -> str:
        """Generate a new API key"""
        import secrets
        return f"mcp_{secrets.token_urlsafe(32)}" 