"""Prometheus metrics collector for Infra Agent v2.

Exposes standard Prometheus metrics via a FastAPI endpoint.
"""

from __future__ import annotations

import time
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram, generate_latest

from infra_agent_v2.config import Config
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.metrics")

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

INFRA_MONITOR_EVENTS = Counter(
    "infra_monitor_events_total",
    "Total monitor events observed",
    ["event_type", "severity"],
)

INFRA_HEALTH_EVENTS = Counter(
    "infra_health_events_total",
    "Total health check events",
    ["check_name", "status"],
)

INFRA_HEALTH_CHECK_RESULT = Gauge(
    "infra_health_check_result",
    "Health check result (1=success, 0=failure)",
    ["check_name"],
)

INFRA_RECOVERY_ATTEMPTS = Counter(
    "infra_recovery_attempts_total",
    "Total recovery attempts",
    ["container_name", "success"],
)

INFRA_RECOVERY_ALERTS = Counter(
    "infra_recovery_alerts_total",
    "Total recovery alerts (max restarts exceeded)",
    ["container_name"],
)

INFRA_ALERTS_SENT = Counter(
    "infra_alerts_sent_total",
    "Total alerts dispatched",
)

INFRA_CONFIG_RELOADS = Counter(
    "infra_config_reloads_total",
    "Total configuration reloads",
)

INFRA_REPORTS_GENERATED = Counter(
    "infra_reports_generated_total",
    "Total periodic reports generated",
)

INFRA_CORRELATION_GROUPS = Gauge(
    "infra_correlation_groups",
    "Current number of active correlation groups",
)

INFRA_UPTIME_SECONDS = Gauge(
    "infra_uptime_seconds",
    "Agent uptime in seconds",
)

INFRA_INCIDENT_LATENCY = Histogram(
    "infra_incident_latency_seconds",
    "Latency to process an incident",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class MetricsCollector:
    """Collects and exposes Prometheus metrics for InfraAgent."""

    def __init__(self, config: Config):
        self.config = config
        self._start_time: Optional[float] = None

    def start(self) -> None:
        """Record agent start time."""
        self._start_time = time.time()
        logger.info("Metrics collector started")

    @property
    def is_running(self) -> bool:
        return self._start_time is not None

    def on_start(self) -> None:
        """Called when the agent starts."""
        self._start_time = time.time()

    def on_stop(self) -> None:
        """Called when the agent stops."""
        self._start_time = None

    # -- Counters --

    def observe_monitor_event(self, event_type: str, severity: str) -> None:
        INFRA_MONITOR_EVENTS.labels(event_type=event_type, severity=severity).inc()

    def observe_health_event(self, check_name: str, status: str) -> None:
        INFRA_HEALTH_EVENTS.labels(check_name=check_name, status=status).inc()
        INFRA_HEALTH_CHECK_RESULT.labels(check_name=check_name).set(1 if status == "success" else 0)

    def observe_recovery_attempt(self, container_name: str, success: bool) -> None:
        INFRA_RECOVERY_ATTEMPTS.labels(
            container_name=container_name, success=str(success).lower(),
        ).inc()

    def observe_recovery_alert(self, container_name: str) -> None:
        INFRA_RECOVERY_ALERTS.labels(container_name=container_name).inc()

    def observe_alert_sent(self) -> None:
        INFRA_ALERTS_SENT.inc()

    def observe_config_reload(self) -> None:
        INFRA_CONFIG_RELOADS.inc()

    def observe_report_generated(self) -> None:
        INFRA_REPORTS_GENERATED.inc()

    # -- Gauges --

    def set_correlation_groups(self, count: int) -> None:
        INFRA_CORRELATION_GROUPS.set(count)

    # -- Latency --

    def observe_incident_latency(self, latency: float) -> None:
        INFRA_INCIDENT_LATENCY.observe(latency)

    # -- Uptime --

    @property
    def uptime_seconds(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    def update_uptime(self) -> None:
        INFRA_UPTIME_SECONDS.set(self.uptime_seconds)

    # -- Metrics generation --

    def generate_latest(self) -> bytes:
        """Return the latest Prometheus metrics in exposition format."""
        return generate_latest()
