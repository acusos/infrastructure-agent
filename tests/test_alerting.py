"""Tests for alerting/engine.py."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from infra_agent_v2.alerting.engine import (
    Alert,
    AlertEngine,
    LoggerHandler,
    WebhookHandler,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def alert():
    return Alert(
        alert_id="alert-001",
        severity="critical",
        title="Container crashed",
        message="OOMKilled",
        container_id="abc123",
        container_name="web",
        event_type="crash",
        correlation_group_id="grp-001",
        timestamp="2026-01-01T00:00:00+00:00",
    )

@pytest.fixture
def engine(config):
    """Return an AlertEngine with no webhook configured."""
    return AlertEngine(config)

# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

class TestAlert:
    """Alert dataclass."""

    def test_auto_id(self):
        alert = Alert(alert_id="", severity="info", title="test", message="test")
        assert alert.alert_id.startswith("alert-")

    def test_auto_timestamp(self):
        alert = Alert(alert_id="a", severity="info", title="test", message="test")
        assert alert.timestamp

    def test_to_dict(self, alert):
        d = alert.to_dict()
        assert d["alert_id"] == "alert-001"
        assert d["severity"] == "critical"
        assert d["metadata"] == {}

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

class TestLoggerHandler:
    """LoggerHandler."""

    def test_matches_all(self, alert):
        handler = LoggerHandler()
        assert handler.matches(alert) is True

    def test_send_returns_true(self, alert):
        handler = LoggerHandler()
        assert handler.send(alert) is True

class TestWebhookHandler:
    """WebhookHandler."""

    def test_matches_no_url(self):
        handler = WebhookHandler(url="")
        assert handler.matches(Alert(alert_id="a", severity="critical", title="t", message="m")) is False

    def test_matches_critical_severity(self):
        handler = WebhookHandler(url="http://localhost:9999", min_severity="warning")
        alert = Alert(alert_id="a", severity="critical", title="t", message="m")
        assert handler.matches(alert) is True

    def test_matches_info_below_warning(self):
        handler = WebhookHandler(url="http://localhost:9999", min_severity="warning")
        alert = Alert(alert_id="a", severity="info", title="t", message="m")
        assert handler.matches(alert) is False

    def test_send_success(self, alert):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
            handler = WebhookHandler(url="http://localhost:9999")
            assert handler.send(alert) is True

    def test_send_failure(self, alert):
        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError()
            handler = WebhookHandler(url="http://localhost:9999")
            assert handler.send(alert) is False

# ---------------------------------------------------------------------------
# AlertEngine
# ---------------------------------------------------------------------------

class TestAlertEngine:
    """AlertEngine integration."""

    def test_default_handler_is_logger(self, engine):
        assert isinstance(engine._handlers[0], LoggerHandler)

    def test_send_critical_alert(self, engine, alert):
        count = engine.send(alert)
        assert count >= 1

    def test_send_returns_handler_count(self, engine, alert):
        count = engine.send(alert)
        assert count >= 1

    def test_send_alert_convenience(self, engine):
        alert = engine.send_alert(
            severity="warning",
            title="Test",
            message="Test alert",
        )
        assert alert.alert_id.startswith("alert-")
        assert alert.severity == "warning"

    def test_register_dispatch_callback(self, engine, alert):
        received = []
        engine.register_dispatch_callback(received.append)
        engine.send(alert)
        assert len(received) == 1

    def test_send_no_handlers_matches(self, engine, alert):
        """If all handlers skip, count is 0."""
        engine._handlers.clear()
        count = engine.send(alert)
        assert count == 0

    def test_webhook_handler_added_when_env_set(self, config):
        with patch.dict("os.environ", {"INFRA_ALERT_WEBHOOK_URL": "http://hook.example.com"}):
            engine = AlertEngine(config)
            webhook_handlers = [h for h in engine._handlers if isinstance(h, WebhookHandler)]
            assert len(webhook_handlers) == 1
