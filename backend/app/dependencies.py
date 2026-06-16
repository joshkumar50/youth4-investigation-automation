"""
FastAPI dependency injection: DB session, current user, storage.
"""
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.security import verify_access_token
from app.core.exceptions import UnauthorizedError
from app.models import User
from app.services.storage_service import StorageService

security = HTTPBearer()

_storage_instance: StorageService | None = None


def get_storage() -> StorageService:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageService()
    return _storage_instance


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        user_id = verify_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    from app.services.auth_service import AuthService
    auth_svc = AuthService(db)
    try:
        return await auth_svc.get_current_user(user_id)
    except UnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.message)


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")
    return current_user
