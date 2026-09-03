"""Password hashing with stdlib scrypt (no extra dependency)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_SCHEME = "scrypt"
_N, _R, _P = 2**14, 8, 1
_SALT_BYTES = 16
_KEY_LEN = 32


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_KEY_LEN
    )
    return "$".join(
        (
            _SCHEME,
            f"{_N}:{_R}:{_P}",
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, params, salt_b64, digest_b64 = stored.split("$")
        n, r, p = (int(part) for part in params.split(":"))
        salt = base64.urlsafe_b64decode(salt_b64)
        expected = base64.urlsafe_b64decode(digest_b64)
    except (ValueError, TypeError):
        return False
    if scheme != _SCHEME:
        return False
    actual = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=len(expected)
    )
    return hmac.compare_digest(actual, expected)
