"""Tests for recovery/engine.py."""

import time
from unittest.mock import MagicMock

from infra_agent_v2.config import Config
from infra_agent_v2.recovery.engine import (
    RecoveryEngine,
    RecoveryAttempt,
    RecoveryAlert,
    RecoveryEvent,
)
from infra_agent_v2.actions.docker_actions import DockerActions, ActionResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_mock_actions(succeed=True):
    """Return a mock DockerActions that returns success or failure."""
    mock = MagicMock(spec=DockerActions)
    mock.restart.return_value = ActionResult(
        container_id="c1",
        container_name="web",
        action="restart",
        success=succeed,
        details="ok" if succeed else "timeout",
    )
    return mock

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class TestRecoveryDataModels:
    """RecoveryAttempt, RecoveryAlert, RecoveryEvent."""

    def test_recovery_attempt(self):
        a = RecoveryAttempt("c1", "2026-01-01T00:00:00+00:00", True, 1)
        assert a.success is True
        assert a.attempt_number == 1

    def test_recovery_alert(self):
        alert = RecoveryAlert(
            timestamp="2026-01-01T00:00:00+00:00",
            container_id="c1",
            container_name="web",
            reason="Max restarts exceeded",
            attempt_count=4,
            max_allowed=3,
        )
        assert alert.attempt_count == 4
        assert alert.max_allowed == 3

    def test_recovery_event(self):
        event = RecoveryEvent(
            timestamp="2026-01-01T00:00:00+00:00",
            container_id="c1",
            container_name="web",
            action="restart_success",
            attempt_number=1,
            success=True,
        )
        assert event.action == "restart_success"
        assert event.success is True

# ---------------------------------------------------------------------------
# Basic Operations
# ---------------------------------------------------------------------------

class TestRecoveryEngineBasic:
    """Initialization and registration."""

    def test_init(self, config):
        mock_actions = _make_mock_actions()
        engine = RecoveryEngine(config, docker_actions=mock_actions)
        assert engine.docker is mock_actions
        assert engine.config.max_restarts == 3

    def test_register_event_handler(self, config):
        engine = RecoveryEngine(config, docker_actions=_make_mock_actions())
        handler = MagicMock()
        engine.register_event_handler(handler)
        assert handler in engine._event_handlers

    def test_register_alert_handler(self, config):
        engine = RecoveryEngine(config, docker_actions=_make_mock_actions())
        handler = MagicMock()
        engine.register_alert_handler(handler)
        assert handler in engine._alert_handlers

# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------

class TestRecoveryEngineRecover:
    """Container recovery flow."""

    def test_recover_success(self, config):
        mock_actions = _make_mock_actions(succeed=True)
        engine = RecoveryEngine(config, docker_actions=mock_actions)
        attempt = engine.recover("c1", "web")
        assert attempt.success is True
        assert attempt.attempt_number == 1
        mock_actions.restart.assert_called_once_with("c1", timeout=30)

    def test_recover_failure(self, config):
        mock_actions = _make_mock_actions(succeed=False)
        engine = RecoveryEngine(config, docker_actions=mock_actions)
        attempt = engine.recover("c1", "web")
        assert attempt.success is False
        assert attempt.attempt_number == 1

    def test_recover_tracks_attempts(self, config):
        mock_actions = _make_mock_actions(succeed=True)
        engine = RecoveryEngine(config, docker_actions=mock_actions)
        engine.recover("c1")
        engine.recover("c1")
        assert engine.get_restart_count("c1") == 2

    def test_recover_respects_max_restarts(self, config):
        mock_actions = _make_mock_actions(succeed=True)
        engine = RecoveryEngine(config, docker_actions=mock_actions)
        for _ in range(3):
            engine.recover("c1")
            engine._last_restart_time["c1"] = 0.0  # bypass cooldown
        attempt = engine.recover("c1")
        assert attempt.success is False
        assert attempt.attempt_number == 4
        assert mock_actions.restart.call_count == 3

    def test_recover_alert_emitted_on_max(self, config):
        mock_actions = _make_mock_actions(succeed=True)
        alert_handler = MagicMock()
        engine = RecoveryEngine(config, docker_actions=mock_actions,
                                alert_handlers=[alert_handler])
        for _ in range(3):
            engine.recover("c1")
        engine.recover("c1")
        alert_handler.assert_called_once()
        alert = alert_handler.call_args[0][0]
        assert isinstance(alert, RecoveryAlert)
        assert alert.attempt_count == 4

    def test_recover_event_emitted(self, config):
        mock_actions = _make_mock_actions(succeed=True)
        event_handler = MagicMock()
        engine = RecoveryEngine(config, docker_actions=mock_actions,
                                event_handlers=[event_handler])
        engine.recover("c1", "web")
        event_handler.assert_called_once()
        event = event_handler.call_args[0][0]
        assert isinstance(event, RecoveryEvent)
        assert event.success is True

    def test_recover_handler_error_does_not_crash(self, config):
        mock_actions = _make_mock_actions(succeed=True)
        engine = RecoveryEngine(config, docker_actions=mock_actions,
                                event_handlers=[MagicMock(side_effect=RuntimeError("broken"))])
        engine.recover("c1")  # should not raise

