"""Recovery engine for Infra Agent v2.

Automatically restarts containers that are crashing or stuck, with configurable
cooldown and max-restart limits. When max_restarts is exceeded, an alert is
emitted instead of continuing to restart.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from infra_agent_v2.config import Config
from infra_agent_v2.actions.docker_actions import DockerActions
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.recovery")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RecoveryAttempt:
    """Record of a single recovery attempt for a container."""
    container_id: str
    timestamp: str
    success: bool
    attempt_number: int

@dataclass
class RecoveryAlert:
    """Alert emitted when max_restarts is exceeded or a restart fails."""
    timestamp: str
    container_id: str
    container_name: str
    reason: str
    attempt_count: int
    max_allowed: int

@dataclass
class RecoveryEvent:
    """Event emitted when a recovery action occurs."""
    timestamp: str
    container_id: str
    container_name: str
    action: str  # "restart_attempt", "restart_success", "restart_failed", "alert"
    attempt_number: int
    success: bool
    message: str = ""

# ---------------------------------------------------------------------------
# Recovery Engine
# ---------------------------------------------------------------------------

class RecoveryEngine:
    """Handles container recovery with cooldown and max-restart limits."""

    def __init__(
        self,
        config: Config,
        docker_actions: Optional[DockerActions] = None,
        event_handlers: Optional[List[Callable[[RecoveryEvent], None]]] = None,
        alert_handlers: Optional[List[Callable[[RecoveryAlert], None]]] = None,
    ):
        self.config = config.recovery
        self.docker = docker_actions or self._build_actions(config)
        self._event_handlers = event_handlers or []
        self._alert_handlers = alert_handlers or []
        self._restart_counts: Dict[str, int] = {}
        self._last_restart_time: Dict[str, float] = {}

    # -- Public API --

    def register_event_handler(self, handler: Callable[[RecoveryEvent], None]) -> None:
        """Register a callback to receive RecoveryEvents."""
        self._event_handlers.append(handler)

    def register_alert_handler(self, handler: Callable[[RecoveryAlert], None]) -> None:
        """Register a callback to receive RecoveryAlerts."""
        self._alert_handlers.append(handler)

    def recover(self, container_id: str, container_name: str = "") -> RecoveryAttempt:
        """Attempt to recover a container by restarting it.

        Returns:
            A RecoveryAttempt with success/failure details.
        """
        attempt = self._get_attempt_count(container_id) + 1
        self._restart_counts[container_id] = attempt

        # Check max restarts
        if attempt > self.config.max_restarts:
            logger.warning(
                "Max restarts (%d) exceeded for container %s; alerting",
                self.config.max_restarts,
                container_id,
            )
            self._emit_alert(container_id, container_name, attempt)
            return RecoveryAttempt(container_id, self._now(), False, attempt)

        # Check cooldown
        last_time = self._last_restart_time.get(container_id, 0)
        elapsed = time.monotonic() - last_time
        if elapsed < self.config.restart_cooldown:
            logger.info(
                "Cooldown active for %s (%.1fs remaining); skipping restart",
                container_id,
                self.config.restart_cooldown - elapsed,
            )
            self._emit_event(container_id, container_name, attempt, False,
                            "restart_failed", f"Cooldown active ({elapsed:.0f}s elapsed)")
            return RecoveryAttempt(container_id, self._now(), False, attempt)

        # Attempt restart
        self._last_restart_time[container_id] = time.monotonic()
        logger.info("Restarting container %s (attempt %d/%d)",
                     container_id, attempt, self.config.max_restarts)

        result = self.docker.restart(container_id, timeout=self.config.restart_timeout)
        success = result.success

        self._emit_event(container_id, container_name, attempt, success,
                         "restart_success" if success else "restart_failed",
                         result.details)

        return RecoveryAttempt(container_id, self._now(), success, attempt)

    def reset(self, container_id: str) -> None:
        """Reset restart tracking for a container (e.g., after successful recovery)."""
        self._restart_counts.pop(container_id, None)
        self._last_restart_time.pop(container_id, None)
        logger.info("Reset recovery tracking for container %s", container_id)

    def get_restart_count(self, container_id: str) -> int:
        """Return the number of restart attempts for a container."""
        return self._restart_counts.get(container_id, 0)

    def is_in_cooldown(self, container_id: str) -> bool:
        """Return True if the container is currently in cooldown."""
        last = self._last_restart_time.get(container_id, 0)
        return (time.monotonic() - last) < self.config.restart_cooldown

    # -- Internal --

    @staticmethod
    def _build_actions(config: Config) -> DockerActions:
        return DockerActions(config)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _get_attempt_count(self, container_id: str) -> int:
        return self._restart_counts.get(container_id, 0)

    def _emit_event(
        self, container_id: str, container_name: str, attempt: int,
        success: bool, action: str, message: str = ""
    ) -> None:
        """Emit a RecoveryEvent to all handlers."""
        event = RecoveryEvent(
            timestamp=self._now(),
            container_id=container_id,
            container_name=container_name or container_id,
            action=action,
            attempt_number=attempt,
            success=success,
            message=message,
        )
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Error in recovery event handler: %s", handler)

    def _emit_alert(self, container_id: str, container_name: str,
                     attempt: int) -> None:
        """Emit a RecoveryAlert and notify alert handlers."""
        alert = RecoveryAlert(
            timestamp=self._now(),
            container_id=container_id,
            container_name=container_name or container_id,
            reason=f"Max restarts ({self.config.max_restarts}) exceeded",
            attempt_count=attempt,
            max_allowed=self.config.max_restarts,
        )
        logger.critical("RECOVERY ALERT: %s", alert.reason)
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception:
                logger.exception("Error in recovery alert handler: %s", handler)
