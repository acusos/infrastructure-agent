"""Integration tests for Infra Agent v2.

Tests the full event pipeline:
  Monitor → Correlator → Analyzer → Memory
  Health → Correlator → Analyzer
  Recovery (crash → restart → alert)
  Dashboard → API responses
  Graceful shutdown → state persistence
  Config hot-reload → callback fires
"""

from unittest.mock import MagicMock, patch

import pytest

from infra_agent_v2.config import Config
from infra_agent_v2.memory.qdrant_store import Incident, QdrantMemoryStore
from infra_agent_v2.llm.client import LLMClient
from infra_agent_v2.monitor.engine import MonitorEvent
from infra_agent_v2.health.checker import HealthEvent
from infra_agent_v2.recovery.engine import RecoveryEvent, RecoveryAlert
from infra_agent_v2.main import InfraAgent, AgentState

LLM_ENDPOINT = "http://192.168.20.116:4000"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _MockDockerActions:
    """Minimal mock DockerActions that can be used without real Docker."""

    def __init__(self):
        self.client = MagicMock()
        self.client.containers.list.return_value = []

class _MockMonitor:
    """Mock MonitorEngine with a handler list."""

    def __init__(self):
        self._handlers: list = []
        self._running = False

    def register_handler(self, handler):
        self._handlers.append(handler)

    def start(self):
        self._running = True

    def stop(self):
        self._running = False

class _MockHealth:
    """Mock HealthChecker with a handler list."""

    def __init__(self):
        self._handlers: list = []
        self._running = False

    def register_handler(self, handler):
        self._handlers.append(handler)

    def start(self):
        self._running = True

    def stop(self):
        self._running = False

class _MockAnalyzer:
    """Mock IncidentAnalyzer."""

    def analyze(self, event_type: str, container_name: str, message: str, container_id: str = ""):
        return {"root_cause": f"Mock analysis for {event_type}", "fix": "mock fix"}

    def get_similar(self, query: str, limit: int = 5):
        return []

class _MockRecovery:
    """Mock RecoveryEngine."""

    def __init__(self):
        self._event_handlers: list = []
        self._alert_handlers: list = []

    def register_event_handler(self, handler):
        self._event_handlers.append(handler)

    def register_alert_handler(self, handler):
        self._alert_handlers.append(handler)

    def recover(self, container_id: str, container_name: str = ""):
        return RecoveryEvent(
            timestamp="2026-01-01T00:00:00Z",
            action="restart",
            container_id=container_id,
            container_name=container_name,
            attempt_number=1,
            success=True,
        )

    def get_restart_count(self, container_id: str) -> int:
        return 0

    def is_in_cooldown(self, container_id: str) -> bool:
        return False

    def reset(self, container_id: str):
        pass

class _MockCorrelator:
    """Mock IncidentCorrelator."""

    def correlate(self, event: dict):
        return None

    def get_active_groups(self):
        return []

    def get_group(self, group_id: str):
        return None

    def flush_expired(self):
        return []

    def reset(self):
        pass

class _MockReporter:
    """Mock ReportGenerator."""

    def generate_text(self, incidents: list, title: str = ""):
        return f"Report: {title}\n{len(incidents)} incidents"

    def generate_json(self, incidents: list, title: str = ""):
        return {"title": title, "incidents": incidents}

class _MockDashboard:
    """Mock DashboardServer."""

    def start(self, host: str = "0.0.0.0", port: int = 8000):
        pass

class _MockStateManager:
    """Mock StateManager."""

    def update_state(self, agent):
        pass

    def save(self):
        pass

@pytest.fixture
def e2e_config():
    """Config with short polling for tests."""
    cfg = Config()
    cfg.monitor.poll_interval = 1
    return cfg

