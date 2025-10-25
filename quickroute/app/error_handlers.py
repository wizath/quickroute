import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from .exceptions import QuickRouteException, DatabaseError, ValidationError

logger = logging.getLogger(__name__)


async def quickroute_exception_handler(request: Request, exc: QuickRouteException):
    """Handler for custom QuickRoute exceptions"""
    logger.error(
        f"QuickRoute Exception: {exc.message} | Status: {exc.status_code} | Path: {request.url.path}",
        extra={"details": exc.details, "path": str(request.url.path)}
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.message,
            "details": exc.details,
            "type": exc.__class__.__name__
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handler for standard HTTP exceptions"""
    logger.warning(
        f"HTTP Exception: {exc.detail} | Status: {exc.status_code} | Path: {request.url.path}",
        extra={"path": str(request.url.path)}
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "type": "HTTPException"
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handler for Pydantic validation errors"""
    logger.warning(
        f"Validation Error: {exc.errors()} | Path: {request.url.path}",
        extra={"errors": exc.errors(), "path": str(request.url.path)}
    )

    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "message": "Validation failed",
            "details": {"validation_errors": exc.errors()},
            "type": "ValidationError"
        }
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handler for SQLAlchemy database errors"""
    logger.error(
        f"Database Error: {str(exc)} | Path: {request.url.path}",
        extra={"error_type": type(exc).__name__, "path": str(request.url.path)}
    )

    if isinstance(exc, IntegrityError):
        return JSONResponse(
            status_code=409,
            content={
                "error": True,
                "message": "Database integrity constraint violated",
                "type": "IntegrityError"
            }
        )

    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal database error",
            "type": "DatabaseError"
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Fallback handler for any unhandled exceptions"""
    logger.error(
        f"Unhandled Exception: {type(exc).__name__}: {str(exc)} | Path: {request.url.path}",
        extra={"exception_type": type(exc).__name__, "path": str(request.url.path)},
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal server error",
            "type": "InternalServerError"
        }
    )