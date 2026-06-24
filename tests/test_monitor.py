"""Tests for the monitor engine."""

from unittest.mock import MagicMock, patch

import pytest

from infra_agent_v2.config import Config
from infra_agent_v2.monitor.engine import ContainerState, MonitorEngine, MonitorEvent


class TestMonitorEngineBasic:
    """Basic monitor engine initialization and lifecycle tests."""

    def test_create_engine(self, config):
        engine = MonitorEngine(config)
        assert engine.docker_client is None
        assert engine._running is False
        assert engine._event_handlers == []

    def test_register_handler(self, config):
        engine = MonitorEngine(config)
        handler = MagicMock()
        engine.register_handler(handler)
        assert handler in engine._event_handlers

    def test_register_multiple_handlers(self, config):
        engine = MonitorEngine(config)
        h1, h2 = MagicMock(), MagicMock()
        engine.register_handler(h1)
        engine.register_handler(h2)
        assert engine._event_handlers == [h1, h2]

    def test_start_idempotent(self, config):
        engine = MonitorEngine(config)
        engine._running = True
        engine.start()  # should not raise, just log a warning
        assert engine._running is True

    def test_stop(self, config):
        engine = MonitorEngine(config)
        engine._running = True
        engine.stop()
        assert engine._running is False

    def test_poll_without_docker_client(self, config):
        engine = MonitorEngine(config)
        events = engine.poll_once()
        assert events == []

    def test_poll_with_docker_error(self, config):
        mock_client = MagicMock()
        mock_client.containers.list.side_effect = Exception("connection refused")
        engine = MonitorEngine(config, docker_client=mock_client)
        events = engine.poll_once()
        assert events == []


class TestMonitorEngineEvents:
    """Test that monitor emits events for state changes."""

    def test_state_change_event_emitted(self, config, docker_container_mock):
        container = docker_container_mock
        container.status = "running"
        container.short_id = "abc123"
        container.name = "test-container"

        mock_client = MagicMock()
        mock_client.containers.list.return_value = [container]

        engine = MonitorEngine(config, docker_client=mock_client)

        # First poll establishes baseline (no events)
        events = engine.poll_once()
        assert events == []

        # Simulate container stopping
        container.status = "exited"
        container.attrs = {"State": {"ExitCode": 0}}
        container.stats.side_effect = Exception("stats unavailable")

        events = engine.poll_once()
        assert len(events) == 1
        assert events[0].event_type == "state_change"
        assert events[0].container_name == "test-container"
        assert events[0].severity == "info"

    def test_crash_event_emitted(self, config, docker_container_mock):
        container = docker_container_mock
        container.status = "running"
        container.short_id = "abc123"
        container.name = "test-container"

        mock_client = MagicMock()
        mock_client.containers.list.return_value = [container]

        engine = MonitorEngine(config, docker_client=mock_client)
        engine.poll_once()  # baseline

        # Container crashes with non-zero exit code
        container.status = "exited"
        container.attrs = {"State": {"ExitCode": 1}}
        container.stats.side_effect = Exception("stats unavailable")

        events = engine.poll_once()
        # Both state_change and crash events should be emitted
        assert len(events) == 2
        crash_events = [e for e in events if e.event_type == "crash"]
        assert len(crash_events) == 1
        assert crash_events[0].severity == "critical"

    def test_handler_called_on_event(self, config, docker_container_mock):
        container = docker_container_mock
        container.status = "running"
        container.short_id = "abc123"
        container.name = "test-container"

        mock_client = MagicMock()
        mock_client.containers.list.return_value = [container]

        engine = MonitorEngine(config, docker_client=mock_client)
        handler = MagicMock()
        engine.register_handler(handler)

        engine.poll_once()  # baseline

        container.status = "exited"
        container.attrs = {"State": {"ExitCode": 0}}
        container.stats.side_effect = Exception("stats unavailable")

        engine.poll_once()
        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert isinstance(event, MonitorEvent)

    def test_handler_error_does_not_crash(self, config, docker_container_mock):
        container = docker_container_mock
        container.status = "running"
        container.short_id = "abc123"
        container.name = "test-container"

        mock_client = MagicMock()
        mock_client.containers.list.return_value = [container]

        engine = MonitorEngine(config, docker_client=mock_client)
        bad_handler = MagicMock(side_effect=RuntimeError("broken"))
        engine.register_handler(bad_handler)

        engine.poll_once()  # baseline

        container.status = "exited"
        container.attrs = {"State": {"ExitCode": 0}}
        container.stats.side_effect = Exception("stats unavailable")

        engine.poll_once()  # should not raise

    def test_container_filter(self, config, docker_container_mock):
        config.monitor.containers = ["web"]
        container = docker_container_mock
        container.name = "db"
        container.status = "running"

        mock_client = MagicMock()
        mock_client.containers.list.return_value = [container]

        engine = MonitorEngine(config, docker_client=mock_client)
        events = engine.poll_once()
        assert events == []

    def test_container_filter_includes_named(self, config, docker_container_mock):
        config.monitor.containers = ["web"]
        container = docker_container_mock
        container.name = "web"
        container.status = "running"

        mock_client = MagicMock()
        mock_client.containers.list.return_value = [container]

        engine = MonitorEngine(config, docker_client=mock_client)
        engine.poll_once()  # baseline
        assert engine._running is False  # poll_once doesn't start the loop

    def test_no_events_on_same_state(self, config, docker_container_mock):
        container = docker_container_mock
        container.status = "running"
        container.short_id = "abc123"
        container.name = "test-container"

        mock_client = MagicMock()
        mock_client.containers.list.return_value = [container]

        engine = MonitorEngine(config, docker_client=mock_client)
        engine.poll_once()  # baseline
        events = engine.poll_once()
        assert events == []
