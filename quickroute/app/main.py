from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from .database import engine
from .admin import setup_admin
from .routers import users, auth
from .settings import settings
from .exceptions import QuickRouteException
from .error_handlers import (
    quickroute_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    sqlalchemy_exception_handler,
    general_exception_handler
)
from .logging import logger
from .middleware import load_middleware
from .router import Router
from .routers import auth, users
from .example_jobs import *  # Import all example jobs to register them
from .plugins import initialize_plugins

app = FastAPI(title=settings.QUICKROUTE_TITLE, description=settings.QUICKROUTE_DESCRIPTION, version=settings.QUICKROUTE_VERSION)

plugin_manager = initialize_plugins(settings)
logger.info(f"Initialized {len(plugin_manager.get_enabled_plugins())} plugins")

from .websocket import get_websocket_manager
from .websocket.middleware import initialize_default_websocket_middleware
from .websocket.examples import *  # Import WebSocket examples

websocket_manager = get_websocket_manager()
initialize_default_websocket_middleware()
logger.info("WebSocket system initialized")

load_middleware(app)

app.add_exception_handler(QuickRouteException, quickroute_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

app_router = Router()

# Basic routes
@app_router.get("/")
async def root(request: Request):
    """Health check endpoint with middleware demonstration"""
    return {
        "ok": True,
        "request_id": getattr(request.state, 'request_id', None),
        "authenticated": getattr(request.state, 'authenticated', False),
        "user_id": getattr(request.state.user, 'id', None) if getattr(request.state, 'user', None) else None,
        "session_data": dict(getattr(request.state, 'session', {})),
    }

@app_router.get("/home/")
async def home(request: Request):
    """Home page."""
    return {"message": "Welcome to QuickRoute!", "framework": "QuickRoute"}

@app_router.get("/about/")
async def about(request: Request):
    """About page."""
    return {
        "title": "About QuickRoute",
        "description": "A async web framework built with FastAPI",
        "features": [
            "Model managers",
            "Interactive shell",
            "Settings pattern",
            "Middleware system",
            "Simple routing"
        ]
    }

@app_router.get("/contact/")
async def contact(request: Request):
    """Contact page."""
    return {
        "title": "Contact Us",
        "email": "contact@quickroute.dev",
        "phone": "+1-555-0123",
        "address": "123 API Street, Web Framework City"
    }

@app_router.get("/middleware-info")
async def middleware_info(request: Request):
    """Endpoint to show middleware information"""
    headers = dict(request.headers)

    return {
        "request_info": {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "client_ip": request.client.host if request.client else "unknown",
        },
        "state_info": {
            "request_id": getattr(request.state, 'request_id', None),
            "authenticated": getattr(request.state, 'authenticated', False),
            "user_id": getattr(request.state.user, 'id', None) if getattr(request.state, 'user', None) else None,
            "session_id": getattr(request.state, 'session_id', None),
            "session_keys": list(getattr(request.state, 'session', {}).keys()),
        },
        "security_headers": {
            "csrf_token": headers.get("x-csrftoken"),
            "request_id": headers.get("x-request-id"),
            "processing_time": headers.get("x-processing-time"),
        }
    }

@app_router.post("/session-test")
async def session_test(request: Request):
    """Test session functionality"""
    if not hasattr(request.state, 'session'):
        request.state.session = {}

    # Increment counter in session
    counter = request.state.session.get('counter', 0) + 1
    request.state.session['counter'] = counter
    request.state.session['last_visit'] = str(request.url)
    request.state.session_modified = True

    return {
        "session_counter": counter,
        "session_id": getattr(request.state, 'session_id', None),
        "message": f"This is visit number {counter}"
    }

app_router.register_with_app(app)

try:
    from .admin import ADMIN_AVAILABLE, setup_admin
    if ADMIN_AVAILABLE:
        setup_admin(app, engine, use_jwt_auth=True)
        logger.info("QuickRoute Admin initialized with JWT authentication")
    else:
        logger.info("QuickRoute Admin not available (sqladmin not installed)")
except ImportError as e:
    logger.warning(f"Could not initialize admin: {e}")

@app.get("/")
async def root(request: Request):
    """Health check endpoint with middleware demonstration"""
    return {
        "ok": True,
        "request_id": getattr(request.state, 'request_id', None),
        "authenticated": getattr(request.state, 'authenticated', False),
        "user_id": getattr(request.state.user, 'id', None) if getattr(request.state, 'user', None) else None,
        "session_data": dict(getattr(request.state, 'session', {})),
    }


@app.get("/middleware-info")
async def middleware_info(request: Request):
    """Endpoint to show middleware information"""
    headers = dict(request.headers)

    return {
        "request_info": {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "client_ip": request.client.host if request.client else "unknown",
        },
        "state_info": {
            "request_id": getattr(request.state, 'request_id', None),
            "authenticated": getattr(request.state, 'authenticated', False),
            "user_id": getattr(request.state.user, 'id', None) if getattr(request.state, 'user', None) else None,
            "session_id": getattr(request.state, 'session_id', None),
            "session_keys": list(getattr(request.state, 'session', {}).keys()),
        },
        "security_headers": {
            "csrf_token": headers.get("x-csrftoken"),
            "request_id": headers.get("x-request-id"),
            "processing_time": headers.get("x-processing-time"),
        }
    }


@app.post("/session-test")
async def session_test(request: Request):
    """Test session functionality"""
    if not hasattr(request.state, 'session'):
        request.state.session = {}

    # Increment counter in session
    counter = request.state.session.get('counter', 0) + 1
    request.state.session['counter'] = counter
    request.state.session['last_visit'] = str(request.url)
    request.state.session_modified = True

    return {
        "session_counter": counter,
        "session_id": getattr(request.state, 'session_id', None),
        "message": f"This is visit number {counter}"
    }
