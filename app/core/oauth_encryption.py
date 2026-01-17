"""
OAuth Token Encryption for Intuit QuickBooks Go-Live Compliance.

Implements AES encryption for OAuth tokens as required by Intuit security requirements:
- Encrypt refresh tokens with symmetric algorithm (AES preferred)
- Store AES key separately from encrypted data
- Support key rotation

Reference: https://developer.intuit.com/app/developer/qbo/docs/go-live/publish-app/security-requirements
"""

import base64
import logging
import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

logger = logging.getLogger(__name__)


class OAuthTokenEncryption:
    """
    Encryption service for OAuth tokens (refresh tokens, access tokens).

    Uses Fernet (AES-128-CBC with HMAC) for symmetric encryption.
    Key is stored separately in environment variable as required by Intuit.
    """

    def __init__(self):
        self._cipher = self._initialize_cipher()

    def _initialize_cipher(self) -> MultiFernet:
        """
        Initialize the Fernet cipher with OAuth encryption keys.

        Keys are stored in environment variables:
        - OAUTH_ENCRYPTION_KEY: Primary key for encryption/decryption
        - OAUTH_ENCRYPTION_KEY_OLD: Previous key for decryption during rotation
        """
        keys = []

        # Primary OAuth encryption key (separate from PII key as per Intuit requirements)
        primary_key = os.getenv("OAUTH_ENCRYPTION_KEY")
        if primary_key:
            try:
                keys.append(Fernet(primary_key.encode()))
            except Exception as e:
                logger.error(f"Invalid OAUTH_ENCRYPTION_KEY: {e}")
                raise ValueError(
                    "OAUTH_ENCRYPTION_KEY is invalid. Generate with: "
                    "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )

        # Old key for rotation (optional)
        old_key = os.getenv("OAUTH_ENCRYPTION_KEY_OLD")
        if old_key:
            try:
                keys.append(Fernet(old_key.encode()))
            except Exception as e:
                logger.warning(f"Invalid OAUTH_ENCRYPTION_KEY_OLD: {e}")

        # Development fallback - generate ephemeral key
        if not keys:
            environment = os.getenv("ENVIRONMENT", "development")
            if environment == "production":
                raise ValueError(
                    "OAUTH_ENCRYPTION_KEY must be set in production. "
                    "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )
            logger.warning(
                "OAUTH_ENCRYPTION_KEY not set - using ephemeral key. "
                "OAuth tokens will NOT persist across restarts!"
            )
            keys.append(Fernet(Fernet.generate_key()))

        return MultiFernet(keys)

    def encrypt_token(self, token: str) -> str:
        """
        Encrypt an OAuth token.

        Args:
            token: The OAuth token to encrypt (access_token or refresh_token)

        Returns:
            Base64-encoded encrypted token with prefix for identification
        """
        if not token:
            return ""

        # Check if already encrypted (has our prefix)
        if token.startswith("enc:"):
            return token

        try:
            encrypted = self._cipher.encrypt(token.encode())
            # Add prefix to identify encrypted tokens
            return f"enc:{base64.urlsafe_b64encode(encrypted).decode()}"
        except Exception as e:
            logger.error(f"OAuth token encryption failed: {e}")
            raise ValueError("Failed to encrypt OAuth token")

    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt an OAuth token.

        Args:
            encrypted_token: The encrypted token (with enc: prefix)

        Returns:
            Original token string
        """
        if not encrypted_token:
            return ""

        # Handle unencrypted tokens (for backwards compatibility during migration)
        if not encrypted_token.startswith("enc:"):
            logger.debug("Token not encrypted, returning as-is (migration pending)")
            return encrypted_token

        try:
            # Remove prefix and decode
            token_data = encrypted_token[4:]  # Remove "enc:" prefix
            decoded = base64.urlsafe_b64decode(token_data.encode())
            decrypted = self._cipher.decrypt(decoded)
            return decrypted.decode()
        except InvalidToken:
            logger.error("OAuth token decryption failed - invalid token or wrong key")
            raise ValueError("Failed to decrypt OAuth token - invalid key or corrupted data")
        except Exception as e:
            logger.error(f"OAuth token decryption failed: {e}")
            raise ValueError("Failed to decrypt OAuth token")

    def is_encrypted(self, token: str) -> bool:
        """Check if a token is encrypted."""
        return token.startswith("enc:") if token else False


@lru_cache()
def get_oauth_encryption() -> OAuthTokenEncryption:
    """Get singleton instance of OAuth encryption service."""
    return OAuthTokenEncryption()


# Convenience functions
def encrypt_oauth_token(token: str) -> str:
    """Encrypt an OAuth token."""
    return get_oauth_encryption().encrypt_token(token)


def decrypt_oauth_token(encrypted_token: str) -> str:
    """Decrypt an OAuth token."""
    return get_oauth_encryption().decrypt_token(encrypted_token)


def is_token_encrypted(token: str) -> bool:
    """Check if a token is encrypted."""
    return get_oauth_encryption().is_encrypted(token)
