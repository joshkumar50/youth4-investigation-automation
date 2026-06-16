"""
Auth router — register, login, refresh, me.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models import User
from app.services.auth_service import AuthService
from app.schemas import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new investigator account."""
    svc = AuthService(db)
    return await svc.register(request)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and receive JWT tokens."""
    svc = AuthService(db)
    return await svc.login(request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh access token using refresh token."""
    svc = AuthService(db)
    return await svc.refresh(request.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_active_user)):
    """Get current authenticated user profile."""
    return UserResponse.model_validate(current_user)
