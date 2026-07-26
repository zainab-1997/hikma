"""FastAPI application entrypoint and deployment middleware."""

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from api.analytics import router as analytics_router
from api.email import router as email_router
from api.health import router as health_router
from api.orders import router as orders_router
from api.products import router as products_router
from config.logging_config import configure_logging
from config.settings import Settings, get_settings
from database.session import init_db
from services.startup_validation_service import validate_startup

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
logger = logging.getLogger("app.requests")


def _request_id(raw: str | None) -> str:
    return raw if raw and REQUEST_ID_PATTERN.fullmatch(raw) else str(uuid.uuid4())


def create_app(settings_override: Settings | None = None) -> FastAPI:
    settings = settings_override or get_settings()
    configure_logging(settings.app_log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        validate_startup(settings)
        init_db(settings.database_url)
        logger.info("application started", extra={"request_id": "startup"})
        yield

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.app_debug,
        lifespan=lifespan,
    )
    application.state.settings = settings

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = _request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "unhandled request error",
                extra={"request_id": request_id, "method": request.method, "path": request.url.path},
            )
            response = JSONResponse(
                status_code=500,
                content={"detail": "An unexpected server error occurred.", "request_id": request_id},
            )
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    application.include_router(orders_router)
    application.include_router(products_router)
    application.include_router(email_router)
    application.include_router(analytics_router)
    application.include_router(health_router)

    # Backward-compatible lightweight health endpoint used by existing clients.
    @application.get("/health", include_in_schema=False)
    def legacy_health():
        return {"status": "ok"}

    return application


app = create_app()
