"""
Smart Property AI
Main FastAPI application.

Run locally with:

    uvicorn app:app --reload
"""

import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from routes.main_routes import router as main_router

from database.database import create_database_tables
# ==========================================================================
# 1. Environment configuration
# ==========================================================================

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR / "uploads"
LOGS_DIR = BASE_DIR / "logs"

ENVIRONMENT = os.getenv(
    "ENVIRONMENT",
    "development",
).strip().lower()

DEBUG = os.getenv(
    "DEBUG",
    "true",
).strip().lower() in {
    "true",
    "1",
    "yes",
    "on",
}

APP_NAME = os.getenv(
    "APP_NAME",
    "Smart Property AI",
)

APP_VERSION = os.getenv(
    "APP_VERSION",
    "1.0.0",
)

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "",
)

SESSION_COOKIE_NAME = os.getenv(
    "SESSION_COOKIE_NAME",
    "smart_property_session",
)

SESSION_MAX_AGE = int(
    os.getenv(
        "SESSION_MAX_AGE",
        str(60 * 60 * 24 * 7),
    )
)

IS_PRODUCTION = ENVIRONMENT == "production"


# Generate a development key when SECRET_KEY is missing.
# Production must always use a permanent secure environment value.
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY is missing. Add a secure SECRET_KEY "
            "to the production environment."
        )

    SECRET_KEY = secrets.token_hex(32)


# ==========================================================================
# 2. Required directories
# ==========================================================================

STATIC_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

TEMPLATES_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

UPLOADS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LOGS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ==========================================================================
# 3. Logging
# ==========================================================================

LOG_LEVEL = (
    logging.DEBUG
    if DEBUG
    else logging.INFO
)

logging.basicConfig(
    level=LOG_LEVEL,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            LOGS_DIR / "application.log",
            encoding="utf-8",
        ),
    ],
)

logger = logging.getLogger(
    "smart_property_ai"
)


# ==========================================================================
# 4. Jinja templates
# ==========================================================================

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)


# ==========================================================================
# 5. Application lifecycle
# ==========================================================================

@asynccontextmanager
async def lifespan(
    application: FastAPI,
) -> AsyncIterator[None]:
    """
    Run startup and shutdown tasks.

    Database setup, model loading and automation startup can
    be added here later.
    """

    logger.info(
        "Starting %s version %s in %s mode.",
        APP_NAME,
        APP_VERSION,
        ENVIRONMENT,
    )

    # Future database startup:
    #
    # from database.database import engine, Base
    # from database import models
    #
    # Base.metadata.create_all(bind=engine)

    # Future scheduler startup:
    #
    # from automation.scheduler import scheduler
    # scheduler.start()

    # Future AI model loading:
    #
    # application.state.ai_model = load_ai_model()

    create_database_tables()

    logger.info(
        "Database tables are ready."
    )

    yield

    # Future scheduler shutdown:
    #
    # if scheduler.running:
    #     scheduler.shutdown(wait=False)

    logger.info(
        "Shutting down %s.",
        APP_NAME,
    )


# ==========================================================================
# 6. Create FastAPI application
# ==========================================================================

app = FastAPI(
    title=APP_NAME,
    description=(
        "A multilingual, accessible property-management "
        "and apartment-search platform powered by a "
        "custom Smart Property AI system."
    ),
    version=APP_VERSION,
    debug=DEBUG,
    lifespan=lifespan,
    docs_url="/docs" if not IS_PRODUCTION else None,
    redoc_url="/redoc" if not IS_PRODUCTION else None,
)


# ==========================================================================
# 7. Session middleware
# ==========================================================================

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie=SESSION_COOKIE_NAME,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=IS_PRODUCTION,
)


# ==========================================================================
# 8. Security and request middleware
# ==========================================================================

class SecurityHeadersMiddleware(
    BaseHTTPMiddleware
):
    """
    Add basic browser security headers to every response.
    """

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        response = await call_next(request)

        response.headers[
            "X-Content-Type-Options"
        ] = "nosniff"

        response.headers[
            "X-Frame-Options"
        ] = "SAMEORIGIN"

        response.headers[
            "Referrer-Policy"
        ] = "strict-origin-when-cross-origin"

        response.headers[
            "Permissions-Policy"
        ] = (
            "camera=(self), "
            "microphone=(self), "
            "geolocation=(self)"
        )

        response.headers[
            "Cross-Origin-Opener-Policy"
        ] = "same-origin"

        if IS_PRODUCTION:
            response.headers[
                "Strict-Transport-Security"
            ] = (
                "max-age=31536000; "
                "includeSubDomains"
            )

        return response


