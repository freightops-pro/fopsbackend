"""
PII Encryption Service for Banking-Grade Security.

Provides field-level encryption for sensitive data:
- Social Security Numbers (SSN)
- Bank account numbers
- Tax IDs (EIN)
- Routing numbers

Uses Fernet symmetric encryption with key rotation support.
"""

import os
import base64
import logging
from typing import Optional
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

logger = logging.getLogger(__name__)


class PIIEncryptionService:
    """
    Encryption service for Personally Identifiable Information (PII).

    Implements:
    - AES-128-CBC encryption via Fernet
    - Key rotation support via MultiFernet
    - Automatic key generation for development
    - Masking utilities for display
    """

    def __init__(self):
        self._cipher = self._initialize_cipher()

    def _initialize_cipher(self) -> MultiFernet:
        """
        Initialize the Fernet cipher with encryption keys.

        Supports multiple keys for rotation:
        - PII_ENCRYPTION_KEY: Primary key (required in production)
        - PII_ENCRYPTION_KEY_OLD: Previous key for decryption during rotation
        """
        keys = []

        # Primary encryption key
        primary_key = os.getenv("PII_ENCRYPTION_KEY")
        if primary_key:
            try:
                keys.append(Fernet(primary_key.encode()))
            except Exception as e:
                logger.error(f"Invalid PII_ENCRYPTION_KEY: {e}")
                raise ValueError("PII_ENCRYPTION_KEY is invalid. Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")

        # Old key for rotation (optional)
        old_key = os.getenv("PII_ENCRYPTION_KEY_OLD")
        if old_key:
            try:
                keys.append(Fernet(old_key.encode()))
            except Exception as e:
                logger.warning(f"Invalid PII_ENCRYPTION_KEY_OLD: {e}")

        # Development fallback - generate ephemeral key
        if not keys:
            if os.getenv("ENVIRONMENT", "development") == "production":
                raise ValueError(
                    "PII_ENCRYPTION_KEY must be set in production. "
                    "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )
            logger.warning(
                "PII_ENCRYPTION_KEY not set - using ephemeral key. "
                "Data will NOT persist across restarts!"
            )
            keys.append(Fernet(Fernet.generate_key()))

        return MultiFernet(keys)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: The sensitive data to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""

        try:
            encrypted = self._cipher.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise ValueError("Failed to encrypt data")

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            ciphertext: The encrypted data

        Returns:
            Original plaintext string
        """
        if not ciphertext:
            return ""

        try:
            decoded = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = self._cipher.decrypt(decoded)
            return decrypted.decode()
        except InvalidToken:
            logger.error("Decryption failed - invalid token or wrong key")
            raise ValueError("Failed to decrypt data - invalid key or corrupted data")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data")

    def encrypt_ssn(self, ssn: str) -> tuple[str, str]:
        """
        Encrypt SSN and return both encrypted value and last 4 for display.

        Args:
            ssn: Full SSN (with or without dashes)

        Returns:
            Tuple of (encrypted_ssn, last_4_digits)
        """
        if not ssn:
            return "", ""

        # Normalize SSN (remove dashes/spaces)
        clean_ssn = "".join(c for c in ssn if c.isdigit())

        if len(clean_ssn) != 9:
            raise ValueError("SSN must be 9 digits")

        encrypted = self.encrypt(clean_ssn)
        last_4 = clean_ssn[-4:]

        return encrypted, last_4

    def encrypt_bank_account(self, account_number: str) -> tuple[str, str]:
        """
        Encrypt bank account number and return masked version for display.

        Args:
            account_number: Full bank account number

        Returns:
            Tuple of (encrypted_account, masked_account)
        """
        if not account_number:
            return "", ""

        # Normalize (remove spaces/dashes)
        clean_account = "".join(c for c in account_number if c.isdigit())

        if len(clean_account) < 4:
            raise ValueError("Account number too short")

        encrypted = self.encrypt(clean_account)
        # Show last 4 digits only
        masked = f"****{clean_account[-4:]}"

        return encrypted, masked

    def encrypt_tax_id(self, tax_id: str) -> tuple[str, str]:
        """
        Encrypt tax ID (EIN) and return masked version for display.

        Args:
            tax_id: Full EIN (XX-XXXXXXX format)

        Returns:
            Tuple of (encrypted_ein, masked_ein)
        """
        if not tax_id:
            return "", ""

        # Normalize (remove dashes)
        clean_ein = "".join(c for c in tax_id if c.isdigit())

        if len(clean_ein) != 9:
            raise ValueError("EIN must be 9 digits")

        encrypted = self.encrypt(clean_ein)
        # Show last 4 digits only
        masked = f"**-***{clean_ein[-4:]}"

        return encrypted, masked

    def encrypt_routing_number(self, routing: str) -> str:
        """
        Encrypt routing number (stored fully encrypted, no mask needed).

        Args:
            routing: 9-digit ABA routing number

        Returns:
            Encrypted routing number
        """
        if not routing:
            return ""

        clean_routing = "".join(c for c in routing if c.isdigit())

        if len(clean_routing) != 9:
            raise ValueError("Routing number must be 9 digits")

        return self.encrypt(clean_routing)

    @staticmethod
    def mask_ssn(last_4: str) -> str:
        """Format SSN mask for display: ***-**-1234"""
        return f"***-**-{last_4}" if last_4 else ""

    @staticmethod
    def mask_account(last_4: str) -> str:
        """Format account mask for display: ****1234"""
        return f"****{last_4}" if last_4 else ""


@lru_cache()
def get_encryption_service() -> PIIEncryptionService:
    """Get singleton instance of encryption service."""
    return PIIEncryptionService()


# Convenience functions for direct use
def encrypt_pii(plaintext: str) -> str:
    """Encrypt any PII field."""
    return get_encryption_service().encrypt(plaintext)


def decrypt_pii(ciphertext: str) -> str:
    """Decrypt any PII field."""
    return get_encryption_service().decrypt(ciphertext)


def encrypt_ssn(ssn: str) -> tuple[str, str]:
    """Encrypt SSN, return (encrypted, last_4)."""
    return get_encryption_service().encrypt_ssn(ssn)


def encrypt_bank_account(account: str) -> tuple[str, str]:
    """Encrypt bank account, return (encrypted, masked)."""
    return get_encryption_service().encrypt_bank_account(account)


def encrypt_tax_id(ein: str) -> tuple[str, str]:
    """Encrypt EIN, return (encrypted, masked)."""
    return get_encryption_service().encrypt_tax_id(ein)
