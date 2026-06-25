"""Main entry point for Infra Agent v2.

Wires together all subsystems into a single orchestrator:
  MonitorEngine  ──┐
                   ├──→ IncidentAnalyzer ──→ QdrantMemoryStore
  HealthChecker  ──┘
                   └──→ RecoveryEngine (on critical)
                   └──→ ReportGenerator (periodic)
"""

from __future__ import annotations

import signal
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from infra_agent_v2.actions.docker_actions import DockerActions
from infra_agent_v2.alerting.engine import Alert, AlertEngine
from infra_agent_v2.config import Config, load_config
from infra_agent_v2.config_watcher.watcher import ConfigWatcher
from infra_agent_v2.correlation.correlator import IncidentCorrelator
from infra_agent_v2.dashboard.server import DashboardServer
from infra_agent_v2.health.checker import HealthChecker, HealthEvent
from infra_agent_v2.llm.analyzer import IncidentAnalyzer
from infra_agent_v2.memory.qdrant_store import QdrantMemoryStore
from infra_agent_v2.monitor.engine import MonitorEngine, MonitorEvent
from infra_agent_v2.recovery.engine import RecoveryEngine, RecoveryEvent, RecoveryAlert
from infra_agent_v2.report.generator import ReportGenerator
from infra_agent_v2.shutdown.handler import ShutdownHandler
from infra_agent_v2.state.persistence import StateManager
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.main")

# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------

@dataclass
class AgentState:
    running: bool = False
    monitor_events: int = 0
    health_events: int = 0
    recovery_attempts: int = 0
    reports_generated: int = 0
    correlation_groups: int = 0
    alerts_sent: int = 0
    config_reloads: int = 0
    last_config_reload: str = ""
    last_report_time: str = ""
    shutdown_reason: str = ""

# ---------------------------------------------------------------------------
# InfraAgent
# ---------------------------------------------------------------------------