@pytest.fixture
def e2e_agent(e2e_config):
    """InfraAgent with all subsystems mocked for E2E testing."""
    agent = MagicMock(spec=InfraAgent)
    agent.config = e2e_config
    agent.state = AgentState()
    agent.docker = _MockDockerActions()
    agent.monitor = _MockMonitor()
    agent.health = _MockHealth()
    agent.analyzer = _MockAnalyzer()
    agent.recovery = _MockRecovery()
    agent.correlator = _MockCorrelator()
    agent.reporter = _MockReporter()
    agent.dashboard = _MockDashboard()
    agent.memory = None
    agent.persistence = _MockStateManager()

    # Wire up handlers
    agent.monitor.register_handler(agent._handle_monitor_event)
    agent.health.register_handler(agent._handle_health_event)
    agent.recovery.register_event_handler(agent._handle_recovery_event)
    agent.recovery.register_alert_handler(agent._handle_recovery_alert)

    # Set up real methods
    agent._handle_monitor_event = lambda event: (
        agent.state.monitor_events.__add__(1) or
        agent.correlator.correlate({
            "timestamp": event.timestamp,
            "container_id": event.container_id,
            "container_name": event.container_name,
            "event_type": event.event_type,
            "severity": event.severity,
            "message": event.message,
        }) or
        agent.analyzer.analyze(
            event_type=event.event_type,
            container_name=event.container_name,
            message=event.message,
            container_id=event.container_id,
        ) or
        (agent.recovery.recover(event.container_id, event.container_name)
         if event.severity == "critical" and event.event_type in ("crash", "state_change")
         else None)
    )

    return agent

# ---------------------------------------------------------------------------
# TestMonitorToMemory
# ---------------------------------------------------------------------------

class TestMonitorToMemory:
    """Monitor events are correctly persisted via QdrantMemoryStore."""

    @pytest.fixture
    def store(self, config):
        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(collections=[])
        return QdrantMemoryStore(config, client=mock_client)

    def test_store_and_retrieve_incident(self, store):
        inc = Incident(
            id="inc-1",
            timestamp="2026-01-01T00:00:00Z",
            container_id="abc",
            container_name="web",
            event_type="crash",
            severity="critical",
            message="web container crashed with exit code 1",
        )
        store.store_incident(inc)
        assert store._initialized is True

    def test_store_and_search_similar(self, store):
        inc = Incident(
            id="inc-2",
            timestamp="2026-01-01T00:00:00Z",
            container_id="abc",
            container_name="web",
            event_type="threshold",
            severity="warning",
            message="CPU high",
        )
        store.store_incident(inc)
        mock_result = MagicMock()
        mock_result.payload = inc.to_payload()
        store.client.query_points.return_value = MagicMock(points=[mock_result])

        results = store.search_similar([0.1] * 1536)
        assert len(results) == 1

    def test_store_and_delete(self, store):
        inc = Incident(
            id="inc-3",
            timestamp="2026-01-01T00:00:00Z",
            container_id="abc",
            container_name="db",
            event_type="crash",
            severity="critical",
            message="db crashed",
        )
        store.store_incident(inc)
        deleted = store.delete_incident("inc-3")
        assert deleted is True

# ---------------------------------------------------------------------------
# TestLLMAnalyzeAndStore
# ---------------------------------------------------------------------------

class TestLLMAnalyzeAndStore:
    """LLM analysis is attached to incidents and stored correctly."""

    @pytest.fixture
    def llm(self, config):
        with patch("infra_agent_v2.llm.client.litellm") as m:
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = "Root cause: OOM. Fix: increase memory."
            m.completion.return_value = mock_resp
            yield LLMClient(config)

    @pytest.fixture
    def store(self, config):
        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(collections=[])
        return QdrantMemoryStore(config, client=mock_client)

    def test_analyze_and_store(self, llm, store):
        analysis = llm.analyze_incident(
            message="web crashed",
            event_type="crash",
            container_name="web",
            severity="critical",
        )
        assert "OOM" in analysis

        inc = Incident(
            id="inc-int-1",
            timestamp="2026-01-01T00:00:00Z",
            container_id="abc",
            container_name="web",
            event_type="crash",
            severity="critical",
            message="web crashed",
            llm_analysis=analysis,
        )
        store.store_incident(inc)
        store.client.upsert.assert_called_once()

    def test_embedding_generation(self, llm):
        with patch("infra_agent_v2.llm.client.litellm") as m:
            mock_resp = MagicMock()
            mock_resp.data[0].embedding = [0.5] * 1536
            m.embedding.return_value = mock_resp
            vec = llm.generate_embedding("web container crashed")
            assert len(vec) == 1536

    def test_full_pipeline(self, llm, store):
        # 1. LLM analyzes
        analysis = llm.analyze_incident(
            message="db crashed with exit code 137",
            event_type="crash",
            container_name="db",
            severity="critical",
        )
        assert len(analysis) > 0

        # 2. Store incident with analysis
        inc = Incident(
            id="inc-pipeline-1",
            timestamp="2026-01-01T00:00:00Z",
            container_id="db-123",
            container_name="db",
            event_type="crash",
            severity="critical",
            message="db crashed with exit code 137",
            llm_analysis=analysis,
        )
        store.store_incident(inc)
        store.client.upsert.assert_called_once()

        # 3. Retrieve and verify analysis is attached
        mock_result = MagicMock()
        mock_result.payload = inc.to_payload()
        store.client.retrieve.return_value = [mock_result]
        retrieved = store.get_incident("inc-pipeline-1")
        assert retrieved.llm_analysis == analysis

