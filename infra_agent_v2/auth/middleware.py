"""Authentication middleware for Infra Agent v2 dashboard.

Supports Basic Auth and Bearer token authentication.
"""

from __future__ import annotations

import hashlib
import os
import base64
from typing import Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.auth")

# ---------------------------------------------------------------------------
# Auth settings
# ---------------------------------------------------------------------------

# Environment variables for credentials (fallback)
DEFAULT_USERNAME = os.environ.get("INFRA_DASHBOARD_USERNAME", "admin")
DEFAULT_PASSWORD = os.environ.get("INFRA_DASHBOARD_PASSWORD", "admin")
DEFAULT_TOKEN = os.environ.get("INFRA_DASHBOARD_TOKEN", "")

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class AuthMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that enforces authentication.

    Supports two modes:
      - ``basic``: HTTP Basic authentication (username/password)
      - ``bearer``: Bearer token authentication

    Public endpoints (``/api/health``, ``/metrics``) are always accessible.
    """

    def __init__(
        self,
        app,
        mode: str = "basic",
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
        token: str = DEFAULT_TOKEN,
    ):
        super().__init__(app)
        self.mode = mode.lower()
        self.username = username
        self.password = password
        self.token = token

        # Hash the password for storage
        self._password_hash = hashlib.sha256(password.encode()).hexdigest()

        # Public endpoints that do not require authentication
        self.public_paths = ["/api/health", "/metrics"]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow public endpoints
        if path in self.public_paths:
            return await call_next(request)

        # Auth disabled
        if self.mode == "none":
            return await call_next(request)

        # Authenticate
        authenticated = False
        if self.mode == "bearer" and self.token:
            authenticated = self._check_bearer(request)
        elif self.mode == "basic":
            authenticated = self._check_basic(request)

        if not authenticated:
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers={"WWW-Authenticate": self._auth_scheme},
            )

        return await call_next(request)

    @property
    def _auth_scheme(self) -> str:
        if self.mode == "bearer":
            return "Bearer"
        return "Basic"

    # -- Bearer token --

    def _check_bearer(self, request: Request) -> bool:
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return False

        token = auth_header[len("Bearer "):].strip()
        # Constant-time comparison
        return hashlib.sha256(token.encode()).hexdigest() == hashlib.sha256(self.token.encode()).hexdigest()

    # -- Basic auth --

    def _check_basic(self, request: Request) -> bool:
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Basic "):
            return False

        try:
            creds = base64.b64decode(auth_header[len("Basic "):]).decode()
        except Exception:
            return False

        username, _, password = creds.partition(":")
        return (
            username == self.username
            and hashlib.sha256(password.encode()).hexdigest() == self._password_hash
        )
