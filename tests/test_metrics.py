"""Tests for metrics/collector.py."""

import time
from unittest.mock import MagicMock, patch

import pytest

from infra_agent_v2.config import Config
from infra_agent_v2.metrics.collector import MetricsCollector

@pytest.fixture
def config():
    """Return a default Config instance."""
    return Config()

@pytest.fixture
def collector(config):
    """Return a MetricsCollector instance."""
    return MetricsCollector(config)

class TestMetricsCollector:
    """MetricsCollector behavior."""

    def test_start(self, collector):
        collector.start()
        assert collector.is_running

    def test_stop(self, collector):
        collector.start()
        collector.on_stop()
        assert not collector.is_running

    def test_uptime_seconds(self, collector):
        collector.start()
        assert collector.uptime_seconds >= 0

    def test_uptime_seconds_before_start(self, collector):
        assert collector.uptime_seconds == 0.0

    def test_observe_monitor_event(self, collector):
        collector.observe_monitor_event("crash", "critical")
        # Counter increments successfully without error

    def test_observe_health_event(self, collector):
        collector.observe_health_event("db-tcp", "success")
        collector.observe_health_event("db-tcp", "failure")
        # Gauges set without error

    def test_observe_recovery_attempt(self, collector):
        collector.observe_recovery_attempt("web", True)
        collector.observe_recovery_attempt("web", False)

    def test_observe_recovery_alert(self, collector):
        collector.observe_recovery_alert("web")

    def test_observe_alert_sent(self, collector):
        collector.observe_alert_sent()

    def test_observe_config_reload(self, collector):
        collector.observe_config_reload()

    def test_observe_report_generated(self, collector):
        collector.observe_report_generated()

    def test_set_correlation_groups(self, collector):
        collector.set_correlation_groups(5)
        # Gauge set without error

    def test_observe_incident_latency(self, collector):
        collector.observe_incident_latency(0.5)
        # Histogram observed without error

    def test_generate_latest(self, collector):
        collector.start()
        collector.observe_monitor_event("crash", "critical")
        collector.observe_health_event("db-tcp", "success")
        collector.observe_recovery_attempt("web", True)
        collector.observe_alert_sent()
        collector.observe_config_reload()
        collector.observe_report_generated()
        collector.set_correlation_groups(3)
        collector.update_uptime()

        metrics = collector.generate_latest()
        assert b"infra_monitor_events_total" in metrics
        assert b"infra_health_events_total" in metrics
        assert b"infra_recovery_attempts_total" in metrics
        assert b"infra_alerts_sent_total" in metrics
        assert b"infra_config_reloads_total" in metrics
        assert b"infra_reports_generated_total" in metrics
        assert b"infra_correlation_groups" in metrics
        assert b"infra_uptime_seconds" in metrics
        assert b"infra_health_check_result" in metrics
