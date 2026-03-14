import time

import socketio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ...infrastructure.database.database import AsyncSessionLocal
from ...infrastructure.utils.logger import logger
from .admin_routes import router as admin_router
from .ai_agent_routes import router as ai_agent_router
from .auth_routes import router as auth_router
from .health_routes import router as health_router
from .package_routes import router as package_router
from .payment_routes import router as payment_router
from .user_routes import router as user_router


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
            )
            return response
        except Exception as exc:
            duration = time.time() - start_time
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=str(exc),
                exception_type=type(exc).__name__,
                duration_ms=round(duration * 1000, 2),
            )
            raise


app = FastAPI(
    title="DietGuard AI API",
    description="""AI-powered nutrition and health backend with structured meal, vitals, and report timelines.""",
    version="2.0.0",
    openapi_tags=[
        {"name": "Authentication", "description": "User authentication and authorization endpoints."},
        {"name": "AI Agents", "description": "AI-powered food, report, and nutrition analysis endpoints."},
        {"name": "Users", "description": "User profile management and settings."},
        {"name": "Packages", "description": "Subscription package management."},
        {"name": "Payments", "description": "Payment processing and subscription upgrades."},
        {"name": "Admin", "description": "Administrative operations."},
        {"name": "Health Timeline", "description": "Structured medical profile, meals, vitals, and insights."},
    ],
    contact={"name": "DietGuard Support", "email": "support@dietguard.ai"},
    license_info={"name": "MIT"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(ai_agent_router, prefix="/api/v1/ai")
app.include_router(health_router, prefix="/api/v1/health")
app.include_router(user_router, prefix="/api/v1/users")
app.include_router(payment_router, prefix="/api/v1/payment")
app.include_router(package_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1/admin")


@app.get("/")
async def read_root():
    return {"message": "DietGuard backend is running"}


@app.get("/health")
async def health_check():
    health_status = {
        "status": "healthy",
        "service": "dietguard-backend",
        "version": "2.0.0",
        "checks": {"database": "unknown"},
    }

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        health_status["checks"]["database"] = "healthy"
        return health_status
    except Exception as exc:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = "unhealthy"
        logger.error("Database health check failed", error=str(exc), exception_type=type(exc).__name__)
        raise HTTPException(status_code=500, detail=health_status) from exc


sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode="asgi")
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
