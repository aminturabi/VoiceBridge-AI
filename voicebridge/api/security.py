"""Security & boundary validation module for VoiceBridge AI API."""

from __future__ import annotations

import os
import time
from typing import Dict, List
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class StartCallSchema(BaseModel):
    """Input boundary validation schema for starting a call."""
    my_language: str = Field(default="en", max_length=10, pattern=r"^[a-zA-Z\-]{2,10}$")
    other_language: str = Field(default="ar", max_length=10, pattern=r"^[a-zA-Z\-]{2,10}$")
    source_kind: str = Field(default="microphone", pattern=r"^(microphone|wav)$")
    wav_path: str | None = Field(default=None, max_length=500)
    two_way: bool = Field(default=True)


class SimpleRateLimiter:
    """In-memory fixed window rate limiter."""

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self._window: Dict[str, List[float]] = {}

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        cutoff = now - 60.0
        timestamps = [t for t in self._window.get(client_id, []) if t > cutoff]
        if len(timestamps) >= self.rpm:
            return False
        timestamps.append(now)
        self._window[client_id] = timestamps
        return True


rate_limiter = SimpleRateLimiter(
    requests_per_minute=int(os.environ.get("VOICEBRIDGE_RATE_LIMIT_PER_MINUTE", "60"))
)


async def verify_api_key(api_key: str | None = Security(API_KEY_HEADER)) -> str | None:
    """Verify optional API Key header if VOICEBRIDGE_ENABLE_AUTH is set to true."""
    auth_enabled = os.environ.get("VOICEBRIDGE_ENABLE_AUTH", "false").lower() in ("true", "1", "yes")
    if not auth_enabled:
        return api_key

    expected_key = os.environ.get("VOICEBRIDGE_API_KEY")
    if not expected_key:
        # If auth enabled but no key configured, reject
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is enabled but VOICEBRIDGE_API_KEY is not configured.",
        )

    if api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
    return api_key
