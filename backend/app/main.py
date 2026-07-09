from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from uuid import uuid4

from app.core.settings import settings
from app.core.logging import setup_logging
from app.core.context import set_request_id
from app.api.v1.health import router as health_router
from app.api.v1.customers import router as customers_router
from app.api.v1.devices import router as devices_router
from app.api.v1.telemetry import router as telemetry_router
from app.api.v1.users import router as users_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.alerts import router as alerts_router
import structlog

# Initialize logging based on environment
setup_logging(settings.ENVIRONMENT)
logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup", environment=settings.ENVIRONMENT)
    from asyncio import CancelledError, create_task
    from app.workers.offline_watchdog import offline_watchdog_loop
    from app.workers.retention import retention_loop

    background_tasks = [
        create_task(offline_watchdog_loop()),
        create_task(retention_loop()),
    ]
    try:
        yield
    finally:
        for task in background_tasks:
            task.cancel()
        for task in background_tasks:
            try:
                await task
            except CancelledError:
                pass
        logger.info("Application shutdown", environment=settings.ENVIRONMENT)


def create_app() -> FastAPI:
    # Hide interactive API docs in production.
    docs_url = None if settings.is_production else "/api/docs"
    redoc_url = None if settings.is_production else "/api/redoc"

    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="""
**IoT Device Management Server API**

This API allows administrators to provision, configure, and monitor Solar Street Light RMS controllers.
It acts as the primary interface for both the frontend administration dashboard and future external integrations.
        """,
        version="0.1.0",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=docs_url,
        redoc_url=redoc_url,
        lifespan=lifespan,
    )

    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Let the dashboard read rate-limit and request-id headers on 429/5xx.
        expose_headers=["Retry-After", "X-Request-ID"],
    )

    # API Routers
    app.include_router(health_router, prefix=settings.API_V1_STR)
    app.include_router(customers_router, prefix=settings.API_V1_STR)
    app.include_router(devices_router, prefix=settings.API_V1_STR)
    app.include_router(telemetry_router, prefix=settings.API_V1_STR)
    app.include_router(users_router, prefix=f"{settings.API_V1_STR}/users")
    app.include_router(dashboard_router, prefix=f"{settings.API_V1_STR}/dashboard")
    # alerts_router already declares prefix="/alerts", so mount it under the API
    # base only — matching devices/customers/telemetry. Mounting under
    # "/api/v1/alerts" here would double the segment (/api/v1/alerts/alerts).
    app.include_router(alerts_router, prefix=settings.API_V1_STR)

    @app.get("/")
    async def root():
        return {"status": "ok", "message": "PCB Server API is running! 🚀", "version": "0.1.0"}

    @app.middleware("http")
    async def add_request_id_middleware(request: Request, call_next):
        req_id = str(uuid4())
        set_request_id(req_id)
        
        with structlog.contextvars.bound_contextvars(request_id=req_id):
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response

    return app

app = create_app()
