"""
Authentication service — register, login, token refresh.
"""
import uuid
from datetime import datetime, timezone
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserRole
from app.repositories.user_repo import UserRepository
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.exceptions import ConflictError, UnauthorizedError
from app.schemas import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.config import settings


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def register(self, request: RegisterRequest) -> UserResponse:
        if await self.user_repo.email_exists(request.email):
            raise ConflictError(f"User with email '{request.email}' already exists")

        user = User(
            email=request.email.lower(),
            hashed_password=hash_password(request.password),
            full_name=request.full_name,
            role=request.role,
        )
        user = await self.user_repo.create(user)
        return UserResponse.model_validate(user)

    async def login(self, request: LoginRequest) -> TokenResponse:
        user = await self.user_repo.get_by_email(request.email)
        if not user or not verify_password(request.password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedError("Account is deactivated")

        access_token = create_access_token(
            subject=str(user.id),
            extra={"email": user.email, "role": user.role.value},
        )
        refresh_token = create_refresh_token(subject=str(user.id))
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise UnauthorizedError("Invalid refresh token")
            user_id = payload.get("sub")
            user = await self.user_repo.get_by_id(uuid.UUID(user_id))
            if not user or not user.is_active:
                raise UnauthorizedError("User not found or inactive")
        except (JWTError, ValueError):
            raise UnauthorizedError("Invalid or expired refresh token")

        access_token = create_access_token(
            subject=str(user.id),
            extra={"email": user.email, "role": user.role.value},
        )
        new_refresh = create_refresh_token(subject=str(user.id))
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def get_current_user(self, user_id: str) -> User:
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user or not user.is_active:
            raise UnauthorizedError("User not found or inactive")
        return user