class RequestLoggingMiddleware(
    BaseHTTPMiddleware
):
    """
    Log request method, path, response status and duration.

    Sensitive form data, message content, passwords and
    authentication tokens are never logged here.
    """

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        started_at = time.perf_counter()

        response = await call_next(request)

        duration_ms = (
            time.perf_counter() - started_at
        ) * 1000

        logger.info(
            "%s %s -> %s %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response


app.add_middleware(
    SecurityHeadersMiddleware
)

app.add_middleware(
    RequestLoggingMiddleware
)


# ==========================================================================
# 9. Static files
# ==========================================================================

app.mount(
    "/static",
    StaticFiles(
        directory=str(STATIC_DIR)
    ),
    name="static",
)


# Do not mount /uploads publicly.
# Private documents and tenant files must be returned through
# protected routes after checking authorization.


# ==========================================================================
# 10. Register main routes
# ==========================================================================

app.include_router(
    main_router
)


# ==========================================================================
# 11. Temporary routes required by base.html and index.html
# ==========================================================================

def temporary_page(
    title: str,
    message: str,
) -> HTMLResponse:
    """
    Generate a temporary HTML page.

    Replace these temporary endpoints with their respective
    route modules as development continues.
    """

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">

            <meta
                name="viewport"
                content="width=device-width, initial-scale=1.0"
            >

            <title>{title} | Smart Property AI</title>

            <link
                rel="stylesheet"
                href="/static/css/style.css"
            >
        </head>

        <body>
            <main
                id="main-content"
                class="auth-page"
            >
                <section class="auth-container">
                    <div class="auth-card">
                        <p class="section-label">
                            Smart Property AI
                        </p>

                        <h1>{title}</h1>

                        <p>{message}</p>

                        <a
                            href="/"
                            class="button button--primary"
                        >
                            Return to homepage
                        </a>
                    </div>
                </section>
            </main>
        </body>
        </html>
        """,
        status_code=status.HTTP_200_OK,
    )


# --------------------------------------------------------------------------
# Temporary authentication routes
# --------------------------------------------------------------------------

@app.get(
    "/login",
    name="login",
)
async def temporary_login_page():
    return temporary_page(
        title="Login",
        message=(
            "The secure login page will be connected through "
            "routes/auth_routes.py."
        ),
    )


@app.get(
    "/register",
    name="register",
)
async def temporary_register_page():
    return temporary_page(
        title="Create an account",
        message=(
            "Account registration will be connected through "
            "routes/auth_routes.py."
        ),
    )


@app.post(
    "/logout",
    name="logout",
)
async def temporary_logout(
    request: Request,
):
    """
    Clear the complete session and return to the homepage.

    This endpoint can be removed after the permanent logout
    route is created in auth_routes.py.
    """

    request.session.clear()

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --------------------------------------------------------------------------
# Temporary listing routes
# --------------------------------------------------------------------------

@app.get(
    "/listings",
    name="listings_page",
)
async def temporary_listings_page():
    return temporary_page(
        title="Property listings",
        message=(
            "Public property listings will be connected through "
            "routes/listing_routes.py."
        ),
    )


@app.get(
    "/listings/search",
    name="search_listings",
)
async def temporary_search_listings():
    return temporary_page(
        title="Property search results",
        message=(
            "Property search results will appear here after "
            "the listing service and database are connected."
        ),
    )


@app.get(
    "/listings/guided-search",
    name="guided_search_page",
)
async def temporary_guided_search_page():
    return temporary_page(
        title="Guided apartment search",
        message=(
            "The multilingual voice-guided search will be "
            "connected through routes/listing_routes.py."
        ),
    )


# --------------------------------------------------------------------------
# Temporary AI assistant route
# --------------------------------------------------------------------------

@app.get(
    "/ai/assistant",
    name="ai_assistant_page",
)
async def temporary_ai_assistant_page():
    return temporary_page(
        title="Smart Property AI Assistant",
        message=(
            "The multilingual conversational assistant will "
            "be connected through routes/ai_routes.py."
        ),
    )


# --------------------------------------------------------------------------
# Temporary dashboard routes
# --------------------------------------------------------------------------

@app.get(
    "/landlord/dashboard",
    name="landlord_dashboard",
)
async def temporary_landlord_dashboard(
    request: Request,
):
    if not request.session.get("username"):
        return RedirectResponse(
            url="/login?next=/landlord/dashboard",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return temporary_page(
        title="Landlord dashboard",
        message=(
            "The property-management dashboard will be "
            "connected through routes/landlord_routes.py."
        ),
    )


@app.get(
    "/tenant/dashboard",
    name="tenant_dashboard",
)
async def temporary_tenant_dashboard(
    request: Request,
):
    if not request.session.get("username"):
        return RedirectResponse(
            url="/login?next=/tenant/dashboard",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return temporary_page(
        title="Tenant dashboard",
        message=(
            "The tenant portal will be connected through "
            "routes/tenant_routes.py."
        ),
    )


@app.get(
    "/admin/dashboard",
    name="admin_dashboard",
)
async def temporary_admin_dashboard(
    request: Request,
):
    if not request.session.get("username"):
        return RedirectResponse(
            url="/login?next=/admin/dashboard",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if request.session.get("role") != "administrator":
        return temporary_page(
            title="Access denied",
            message=(
                "You do not have permission to access the "
                "administrator dashboard."
            ),
        )

    return temporary_page(
        title="Administrator dashboard",
        message=(
            "The administrator dashboard will be connected "
            "through routes/admin_routes.py."
        ),
    )


# ==========================================================================
# 12. Favicon shortcut
# ==========================================================================

@app.get(
    "/favicon.ico",
    include_in_schema=False,
)
async def favicon():
    """
    Redirect conventional favicon requests to the static file.
    """

    return RedirectResponse(
        url="/static/images/favicon.ico",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


# ==========================================================================
# 13. Error handlers
# ==========================================================================

@app.exception_handler(
    StarletteHTTPException
)
async def http_exception_handler(
    request: Request,
    exception: StarletteHTTPException,
):
    """
    Render HTML error pages for browser requests and JSON
    responses for API requests.
    """

    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=exception.status_code,
            content={
                "success": False,
                "error": str(exception.detail),
                "status_code": exception.status_code,
            },
        )

    error_templates = {
        400: "errors/400.html",
        401: "errors/401.html",
        403: "errors/403.html",
        404: "errors/404.html",
        429: "errors/429.html",
        500: "errors/500.html",
    }

    template_name = error_templates.get(
        exception.status_code
    )

    if template_name:
        template_path = (
            TEMPLATES_DIR / template_name
        )

        if template_path.exists():
            return templates.TemplateResponse(
                request=request,
                name=template_name,
                context={
                    "request": request,
                    "current_year": datetime.now(
                        timezone.utc
                    ).year,
                    "current_language": (
                        request.session.get(
                            "language",
                            "en",
                        )
                    ),
                    "status_code": exception.status_code,
                    "error": str(exception.detail),
                },
                status_code=exception.status_code,
            )

    return temporary_error_response(
        status_code=exception.status_code,
        title="Request error",
        message=str(exception.detail),
    )


@app.exception_handler(
    RequestValidationError
)
async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
):
    """
    Return validation errors without exposing sensitive data.
    """

    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": "The submitted information is invalid.",
                "details": exception.errors(),
            },
        )

    return temporary_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Invalid information",
        message=(
            "Some submitted information is missing or invalid. "
            "Please review the form and try again."
        ),
    )


@app.exception_handler(
    Exception
)
async def unexpected_exception_handler(
    request: Request,
    exception: Exception,
):
    """
    Handle unexpected errors without exposing internal
    application details to the user.
    """

    logger.exception(
        "Unhandled error while processing %s %s",
        request.method,
        request.url.path,
    )

    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": (
                    "An unexpected server error occurred."
                ),
            },
        )

    error_template = (
        TEMPLATES_DIR / "errors" / "500.html"
    )

    if error_template.exists():
        return templates.TemplateResponse(
            request=request,
            name="errors/500.html",
            context={
                "request": request,
                "current_year": datetime.now(
                    timezone.utc
                ).year,
                "current_language": (
                    request.session.get(
                        "language",
                        "en",
                    )
                ),
                "status_code": 500,
                "error": (
                    "An unexpected server error occurred."
                ),
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return temporary_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Server error",
        message=(
            "An unexpected problem occurred. "
            "Please try again later."
        ),
    )


def temporary_error_response(
    status_code: int,
    title: str,
    message: str,
) -> HTMLResponse:
    """
    Return a fallback error page when a dedicated template
    has not been created.
    """

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">

            <meta
                name="viewport"
                content="width=device-width, initial-scale=1.0"
            >

            <title>{status_code} | Smart Property AI</title>

            <link
                rel="stylesheet"
                href="/static/css/style.css"
            >
        </head>

        <body>
            <main class="auth-page">
                <section class="auth-container">
                    <div class="auth-card">
                        <p class="section-label">
                            Error {status_code}
                        </p>

                        <h1>{title}</h1>

                        <p>{message}</p>

                        <a
                            href="/"
                            class="button button--primary"
                        >
                            Return to homepage
                        </a>
                    </div>
                </section>
            </main>
        </body>
        </html>
        """,
        status_code=status_code,
    )


# ==========================================================================
# 14. Direct execution
# ==========================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=int(
            os.getenv(
                "PORT",
                "8000",
            )
        ),
        reload=DEBUG and not IS_PRODUCTION,
        log_level="debug" if DEBUG else "info",
    )