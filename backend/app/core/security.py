"""
JWT security utilities: token creation, verification, password hashing.
"""
from datetime import datetime, timedelta, timezone
from typing import Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str | Any, extra: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(subject), "exp": expire, "type": "access"}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str | Any) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {"sub": str(subject), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


def verify_access_token(token: str) -> str:
    """Verify access token and return subject (user_id)."""
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise JWTError("Invalid token type")
        sub = payload.get("sub")
        if not sub:
            raise JWTError("Missing subject")
        return sub
    except JWTError:
        raise
