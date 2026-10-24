"""Local scrypt password hashes. No default account or remotely verified identity."""

import base64
import hashlib
import hmac
import secrets

from factoryflow.kernel.contracts import BusinessError


def derive(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=32768, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=64
    )


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise BusinessError("PASSWORD_LENGTH", field="password")
    salt = secrets.token_bytes(16)
    digest = derive(password, salt)
    return "scrypt-v1$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, encoded: str | None) -> bool:
    if not isinstance(password, str) or len(password) > 128:
        return False
    if encoded is None:
        derive(password, b"\0" * 16)
        return False
    try:
        version, salt, expected = encoded.split("$")
        if version != "scrypt-v1":
            return False
        return hmac.compare_digest(
            derive(password, base64.b64decode(salt)), base64.b64decode(expected)
        )
    except ValueError, TypeError:
        return False