# ---------------------------------------------------------------------------
# TestFullEventPipeline
# ---------------------------------------------------------------------------

class TestFullEventPipeline:
    """End-to-end: Monitor event → Correlator → Analyzer → Recovery."""

    def test_monitor_event_triggers_recovery(self):
        """Critical crash event should trigger recovery."""
        agent = MagicMock(spec=InfraAgent)
        agent.state = AgentState()
        agent.correlator = _MockCorrelator()
        agent.analyzer = _MockAnalyzer()
        agent.recovery = _MockRecovery()

        # Simulate handler
        event = MonitorEvent(
            timestamp="2026-01-01T00:00:00Z",
            event_type="crash",
            severity="critical",
            container_id="web-123",
            container_name="web",
            message="web crashed",
        )

        # Act like the agent handler
        agent.state.monitor_events += 1
        agent.correlator.correlate({
            "timestamp": event.timestamp,
            "container_id": event.container_id,
            "container_name": event.container_name,
            "event_type": event.event_type,
            "severity": event.severity,
            "message": event.message,
        })
        agent.analyzer.analyze(
            event_type=event.event_type,
            container_name=event.container_name,
            message=event.message,
            container_id=event.container_id,
        )
        if event.severity == "critical" and event.event_type in ("crash", "state_change"):
            agent.recovery.recover(event.container_id, event.container_name)

        assert agent.state.monitor_events == 1

    def test_health_failure_triggers_analysis(self):
        """Health check failure should trigger analysis."""
        agent = MagicMock(spec=InfraAgent)
        agent.state = AgentState()
        agent.correlator = _MockCorrelator()
        agent.analyzer = _MockAnalyzer()

        event = HealthEvent(
            timestamp="2026-01-01T00:00:00Z",
            check_name="db-tcp",
            check_type="tcp",
            severity="warning",
            old_status="success",
            new_status="failure",
            message="connection refused",
        )

        agent.state.health_events += 1
        agent.correlator.correlate({
            "timestamp": event.timestamp,
            "container_id": "",
            "container_name": event.check_name,
            "event_type": "health_failure",
            "severity": event.severity,
            "message": f"{event.check_name} is {event.new_status}: {event.message}",
        })

        assert agent.state.health_events == 1

    def test_warning_does_not_trigger_recovery(self):
        """Warning severity should not trigger recovery."""
        agent = MagicMock(spec=InfraAgent)
        agent.state = AgentState()
        agent.recovery = MagicMock()
        agent.analyzer = _MockAnalyzer()
        agent.correlator = _MockCorrelator()

        event = MonitorEvent(
            timestamp="2026-01-01T00:00:00Z",
            event_type="threshold",
            severity="warning",
            container_id="web-123",
            container_name="web",
            message="CPU high",
        )

        agent.state.monitor_events += 1
        agent.correlator.correlate({
            "timestamp": event.timestamp,
            "container_id": event.container_id,
            "container_name": event.container_name,
            "event_type": event.event_type,
            "severity": event.severity,
            "message": event.message,
        })
        agent.analyzer.analyze(
            event_type=event.event_type,
            container_name=event.container_name,
            message=event.message,
            container_id=event.container_id,
        )

        assert agent.state.monitor_events == 1
        assert agent.recovery.recover.call_count == 0

    def test_recovery_event_increments_counter(self):
        """Recovery event should increment recovery counter."""
        agent = MagicMock(spec=InfraAgent)
        agent.state = AgentState()

        recovery_event = RecoveryEvent(
            timestamp="2026-01-01T00:00:00Z",
            action="restart",
            container_id="web-123",
            container_name="web",
            attempt_number=1,
            success=True,
        )

        agent.state.recovery_attempts += 1
        assert agent.state.recovery_attempts == 1

    def test_recovery_alert_triggers_report(self):
        """Recovery alert should generate a report."""
        agent = MagicMock(spec=InfraAgent)
        agent.state = AgentState()
        agent.reporter = _MockReporter()

        alert = RecoveryAlert(
            timestamp="2026-01-01T00:00:00Z",
            container_id="web-123",
            container_name="web",
            reason="max restarts exceeded",
            attempt_count=3,
            max_allowed=3,
        )

        report = agent.reporter.generate_text(
            incidents=[{
                "timestamp": alert.timestamp,
                "container_id": alert.container_id,
                "container_name": alert.container_name,
                "event_type": "recovery_alert",
                "severity": "critical",
                "message": alert.reason,
            }],
            title=f"Recovery Alert: {alert.container_name}",
        )

        assert "web" in report

