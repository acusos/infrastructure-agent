"""Tests for dashboard/server.py."""

from unittest.mock import MagicMock

import pytest

from infra_agent_v2.config import Config
from infra_agent_v2.dashboard.server import DashboardServer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_agent(config):
    """Return a mock InfraAgent with all subsystems stubbed."""
    agent = MagicMock()
    agent.config = config
    agent.state = MagicMock()
    agent.state.running = True
    agent.state.monitor_events = 5
    agent.state.health_events = 2
    agent.state.recovery_attempts = 3
    agent.state.reports_generated = 1
    agent.state.correlation_groups = 2
    agent.state.last_report_time = "2026-01-01T00:00:00+00:00"
    agent.memory = MagicMock()
    agent.docker = MagicMock()
    agent.recovery = MagicMock()
    agent.analyzer = MagicMock()
    agent.reporter = MagicMock()
    agent.correlator = MagicMock()
    return agent

# ---------------------------------------------------------------------------
# DashboardServer
# ---------------------------------------------------------------------------

class TestDashboardServer:
    """Dashboard server endpoints via TestClient."""

    @pytest.fixture
    def client(self, mock_agent):
        """Return a FastAPI TestClient."""
        from fastapi.testclient import TestClient
        server = DashboardServer(mock_agent)
        return TestClient(server.app)

    def test_health(self, mock_agent, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_status(self, mock_agent, client):
        resp = client.get("/api/status")
        data = resp.json()
        assert data["running"] is True
        assert data["monitor_events"] == 5
        assert data["health_events"] == 2
        assert data["recovery_attempts"] == 3
        assert data["reports_generated"] == 1
        assert data["correlation_groups"] == 2
        assert data["memory_connected"] is True

    def test_correlation_groups_list(self, mock_agent, client):
        from infra_agent_v2.correlation.correlator import CorrelationGroup
        from datetime import datetime, timezone
        group = CorrelationGroup(group_id="abc123", start_time=datetime.now(timezone.utc))
        mock_agent.correlator.get_active_groups.return_value = [group]
        resp = client.get("/api/correlation")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_correlation_group_by_id(self, mock_agent, client):
        from infra_agent_v2.correlation.correlator import CorrelationGroup
        from datetime import datetime, timezone
        group = CorrelationGroup(group_id="abc123", start_time=datetime.now(timezone.utc))
        mock_agent.correlator.get_group.return_value = group
        resp = client.get("/api/correlation/abc123")
        assert resp.status_code == 200
        assert resp.json()["group_id"] == "abc123"

    def test_correlation_group_not_found(self, mock_agent, client):
        mock_agent.correlator.get_group.return_value = None
        resp = client.get("/api/correlation/missing")
        assert resp.status_code == 404

    def test_correlation_flush(self, mock_agent, client):
        mock_agent.correlator.flush_expired.return_value = []
        resp = client.post("/api/correlation/flush")
        assert resp.status_code == 200
        assert resp.json()["flushed"] == 0

    def test_correlation_reset(self, mock_agent, client):
        resp = client.post("/api/correlation/reset")
        assert resp.status_code == 200
        assert resp.json()["reset"] is True

    def test_containers(self, mock_agent, client):
        mock_agent.docker.list_containers.return_value = [
            {"id": "abc123", "name": "web", "status": "running"},
        ]
        resp = client.get("/api/containers")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_container_info(self, mock_agent, client):
        mock_agent.docker.get_stats.return_value = {"cpu": 50}
        mock_agent.recovery.get_restart_count.return_value = 2
        mock_agent.recovery.is_in_cooldown.return_value = False
        resp = client.get("/api/containers/abc123")
        assert resp.status_code == 200
        assert resp.json()["restart_count"] == 2
        assert resp.json()["in_cooldown"] is False

    def test_container_not_found(self, mock_agent, client):
        mock_agent.docker.get_stats.return_value = {}
        resp = client.get("/api/containers/missing")
        assert resp.status_code == 404

    def test_incidents(self, mock_agent, client):
        from infra_agent_v2.memory.qdrant_store import Incident
        mock_agent.memory.get_all.return_value = [
            Incident(
                id="inc1",
                timestamp="2026-01-01T00:00:00+00:00",
                container_id="c1",
                container_name="web",
                event_type="crash",
                severity="critical",
                message="OOMKilled",
            ),
        ]
        resp = client.get("/api/incidents")
        data = resp.json()
        assert data["total"] == 1
        assert len(data["incidents"]) == 1

    def test_incidents_with_limit(self, mock_agent, client):
        resp = client.get("/api/incidents?limit=5")
        assert resp.status_code == 200

    def test_incident_not_found(self, mock_agent, client):
        mock_agent.memory.get_incident.return_value = None
        resp = client.get("/api/incidents/missing")
        assert resp.status_code == 404

    def test_incident_memory_unavailable(self, mock_agent, client):
        mock_agent.memory = None
        resp = client.get("/api/incidents/abc123")
        assert resp.status_code == 503

    def test_similar_incidents(self, mock_agent, client):
        mock_agent.analyzer.get_similar.return_value = []
        resp = client.get("/api/incidents/similar/OOMKilled")
        assert resp.status_code == 200

    def test_similar_with_limit(self, mock_agent, client):
        resp = client.get("/api/incidents/similar/OOMKilled?limit=3")
        assert resp.status_code == 200

    def test_recover_container(self, mock_agent, client):
        from infra_agent_v2.recovery.engine import RecoveryAttempt
        mock_agent.recovery.recover.return_value = RecoveryAttempt(
            "abc123", "2026-01-01T00:00:00+00:00", True, 1,
        )
        resp = client.post("/api/recovery/abc123")
        data = resp.json()
        assert data["success"] is True
        assert data["attempt_number"] == 1

    def test_reset_recovery(self, mock_agent, client):
        resp = client.post("/api/recovery/abc123/reset")
        assert resp.status_code == 200
        assert resp.json()["reset"] is True

    def test_generate_report(self, mock_agent, client):
        mock_agent.reporter.generate_text.return_value = "Report text"
        resp = client.get("/api/report")
        assert resp.status_code == 200

    def test_generate_json_report(self, mock_agent, client):
        mock_agent.reporter.generate_json.return_value = '{"incidents":[]}'
        resp = client.get("/api/report/json")
        assert resp.status_code == 200

    def test_status_no_memory(self, mock_agent, client):
        mock_agent.memory = None
        resp = client.get("/api/status")
        assert resp.status_code == 200
        assert resp.json()["memory_connected"] is False
