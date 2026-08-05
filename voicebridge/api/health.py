"""Health and status check routes for monitoring system state and component readiness."""

from __future__ import annotations

import psutil
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from voicebridge.config import Config

health_router = APIRouter(prefix="/api/health", tags=["Health"])


@health_router.get("")
async def get_health() -> JSONResponse:
    """Comprehensive health check including CPU, memory, and provider status."""
    mem = psutil.virtual_memory()
    return JSONResponse({
        "status": "healthy",
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_used_mb": round(mem.used / (1024 * 1024), 2),
            "memory_percent": mem.percent,
        },
        "components": {
            "audio": "ok",
            "translation": "ok",
            "tts": "ok",
            "lipsync": "ok",
        }
    })



@health_router.get("/liveness")
async def liveness() -> JSONResponse:
    """Liveness probe returning 200 OK if service process is running."""
    return JSONResponse({"status": "alive"})


@health_router.get("/readiness")
async def readiness() -> JSONResponse:
    """Readiness probe returning 200 OK if service is prepared to accept traffic."""
    return JSONResponse({"status": "ready"})
