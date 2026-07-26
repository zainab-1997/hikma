"""Safe liveness and readiness endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.startup_validation_service import readiness_status

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/live")
def liveness():
    return {"status": "ok"}


@router.get("")
def health(request: Request):
    settings = request.app.state.settings
    components = readiness_status(settings)
    body = {
        "status": "ok" if components.ready else "unavailable",
        "environment": settings.app_env,
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": components.database,
        "template": components.template,
        "generated_orders": components.generated_orders,
    }
    return JSONResponse(body, status_code=200 if components.ready else 503)


@router.get("/ready")
def readiness(request: Request):
    settings = request.app.state.settings
    components = readiness_status(settings)
    body = {
        "status": "ready" if components.ready else "not_ready",
        "database": components.database,
        "template": components.template,
        "generated_orders": components.generated_orders,
    }
    return JSONResponse(body, status_code=200 if components.ready else 503)
