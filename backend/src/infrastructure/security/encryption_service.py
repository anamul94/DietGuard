"""
HIPAA-compliant encryption service for sensitive patient data.
Uses AES-256-GCM for field-level encryption.
"""
import os
import base64
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ...infrastructure.utils.logger import logger


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive patient data.
    Follows HIPAA requirements for data protection.
    """
    
    def __init__(self):
        """Initialize encryption service with key from environment."""
        self._encryption_key = self._get_or_create_key()
        self._aesgcm = AESGCM(self._encryption_key)
    
    @staticmethod
    def _get_or_create_key() -> bytes:
        """
        Get encryption key from environment or generate one.
        
        Returns:
            32-byte encryption key for AES-256
            
        Raises:
            ValueError: If key is not properly configured
        """
        # Get key from environment
        key_string = os.getenv('ENCRYPTION_KEY')
        
        if not key_string:
            raise ValueError(
                "ENCRYPTION_KEY not found in environment. "
                "Please set a secure 32-byte base64-encoded key."
            )
        
        try:
            # Decode base64 key
            key = base64.b64decode(key_string)
            
            if len(key) != 32:
                raise ValueError("Encryption key must be 32 bytes for AES-256")
            
            return key
            
        except Exception as e:
            raise ValueError(f"Invalid encryption key format: {str(e)}")
    
    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        """
        Encrypt a string value.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64-encoded encrypted string, or None if input is None
            
        Raises:
            ValueError: If encryption fails
        """
        if plaintext is None or plaintext == "":
            return None
        
        try:
            # Generate random nonce (12 bytes for GCM)
            nonce = os.urandom(12)
            
            # Encrypt the data
            ciphertext = self._aesgcm.encrypt(
                nonce,
                plaintext.encode('utf-8'),
                None  # No associated data
            )
            
            # Combine nonce + ciphertext and encode as base64
            encrypted_data = nonce + ciphertext
            return base64.b64encode(encrypted_data).decode('utf-8')
            
        except Exception as e:
            logger.error("Encryption failed", error=str(e))
            raise ValueError("Failed to encrypt data")
    
    def decrypt(self, encrypted_data: Optional[str]) -> Optional[str]:
        """
        Decrypt an encrypted string value.
        
        Args:
            encrypted_data: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string, or None if input is None
            
        Raises:
            ValueError: If decryption fails
        """
        if encrypted_data is None or encrypted_data == "":
            return None
        
        try:
            # Decode base64
            encrypted_bytes = base64.b64decode(encrypted_data)
            
            # Extract nonce (first 12 bytes) and ciphertext
            nonce = encrypted_bytes[:12]
            ciphertext = encrypted_bytes[12:]
            
            # Decrypt the data
            plaintext_bytes = self._aesgcm.decrypt(
                nonce,
                ciphertext,
                None  # No associated data
            )
            
            return plaintext_bytes.decode('utf-8')
            
        except Exception as e:
            logger.error("Decryption failed", error=str(e))
            raise ValueError("Failed to decrypt data")
    
    def encrypt_dict(self, data: Optional[dict]) -> Optional[str]:
        """
        Encrypt a dictionary as JSON string.
        
        Args:
            data: Dictionary to encrypt
            
        Returns:
            Base64-encoded encrypted JSON string, or None if input is None
        """
        if data is None:
            return None
        
        import json
        json_string = json.dumps(data)
        return self.encrypt(json_string)
    
    def decrypt_dict(self, encrypted_data: Optional[str]) -> Optional[dict]:
        """
        Decrypt an encrypted JSON string to dictionary.
        
        Args:
            encrypted_data: Base64-encoded encrypted JSON string
            
        Returns:
            Decrypted dictionary, or None if input is None
        """
        if encrypted_data is None:
            return None
        
        import json
        json_string = self.decrypt(encrypted_data)
        return json.loads(json_string) if json_string else None


# Singleton instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Get singleton encryption service instance.
    
    Returns:
        EncryptionService instance
    """
    global _encryption_service
    
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    
    return _encryption_service
