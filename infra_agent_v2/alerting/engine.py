"""Alerting engine for Infra Agent v2.

Sends notifications when incidents occur. Supports pluggable handlers:
- LoggerHandler: writes to log (always active by default)
- WebhookHandler: POSTs JSON to a URL

Handlers are evaluated in order; an alert is considered "sent" if at least
one handler succeeds.
"""

from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import requests

from infra_agent_v2.config import Config
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.alerting")

# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    """A single alert notification."""
    alert_id: str
    severity: str
    title: str
    message: str
    container_id: str = ""
    container_name: str = ""
    event_type: str = ""
    correlation_group_id: str = ""
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.alert_id:
            self.alert_id = f"alert-{uuid.uuid4().hex[:8]}"
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "container_id": self.container_id,
            "container_name": self.container_name,
            "event_type": self.event_type,
            "correlation_group_id": self.correlation_group_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

class AlertHandler(ABC):
    """Abstract alert handler."""

    @abstractmethod
    def send(self, alert: Alert) -> bool:
        """Send the alert. Returns True on success."""
        ...

    @abstractmethod
    def matches(self, alert: Alert) -> bool:
        """Return True if this handler should process this alert."""
        ...

@dataclass
class LoggerHandler(AlertHandler):
    """Writes alerts to the log at the appropriate level."""

    def send(self, alert: Alert) -> bool:
        level_map = {
            "critical": logger.critical,
            "warning": logger.warning,
            "info": logger.info,
        }
        log_fn = level_map.get(alert.severity, logger.info)
        log_fn(
            "ALERT [%s]: %s — %s",
            alert.alert_id,
            alert.title,
            alert.message,
        )
        return True

    def matches(self, alert: Alert) -> bool:
        return True

@dataclass
class WebhookHandler(AlertHandler):
    """POSTs alert JSON to a URL."""

    url: str = ""
    headers: Dict[str, str] = field(default_factory=lambda: {"Content-Type": "application/json"})
    timeout: int = 10
    min_severity: str = "warning"

    SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

    def matches(self, alert: Alert) -> bool:
        if not self.url:
            return False
        return self.SEVERITY_ORDER.get(alert.severity, 3) <= self.SEVERITY_ORDER.get(self.min_severity, 3)

    def send(self, alert: Alert) -> bool:
        try:
            resp = requests.post(
                self.url,
                json=alert.to_dict(),
                headers=self.headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            logger.info("Webhook alert sent to %s (status=%d)", self.url, resp.status_code)
            return True
        except Exception as exc:
            logger.error("Failed to send webhook alert to %s: %s", self.url, exc)
            return False

# ---------------------------------------------------------------------------
# AlertEngine
# ---------------------------------------------------------------------------

class AlertEngine:
    """Coordinates alert handlers and dispatches alerts."""

    def __init__(self, config: Config):
        self.config = config
        self._handlers: List[AlertHandler] = [LoggerHandler()]

        # Add webhook handler if configured
        webhook_url = os.environ.get("INFRA_ALERT_WEBHOOK_URL", "")
        min_sev = os.environ.get("INFRA_ALERT_MIN_SEVERITY", "warning")
        if webhook_url:
            self._handlers.append(WebhookHandler(url=webhook_url, min_severity=min_sev))

        self._dispatch_callbacks: List[Callable[[Alert], None]] = []

    def register_handler(self, handler: AlertHandler) -> None:
        """Register an additional alert handler."""
        self._handlers.append(handler)
        logger.info("Registered alert handler: %s", type(handler).__name__)

    def register_dispatch_callback(self, cb: Callable[[Alert], None]) -> None:
        """Register a callback that fires after every alert is dispatched."""
        self._dispatch_callbacks.append(cb)

    def send(self, alert: Alert) -> int:
        """Send an alert through all matching handlers.

        Returns the number of handlers that successfully sent the alert.
        """
        if not alert.severity:
            alert.severity = "info"

        sent = 0
        for handler in self._handlers:
            if not handler.matches(alert):
                continue
            try:
                if handler.send(alert):
                    sent += 1
            except Exception as exc:
                logger.error("Handler %s failed for alert %s: %s",
                             type(handler).__name__, alert.alert_id, exc)

        if sent == 0:
            logger.warning("No handlers matched or succeeded for alert %s", alert.alert_id)

        # Fire dispatch callbacks
        for cb in self._dispatch_callbacks:
            try:
                cb(alert)
            except Exception:
                logger.exception("Dispatch callback failed for alert %s", alert.alert_id)

        return sent

    def send_alert(
        self,
        severity: str,
        title: str,
        message: str,
        container_id: str = "",
        container_name: str = "",
        event_type: str = "",
        correlation_group_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Alert:
        """Convenience: create and send an alert in one call."""
        alert = Alert(
            alert_id="",
            severity=severity,
            title=title,
            message=message,
            container_id=container_id,
            container_name=container_name,
            event_type=event_type,
            correlation_group_id=correlation_group_id,
            timestamp="",
            metadata=metadata or {},
        )
        self.send(alert)
        return alert