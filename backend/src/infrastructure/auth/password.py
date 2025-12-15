from __future__ import annotations

import hashlib
from typing import Tuple

# NOTE: Keep a hard limit to reduce the risk of DoS via extremely long passwords.
# This is a limit in *bytes* (UTF-8 encoded), not characters.
MAX_PASSWORD_BYTES = 1024

# bcrypt only uses the first 72 bytes of the input. Some backends raise if the input
# is longer to avoid silent truncation.
BCRYPT_MAX_PASSWORD_BYTES = 72

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError

    _argon2_hasher: PasswordHasher | None = PasswordHasher()
except Exception:  # pragma: no cover
    _argon2_hasher = None
    VerifyMismatchError = None  # type: ignore[assignment]

try:
    import bcrypt  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    bcrypt = None


def _to_password_bytes(password: str) -> bytes:
    if not isinstance(password, str):
        raise TypeError("Password must be a string")
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
    return password_bytes


def _bcrypt_input(password_bytes: bytes) -> bytes:
    if len(password_bytes) <= BCRYPT_MAX_PASSWORD_BYTES:
        return password_bytes
    # Pre-hash to avoid bcrypt truncation / length errors while still allowing long passphrases.
    return hashlib.sha256(password_bytes).digest()


def hash_password(password: str) -> str:
    password_bytes = _to_password_bytes(password)

    if _argon2_hasher is not None:
        try:
            return _argon2_hasher.hash(password)
        except Exception as e:
            raise ValueError("Password hashing failed") from e

    if bcrypt is None:  # pragma: no cover
        raise RuntimeError("No password hashing backend available (argon2/bcrypt missing)")

    try:
        bcrypt_input = _bcrypt_input(password_bytes)
        return bcrypt.hashpw(bcrypt_input, bcrypt.gensalt()).decode("utf-8")
    except Exception as e:
        raise ValueError("Password hashing failed") from e


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = _to_password_bytes(plain_password)
    except Exception:
        return False

    # Argon2 hashes are in modular crypt format: "$argon2id$..."
    if isinstance(hashed_password, str) and hashed_password.startswith("$argon2"):
        if _argon2_hasher is None:
            return False
        try:
            return _argon2_hasher.verify(hashed_password, plain_password)
        except VerifyMismatchError:  # type: ignore[misc]
            return False
        except Exception:
            return False

    # bcrypt hashes are in modular crypt format: "$2b$...", "$2a$...", "$2y$..."
    if bcrypt is None:
        return False
    try:
        bcrypt_input = _bcrypt_input(password_bytes)
        return bcrypt.checkpw(bcrypt_input, hashed_password.encode("utf-8"))
    except Exception:
        return False


def validate_password_strength(password: str) -> Tuple[bool, str]:
    try:
        _to_password_bytes(password)
    except Exception as e:
        return False, str(e)

    if len(password) < 6:
        return False, "Password must be at least 6 characters long"

    return True, ""