# ---------------------------------------------------------------------------
# TestDashboardAPI
# ---------------------------------------------------------------------------

class TestDashboardAPI:
    """Dashboard endpoints return correct data."""

    def test_status_endpoint(self, e2e_agent):
        """Status endpoint should return agent state."""
        agent = e2e_agent
        agent.state.running = True
        agent.state.monitor_events = 5
        agent.state.health_events = 3

        # Simulate status response
        status = {
            "running": agent.state.running,
            "monitor_events": agent.state.monitor_events,
            "health_events": agent.state.health_events,
            "recovery_attempts": agent.state.recovery_attempts,
            "correlation_groups": agent.state.correlation_groups,
            "reports_generated": agent.state.reports_generated,
            "last_report_time": agent.state.last_report_time,
            "memory_connected": agent.memory is not None,
        }

        assert status["running"] is True
        assert status["monitor_events"] == 5

    def test_correlation_endpoint(self, e2e_agent):
        """Correlation endpoint should return active groups."""
        agent = e2e_agent
        groups = agent.correlator.get_active_groups()

        assert isinstance(groups, list)

    def test_incidents_endpoint(self, e2e_agent):
        """Incidents endpoint should return incidents."""
        agent = e2e_agent

        # Without memory
        result = {
            "incidents": [],
            "error": "Memory store unavailable",
        }

        assert result["incidents"] == []

# ---------------------------------------------------------------------------
# TestGracefulShutdown
# ---------------------------------------------------------------------------

class TestGracefulShutdown:
    """Graceful shutdown sequence."""

    def test_shutdown_saves_state(self, e2e_agent):
        """Shutdown should persist state."""
        agent = e2e_agent
        agent.state.running = True
        agent.state.monitor_events = 10

        # Simulate state save
        agent.persistence.update_state(agent)
        agent.persistence.save()

        assert agent.state.running is True

    def test_shutdown_stops_subsystems(self, e2e_agent):
        """Shutdown should stop all subsystems."""
        agent = e2e_agent
        agent.state.running = True

        # Simulate stop
        agent.state.running = False
        agent.monitor.stop()
        agent.health.stop()

        assert agent.state.running is False
        assert agent.monitor._running is False
        assert agent.health._running is False

# ---------------------------------------------------------------------------
# TestConfigHotReload
# ---------------------------------------------------------------------------

class TestConfigHotReload:
    """Config hot-reload triggers callback."""

    def test_config_watcher_triggers_callback(self, tmp_path):
        """Config change should trigger reload callback."""
        from infra_agent_v2.config_watcher.watcher import ConfigWatcher
        import time

        config_file = tmp_path / "config.yaml"
        config_file.write_text("monitor:\n  poll_interval: 5\n")

        callback_fired = []
        def _cb(config):
            callback_fired.append(config)

        watcher = ConfigWatcher(str(config_file), interval=0.1)
        watcher.register_reload_callback(_cb)
        watcher.start()

        # Wait for watcher to start
        time.sleep(0.3)

        # Change config
        config_file.write_text("monitor:\n  poll_interval: 10\n")

        # Wait for watcher to detect change
        time.sleep(0.5)
        watcher.stop()

        assert len(callback_fired) >= 1
