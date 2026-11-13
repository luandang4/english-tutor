"""Password hashing (Argon2id) and opaque session tokens."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # argon2-cffi defaults = RFC 9106 low-memory profile (Argon2id)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    """Only the SHA-256 of a session token is stored, so a DB leak doesn't leak live sessions."""
    return hashlib.sha256(token.encode()).hexdigest()


# Verified against a dummy hash when the email doesn't exist, so login timing doesn't reveal accounts.
DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


PASSWORD_RULES = "ít nhất 8 ký tự, gồm cả chữ cái và chữ số"


def password_problem(password: str) -> str | None:
    """Why a new password is too weak, or None. Same rules as the hint shown in the UI."""
    if len(password) < 8:
        return "Mật khẩu cần ít nhất 8 ký tự."
    if not any(c.isalpha() for c in password):
        return "Mật khẩu cần có ít nhất 1 chữ cái."
    if not any(c.isdigit() for c in password):
        return "Mật khẩu cần có ít nhất 1 chữ số."
    return None
