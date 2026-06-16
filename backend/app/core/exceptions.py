"""
Custom exception classes and FastAPI exception handlers.
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class IIPException(Exception):
    """Base exception for Investigation Intelligence Platform."""
    def __init__(self, message: str, status_code: int = 500, detail: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(message)


class NotFoundError(IIPException):
    def __init__(self, resource: str, resource_id: str | int):
        super().__init__(
            message=f"{resource} with id '{resource_id}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnauthorizedError(IIPException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(IIPException):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message=message, status_code=status.HTTP_403_FORBIDDEN)


class ConflictError(IIPException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=status.HTTP_409_CONFLICT)


class ValidationError(IIPException):
    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(message=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


class StorageError(IIPException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


class ProcessingError(IIPException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app."""

    @app.exception_handler(IIPException)
    async def iip_exception_handler(request: Request, exc: IIPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "detail": exc.detail,
                "status_code": exc.status_code,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Request validation failed",
                "detail": exc.errors(),
                "status_code": 422,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "detail": {},
                "status_code": 500,
            },
        )
