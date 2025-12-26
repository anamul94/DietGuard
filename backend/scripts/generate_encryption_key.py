"""
Generate a secure encryption key for HIPAA-compliant data encryption.
Run this script to generate a new ENCRYPTION_KEY for your .env file.
"""
import os
import base64

def generate_encryption_key():
    """Generate a secure 32-byte encryption key for AES-256."""
    key = os.urandom(32)  # 32 bytes = 256 bits for AES-256
    key_b64 = base64.b64encode(key).decode('utf-8')
    
    print("=" * 70)
    print("ENCRYPTION KEY GENERATED")
    print("=" * 70)
    print("\nAdd this to your .env file:")
    print(f"\nENCRYPTION_KEY={key_b64}")
    print("\n" + "=" * 70)
    print("IMPORTANT:")
    print("- Keep this key secret and secure")
    print("- Never commit this key to version control")
    print("- Use different keys for dev/staging/production")
    print("- Store production keys in a secure key management system (AWS KMS, etc.)")
    print("- If you lose this key, encrypted data cannot be recovered")
    print("=" * 70)
    
    return key_b64

if __name__ == "__main__":
    generate_encryption_key()
