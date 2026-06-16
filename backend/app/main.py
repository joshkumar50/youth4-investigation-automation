"""
FastAPI application — main entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import settings
from app.core.logging import configure_logging
from app.core.exceptions import register_exception_handlers
from app.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    configure_logging()

    # Create all tables (handled by Alembic in production, fallback for dev)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Cleanup
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI-powered digital evidence investigation platform that transforms "
        "raw evidence into structured investigation intelligence."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Exception Handlers ──
register_exception_handlers(app)

# ── Routers ──
from app.routers import auth, cases, evidence

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(evidence.router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for load balancers and Docker healthcheck."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Investigation Intelligence Platform API",
        "docs": "/docs",
        "version": settings.app_version,
    }
