"""Health check engine for Infra Agent v2.

Performs HTTP and TCP health checks against configured endpoints and
emits HealthEvent objects when a check passes or fails.
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import requests

from infra_agent_v2.config import Config
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.health")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class HealthCheckResult:
    """Result of a single health check probe."""
    timestamp: str
    check_name: str
    check_type: str  # "http", "tcp"
    status: str  # "ok", "failure", "error"
    latency_ms: float
    message: str = ""

@dataclass
class HealthEvent:
    """Event emitted when a health check status changes."""
    timestamp: str
    check_name: str
    check_type: str
    old_status: str
    new_status: str
    severity: str  # "info", "warning", "critical"
    message: str = ""

# ---------------------------------------------------------------------------
# Health Checker
# ---------------------------------------------------------------------------

class HealthChecker:
    """Runs HTTP and TCP health checks at configurable intervals."""

    def __init__(
        self,
        config: Config,
        event_handlers: Optional[List[Callable[[HealthEvent], None]]] = None,
        session: Optional[requests.Session] = None,
    ):
        self.config = config.health
        self._event_handlers = event_handlers or []
        self._running = False
        self._session = session or requests.Session()
        self._last_results: Dict[str, str] = {}  # check_name -> last status

    # -- Public API --

    def register_handler(self, handler: Callable[[HealthEvent], None]) -> None:
        """Register a callback to receive HealthEvents."""
        self._event_handlers.append(handler)

    def start(self) -> None:
        """Start the health check loop (runs in current thread)."""
        if self._running:
            logger.warning("Health checker is already running")
            return
        self._running = True
        logger.info("Health checker started (%d endpoints, %d tcp checks)",
                    len(self.config.endpoints), len(self.config.tcp_checks))

        while self._running:
            try:
                self._run_all()
            except Exception as exc:
                logger.exception("Unexpected error in health check loop: %s", exc)
            finally:
                if self._running:
                    self._sleep_next()

    def stop(self) -> None:
        """Stop the health check loop."""
        self._running = False
        logger.info("Health checker stopped")

    def check_once(self) -> List[HealthCheckResult]:
        """Execute one round of all health checks without blocking.
        
        Useful for testing and one-shot checks.
        """
        return self._run_all()

    # -- Private --

    def _run_all(self) -> List[HealthCheckResult]:
        """Execute every configured check and return results."""
        results: List[HealthCheckResult] = []
        for endpoint in self.config.endpoints:
            results.append(self._check_http(endpoint))
        for tcp in self.config.tcp_checks:
            results.append(self._check_tcp(tcp))
        return results

    def _check_http(self, endpoint) -> HealthCheckResult:
        """Probe an HTTP endpoint."""
        start = time.monotonic()
        try:
            resp = self._session.get(endpoint.url, timeout=5)
            latency = (time.monotonic() - start) * 1000
            status = "ok" if resp.status_code < 500 else "failure"
            msg = f"HTTP {resp.status_code}"
            self._maybe_emit_change(endpoint.name, status, "http", msg)
            return HealthCheckResult(
                timestamp=datetime.now(timezone.utc).isoformat(),
                check_name=endpoint.name,
                check_type="http",
                status=status,
                latency_ms=latency,
                message=msg,
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            msg = str(exc)
            status = "error"
            self._maybe_emit_change(endpoint.name, status, "http", msg)
            return HealthCheckResult(
                timestamp=datetime.now(timezone.utc).isoformat(),
                check_name=endpoint.name,
                check_type="http",
                status=status,
                latency_ms=latency,
                message=msg,
            )

    def _check_tcp(self, tcp) -> HealthCheckResult:
        """Probe a TCP endpoint."""
        start = time.monotonic()
        try:
            with socket.create_connection(
                (tcp.host, tcp.port), timeout=5
            ) as sock:
                sock.setblocking(True)
            latency = (time.monotonic() - start) * 1000
            check_name = f"tcp://{tcp.host}:{tcp.port}"
            status = "ok"
            self._maybe_emit_change(check_name, status, "tcp")
            return HealthCheckResult(
                timestamp=datetime.now(timezone.utc).isoformat(),
                check_name=check_name,
                check_type="tcp",
                status=status,
                latency_ms=latency,
            )
        except OSError as exc:
            latency = (time.monotonic() - start) * 1000
            check_name = f"tcp://{tcp.host}:{tcp.port}"
            status = "error"
            self._maybe_emit_change(check_name, status, "tcp", str(exc))
            return HealthCheckResult(
                timestamp=datetime.now(timezone.utc).isoformat(),
                check_name=check_name,
                check_type="tcp",
                status=status,
                latency_ms=latency,
                message=str(exc),
            )

    def _maybe_emit_change(
        self, check_name: str, new_status: str, check_type: str, message: str = ""
    ) -> None:
        """Emit a HealthEvent if the check status has changed."""
        old_status = self._last_results.get(check_name, "unknown")
        self._last_results[check_name] = new_status
        if old_status == new_status:
            return

        severity = "critical" if new_status in ("failure", "error") else "info"
        if old_status != "unknown" and old_status in ("failure", "error") and new_status == "ok":
            severity = "info"

        event = HealthEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            check_name=check_name,
            check_type=check_type,
            old_status=old_status,
            new_status=new_status,
            severity=severity,
            message=message or f"{check_name}: {old_status} -> {new_status}",
        )
        self._emit(event)
        logger.info("Health change: %s", event.message)

    def _emit(self, event: HealthEvent) -> None:
        """Dispatch an event to all registered handlers."""
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Error in health event handler: %s", handler)

    def _sleep_next(self) -> None:
        """Sleep until the next check is due.
        
        Uses the minimum interval across all configured checks.
        """
        intervals = [e.interval for e in self.config.endpoints] + [
            t.interval for t in self.config.tcp_checks
        ]
        if not intervals:
            # No checks configured; sleep a reasonable default
            time.sleep(10)
            return
        next_in = min(intervals)
        deadline = time.monotonic() + next_in
        while self._running and time.monotonic() < deadline:
            time.sleep(1)
