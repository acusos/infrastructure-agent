"""Tests for auth/middleware.py."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient

from infra_agent_v2.auth.middleware import AuthMiddleware

@pytest.fixture
def basic_middleware():
    """AuthMiddleware with basic auth."""
    from fastapi import FastAPI
    app = FastAPI()
    app.add_middleware(AuthMiddleware, mode="basic", username="admin", password="secret")
    return app

@pytest.fixture
def bearer_middleware():
    """AuthMiddleware with bearer token auth."""
    from fastapi import FastAPI
    app = FastAPI()
    app.add_middleware(AuthMiddleware, mode="bearer", token="supersecret")
    return app

@pytest.fixture
def app():
    """Create a test FastAPI app with auth middleware."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware, mode="basic", username="admin", password="secret")

    @app.get("/api/status")
    def status():
        return {"status": "ok"}

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics():
        return "metrics"

    return app

class TestAuthMiddleware:
    """AuthMiddleware behavior."""

    def test_public_health_no_auth(self, app):
        """Health endpoint is public."""
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_public_metrics_no_auth(self, app):
        """Metrics endpoint is public."""
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_protected_endpoint_requires_auth(self, app):
        """Protected endpoint requires authentication."""
        client = TestClient(app)
        response = client.get("/api/status")
        assert response.status_code == 401

    def test_basic_auth_success(self, app):
        """Valid basic auth credentials succeed."""
        import base64
        client = TestClient(app)
        credentials = base64.b64encode(b"admin:secret").decode()
        response = client.get("/api/status", headers={"Authorization": f"Basic {credentials}"})
        assert response.status_code == 200

    def test_basic_auth_wrong_password(self, app):
        """Wrong password fails."""
        import base64
        client = TestClient(app)
        credentials = base64.b64encode(b"admin:wrong").decode()
        response = client.get("/api/status", headers={"Authorization": f"Basic {credentials}"})
        assert response.status_code == 401

    def test_basic_auth_wrong_username(self, app):
        """Wrong username fails."""
        import base64
        client = TestClient(app)
        credentials = base64.b64encode(b"wrong:secret").decode()
        response = client.get("/api/status", headers={"Authorization": f"Basic {credentials}"})
        assert response.status_code == 401

    def test_no_auth_header_fails(self, app):
        """No auth header fails."""
        client = TestClient(app)
        response = client.get("/api/status")
        assert response.status_code == 401

    def test_bearer_auth_success(self):
        """Valid bearer token succeeds."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        bearer_app = FastAPI()
        bearer_app.add_middleware(AuthMiddleware, mode="bearer", token="supersecret")

        @bearer_app.get("/api/status")
        def status():
            return {"status": "ok"}

        client = TestClient(bearer_app)
        response = client.get("/api/status", headers={"Authorization": "Bearer supersecret"})
        assert response.status_code == 200

    def test_bearer_auth_wrong_token(self):
        """Wrong bearer token fails."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        bearer_app = FastAPI()
        bearer_app.add_middleware(AuthMiddleware, mode="bearer", token="supersecret")

        @bearer_app.get("/api/status")
        def status():
            return {"status": "ok"}

        client = TestClient(bearer_app)
        response = client.get("/api/status", headers={"Authorization": "Bearer wrong"})
        assert response.status_code == 401

    def test_bearer_auth_no_token(self):
        """No bearer token fails."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        bearer_app = FastAPI()
        bearer_app.add_middleware(AuthMiddleware, mode="bearer", token="supersecret")

        @bearer_app.get("/api/status")
        def status():
            return {"status": "ok"}

        client = TestClient(bearer_app)
        response = client.get("/api/status")
        assert response.status_code == 401

    def test_auth_disabled(self):
        """Mode 'none' disables authentication."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        no_auth_app = FastAPI()
        no_auth_app.add_middleware(AuthMiddleware, mode="none")

        @no_auth_app.get("/api/status")
        def status():
            return {"status": "ok"}

        client = TestClient(no_auth_app)
        response = client.get("/api/status")
        assert response.status_code == 200