# ---------------------------------------------------------------------------
# Cooldown
# ---------------------------------------------------------------------------

class TestRecoveryEngineCooldown:
    """Cooldown enforcement."""

    def test_cooldown_skips_restart(self, config):
        mock_actions = _make_mock_actions(succeed=True)
        engine = RecoveryEngine(config, docker_actions=mock_actions)
        engine.recover("c1")
        attempt = engine.recover("c1")
        assert attempt.success is False
        assert mock_actions.restart.call_count == 1

    def test_cooldown_elapsed_allows_restart(self, config):
        mock_actions = _make_mock_actions(succeed=True)
        engine = RecoveryEngine(config, docker_actions=mock_actions)
        engine._last_restart_time["c1"] = 0.0
        attempt = engine.recover("c1")
        assert attempt.success is True

    def test_is_in_cooldown_true(self, config):
        mock_actions = _make_mock_actions()
        engine = RecoveryEngine(config, docker_actions=mock_actions)
        engine._last_restart_time["c1"] = time.monotonic() - 10
        assert engine.is_in_cooldown("c1") is True

    def test_is_in_cooldown_false(self, config):
        mock_actions = _make_mock_actions()
        engine = RecoveryEngine(config, docker_actions=mock_actions)
        engine._last_restart_time["c1"] = 0.0
        assert engine.is_in_cooldown("c1") is False

    def test_is_in_cooldown_unknown_container(self, config):
        mock_actions = _make_mock_actions()
        engine = RecoveryEngine(config, docker_actions=mock_actions)
        assert engine.is_in_cooldown("unknown") is False

# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestRecoveryEngineReset:
    """Reset restart tracking."""

    def test_reset_clears_counts(self, config):
        mock_actions = _make_mock_actions()
        engine = RecoveryEngine(config, docker_actions=mock_actions)
        engine.recover("c1")
        engine.recover("c1")
        assert engine.get_restart_count("c1") == 2
        engine.reset("c1")
        assert engine.get_restart_count("c1") == 0

    def test_reset_unknown_container_no_error(self, config):
        mock_actions = _make_mock_actions()
        engine = RecoveryEngine(config, docker_actions=mock_actions)
        engine.reset("nonexistent")

# ---------------------------------------------------------------------------
# Event/Alert Handlers
# ---------------------------------------------------------------------------

class TestRecoveryEngineHandlers:
    """Event and alert handler dispatch."""

    def test_alert_handler_receives_alert(self, config):
        mock_actions = _make_mock_actions(succeed=True)
        alert_handler = MagicMock()
        engine = RecoveryEngine(config, docker_actions=mock_actions,
                                alert_handlers=[alert_handler])
        for _ in range(3):
            engine.recover("c1", "web")
        engine.recover("c1", "web")
        alert_handler.assert_called_once()
        alert = alert_handler.call_args[0][0]
        assert alert.container_name == "web"

    def test_event_handler_receives_event_on_failure(self, config):
        mock_actions = _make_mock_actions(succeed=False)
        event_handler = MagicMock()
        engine = RecoveryEngine(config, docker_actions=mock_actions,
                                event_handlers=[event_handler])
        engine.recover("c1", "web")
        event = event_handler.call_args[0][0]
        assert event.action == "restart_failed"
        assert event.success is False