class InfraAgent:
    """Orchestrator that wires all subsystems together."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or load_config()
        self.state = AgentState()

        # Core subsystems
        self.docker = DockerActions(self.config)
        self.monitor = MonitorEngine(self.config, docker_client=self.docker.client)
        self.health = HealthChecker(self.config)
        self.analyzer = IncidentAnalyzer(self.config)
        self.recovery = RecoveryEngine(self.config, docker_actions=self.docker)
        self.reporter = ReportGenerator(self.config)
        self.correlator = IncidentCorrelator(self.config)
        self.alerter = AlertEngine(self.config)
        self.persistence = StateManager(self.config)
        self.shutdown_handler = ShutdownHandler(
            on_state_save=self._save_state,
            on_stop=self.stop,
        )

        # Dashboard — built after all subsystems so it can reference them
        self.dashboard: Optional[DashboardServer] = None

        # Memory — may fail if Qdrant is unavailable
        self.memory: Optional[QdrantMemoryStore] = None
        try:
            self.memory = QdrantMemoryStore(self.config)
            self.memory.connect()
            logger.info("Connected to Qdrant memory store")
        except Exception:
            logger.warning("Qdrant memory store unavailable; continuing without persistence")

        # Wire event handlers
        self._wire_handlers()

        # Wire alerter dispatch callback to track count
        self.alerter.register_dispatch_callback(self._on_alert_dispatched)

        # Build dashboard last so it has access to all subsystems
        self.dashboard = DashboardServer(self)

    # -- Public API --

    def start(self) -> None:
        """Start all subsystems in background threads."""
        if self.state.running:
            logger.warning("Agent is already running")
            return

        self.state.running = True
        logger.info("Infra Agent v2 starting...")

        self._start_monitor()
        self._start_health()
        self._start_dashboard()
        self._start_report_loop()

        # Register shutdown handler for signals
        self.shutdown_handler.register()

        logger.info("Infra Agent v2 started (pid=%d)", threading.get_ident())

    def stop(self) -> None:
        """Stop all subsystems and clean up."""
        self.state.running = False
        logger.info("Infra Agent v2 stopping...")
        self.monitor.stop()
        self.health.stop()
        logger.info("Infra Agent v2 stopped")

    def _save_state(self) -> None:
        """Persist current runtime state to disk."""
        try:
            self.persistence.update_state(self)
            self.persistence.save()
        except Exception:
            logger.exception("Failed to save state during shutdown")

    def poll_once(self) -> dict:
        """Run one round of monitoring and health checks without blocking.

        Returns:
            A summary dict with event counts and recovery actions taken.
        """
        result: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "monitor_events": 0,
            "health_events": 0,
            "recovery_actions": 0,
            "incidents": [],
        }

        # Monitor
        events = self.monitor.poll_once()
        for evt in events:
            self._handle_monitor_event(evt)
        result["monitor_events"] = len(events)

        # Health
        health_results = self.health.check_once()
        result["health_events"] = len(health_results)

        # Collect incidents from memory for the summary
        if self.memory:
            try:
                recent = self.memory.get_all()
                result["incidents"] = [inc.to_payload() for inc in recent[-10:]]
            except Exception:
                pass

        return result

    # -- Event wiring --

    def _wire_handlers(self) -> None:
        """Connect subsystem event handlers."""
        self.monitor.register_handler(self._handle_monitor_event)
        self.health.register_handler(self._handle_health_event)
        self.recovery.register_event_handler(self._handle_recovery_event)
        self.recovery.register_alert_handler(self._handle_recovery_alert)

    def _on_alert_dispatched(self, alert: Alert) -> None:
        """Callback when an alert is dispatched; increment counter."""
        self.state.alerts_sent += 1

    # -- Event handlers --

    def _handle_monitor_event(self, event: MonitorEvent) -> None:
        """Handle a MonitorEvent: correlate → analyze → recover if critical."""
        self.state.monitor_events += 1
        logger.info("Monitor event: %s [%s] %s", event.event_type, event.severity, event.message)

        # Correlate with other events
        event_dict = {
            "timestamp": event.timestamp,
            "container_id": event.container_id,
            "container_name": event.container_name,
            "event_type": event.event_type,
            "severity": event.severity,
            "message": event.message,
        }
        group = self.correlator.correlate(event_dict)
        self.state.correlation_groups = len(self.correlator.get_active_groups())

        # Analyze via LLM
        self.analyzer.analyze(
            event_type=event.event_type,
            container_name=event.container_name,
            message=event.message,
            container_id=event.container_id,
        )

        # If critical, attempt recovery
        if event.severity == "critical" and event.event_type in ("crash", "state_change"):
            self._attempt_recovery(event.container_id, event.container_name)

    def _handle_health_event(self, event: HealthEvent) -> None:
        """Handle a HealthEvent: correlate → analyze the check failure."""
        self.state.health_events += 1
        logger.info("Health event: %s [%s] %s", event.check_name, event.severity, event.message)

        # Correlate with other events
        event_dict = {
            "timestamp": event.timestamp,
            "container_id": "",
            "container_name": event.check_name,
            "event_type": "health_failure",
            "severity": event.severity,
            "message": f"{event.check_name} is {event.new_status}: {event.message}",
        }
        self.correlator.correlate(event_dict)
        self.state.correlation_groups = len(self.correlator.get_active_groups())

        if event.new_status in ("failure", "error"):
            self.analyzer.analyze(
                event_type="health_failure",
                container_name=event.check_name,
                message=f"{event.check_name} is {event.new_status}: {event.message}",
            )

    def _handle_recovery_event(self, event: RecoveryEvent) -> None:
        """Log recovery events."""
        self.state.recovery_attempts += 1
        logger.info("Recovery event: %s [%s] attempt=%d success=%s",
                     event.action, event.container_name, event.attempt_number, event.success)

    def _handle_recovery_alert(self, alert: RecoveryAlert) -> None:
        """Log and report recovery alerts."""
        logger.critical("RECOVERY ALERT: %s on %s — %s (attempt %d/%d)",
                        alert.container_name, alert.container_id,
                        alert.reason, alert.attempt_count, alert.max_allowed)

        # Generate an alert report
        try:
            report = self.reporter.generate_text(
                incidents=[{
                    "timestamp": alert.timestamp,
                    "container_id": alert.container_id,
                    "container_name": alert.container_name,
                    "event_type": "recovery_alert",
                    "severity": "critical",
                    "message": alert.reason,
                    "llm_analysis": f"Container {alert.container_name} exceeded max restarts",
                }],
                title=f"Recovery Alert: {alert.container_name}",
            )
            logger.warning("ALERT REPORT:\n%s", report)
        except Exception:
            logger.exception("Failed to generate alert report")

    # -- Recovery --

    def _attempt_recovery(self, container_id: str, container_name: str) -> None:
        """Attempt to recover a container."""
        logger.info("Attempting recovery for %s", container_name)
        attempt = self.recovery.recover(container_id, container_name)
        if attempt.success:
            logger.info("Recovery succeeded for %s (attempt %d)", container_name, attempt.attempt_number)
        else:
            logger.warning("Recovery failed for %s (attempt %d)", container_name, attempt.attempt_number)

    # -- Background threads --

    def _start_monitor(self) -> None:
        """Start the monitor engine in a background thread."""
        t = threading.Thread(target=self.monitor.start, daemon=True, name="monitor")
        t.start()

    def _start_health(self) -> None:
        """Start the health checker in a background thread."""
        t = threading.Thread(target=self.health.start, daemon=True, name="health")
        t.start()

    def _start_dashboard(self) -> None:
        """Start the HTTP dashboard server."""
        if self.dashboard is None:
            logger.warning("Dashboard server not initialized; skipping start")
            return
        host = self.config.dashboard.host
        port = self.config.dashboard.port
        self.dashboard.start(host=host, port=port)
        logger.info("Dashboard started at %s:%d", host, port)

    def _start_report_loop(self) -> None:
        """Periodically generate summary reports."""
        def _loop():
            while self.state.running:
                try:
                    self._generate_periodic_report()
                except Exception:
                    logger.exception("Error in report loop")
                time.sleep(self.config.monitor.poll_interval * 60)  # every ~N minutes
        t = threading.Thread(target=_loop, daemon=True, name="reporter")
        t.start()

    def _generate_periodic_report(self) -> None:
        """Generate a summary report of recent incidents."""
        incidents: List[dict] = []
        if self.memory:
            try:
                all_incidents = self.memory.get_all()
                incidents = [inc.to_payload() for inc in all_incidents[-50:]]
            except Exception:
                logger.warning("Failed to fetch incidents for report")

        report = self.reporter.generate_text(incidents, title="Periodic Incident Report")
        logger.info("PERIODIC REPORT:\n%s", report)
        self.state.reports_generated += 1
        self.state.last_report_time = datetime.now(timezone.utc).isoformat()

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(config_path: Optional[str] = None) -> None:
    """Start the Infra Agent with optional config path.

    Args:
        config_path: Path to YAML config file. If None, uses defaults.
    """
    agent = InfraAgent(load_config(config_path))
    try:
        agent.start()
        # Keep running until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        agent.shutdown_handler.shutdown(reason="graceful")
        agent.shutdown_handler.unregister()

def main() -> None:
    run()

if __name__ == "__main__":
    main()
