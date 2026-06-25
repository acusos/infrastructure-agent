"""Tests for main.py (InfraAgent orchestrator)."""

from unittest.mock import MagicMock, patch

import pytest

from infra_agent_v2.config import Config
from infra_agent_v2.main import InfraAgent, AgentState, run

# ---------------------------------------------------------------------------
# AgentState
# ---------------------------------------------------------------------------

class TestAgentState:
    """AgentState dataclass."""

    def test_defaults(self):
        state = AgentState()
        assert state.running is False
        assert state.monitor_events == 0
        assert state.reports_generated == 0

    def test_populated(self):
        state = AgentState(running=True, monitor_events=5, reports_generated=2)
        assert state.running is True
        assert state.monitor_events == 5

# ---------------------------------------------------------------------------
# InfraAgent
# ---------------------------------------------------------------------------

class TestInfraAgent:
    """Full orchestrator tests with mocked dependencies."""

    @pytest.fixture
    def agent(self, config):
        """Create an InfraAgent with all dependencies mocked."""
        with patch("infra_agent_v2.main.DockerActions") as MockDocker, \
             patch("infra_agent_v2.main.MonitorEngine") as MockMonitor, \
             patch("infra_agent_v2.main.HealthChecker") as MockHealth, \
             patch("infra_agent_v2.main.IncidentAnalyzer") as MockAnalyzer, \
             patch("infra_agent_v2.main.RecoveryEngine") as MockRecovery, \
             patch("infra_agent_v2.main.ReportGenerator") as MockReporter, \
             patch("infra_agent_v2.main.QdrantMemoryStore") as MockQdrant, \
             patch("infra_agent_v2.main.IncidentCorrelator") as MockCorrelator:

            # Docker
            mock_docker = MagicMock()
            mock_docker.client = MagicMock()
            MockDocker.return_value = mock_docker

            # Monitor
            mock_monitor = MagicMock()
            MockMonitor.return_value = mock_monitor

            # Health
            mock_health = MagicMock()
            MockHealth.return_value = mock_health

            # Analyzer
            mock_analyzer = MagicMock()
            MockAnalyzer.return_value = mock_analyzer

            # Recovery
            mock_recovery = MagicMock()
            MockRecovery.return_value = mock_recovery

            # Reporter
            mock_reporter = MagicMock()
            MockReporter.return_value = mock_reporter

            # Qdrant — raise so it gets caught
            MockQdrant.side_effect = RuntimeError("Qdrant unavailable")

            # Correlator
            mock_correlator = MagicMock()
            MockCorrelator.return_value = mock_correlator

            agent = InfraAgent(config)
            return agent

    def test_init_wires_subsystems(self, config, agent):
        assert agent.config is not None
        assert agent.docker is not None
        assert agent.monitor is not None
        assert agent.health is not None
        assert agent.analyzer is not None
        assert agent.recovery is not None
        assert agent.reporter is not None

    def test_init_no_qdrant_continues(self, config, agent):
        assert agent.memory is None
        assert agent.state.running is False

    def test_start_stops(self, config, agent):
        agent.start()
        assert agent.state.running is True
        agent.stop()
        assert agent.state.running is False
        agent.monitor.stop.assert_called_once()
        agent.health.stop.assert_called_once()

    def test_start_already_running(self, config, agent):
        agent.start()
        agent.start()  # should be idempotent, no error

    def test_poll_once_returns_dict(self, config, agent):
        agent.monitor.poll_once.return_value = []
        agent.health.check_once.return_value = []
        result = agent.poll_once()
        assert "timestamp" in result
        assert result["monitor_events"] == 0
        assert result["health_events"] == 0

    def test_poll_once_counts_monitor_events(self, config, agent):
        mock_event = MagicMock()
        mock_event.event_type = "state_change"
        mock_event.severity = "info"
        mock_event.container_name = "web"
        mock_event.message = "container stopped"
        mock_event.container_id = "abc"
        agent.monitor.poll_once.return_value = [mock_event]
        agent.health.check_once.return_value = []

        result = agent.poll_once()
        assert result["monitor_events"] == 1

    def test_poll_once_counts_health_events(self, config, agent):
        agent.monitor.poll_once.return_value = []
        agent.health.check_once.return_value = [MagicMock()]
        result = agent.poll_once()
        assert result["health_events"] == 1

    def test_handle_monitor_event_triggers_analyze(self, config, agent):
        mock_event = MagicMock()
        mock_event.event_type = "state_change"
        mock_event.severity = "warning"
        mock_event.container_name = "web"
        mock_event.message = "container restarted"
        mock_event.container_id = "abc"
        agent._handle_monitor_event(mock_event)
        agent.analyzer.analyze.assert_called_once()
        assert agent.state.monitor_events == 1

    def test_handle_monitor_critical_triggers_recovery(self, config, agent):
        mock_event = MagicMock()
        mock_event.event_type = "crash"
        mock_event.severity = "critical"
        mock_event.container_name = "web"
        mock_event.message = "container crashed"
        mock_event.container_id = "abc"
        agent._handle_monitor_event(mock_event)
        agent.recovery.recover.assert_called_once_with("abc", "web")

    def test_handle_health_failure_triggers_analyze(self, config, agent):
        mock_event = MagicMock()
        mock_event.check_name = "app_health"
        mock_event.new_status = "failure"
        mock_event.message = "HTTP 500"
        mock_event.severity = "critical"
        agent._handle_health_event(mock_event)
        agent.analyzer.analyze.assert_called_once()
        assert agent.state.health_events == 1

    def test_handle_health_ok_does_not_analyze(self, config, agent):
        mock_event = MagicMock()
        mock_event.check_name = "app_health"
        mock_event.new_status = "ok"
        mock_event.message = "HTTP 200"
        mock_event.severity = "info"
        agent._handle_health_event(mock_event)
        agent.analyzer.analyze.assert_not_called()

    def test_handle_recovery_alert_generates_report(self, config, agent):
        mock_alert = MagicMock()
        mock_alert.timestamp = "2026-01-01T00:00:00+00:00"
        mock_alert.container_id = "c1"
        mock_alert.container_name = "web"
        mock_alert.reason = "Max restarts exceeded"
        mock_alert.attempt_count = 4
        mock_alert.max_allowed = 3
        agent._handle_recovery_alert(mock_alert)
        agent.reporter.generate_text.assert_called_once()

    def test_handle_recovery_event_increments_count(self, config, agent):
        mock_event = MagicMock()
        mock_event.action = "restart_success"
        mock_event.container_name = "web"
        mock_event.attempt_number = 1
        mock_event.success = True
        agent._handle_recovery_event(mock_event)
        assert agent.state.recovery_attempts == 1

# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------

class TestRun:
    """Top-level entry point behavior."""

    def test_run_exists(self):
        from infra_agent_v2.main import run, main
        assert callable(run)
        assert callable(main)
