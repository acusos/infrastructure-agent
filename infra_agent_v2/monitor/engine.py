"""Docker container monitoring engine for Infra Agent v2."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from docker.errors import DockerException

from infra_agent_v2.config import Config
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.monitor")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ContainerState:
    """Snapshot of a container's state at a point in time."""
    name: str
    id: str
    status: str  # "running", "exited", "created", etc.
    exit_code: Optional[int] = None
    cpu_percent: float = 0.0
    memory_usage_bytes: int = 0
    memory_limit_bytes: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class MonitorEvent:
    """Event emitted by the monitor when a state change is detected."""
    timestamp: str
    container_id: str
    container_name: str
    event_type: str  # "state_change", "threshold_breach", "crash"
    severity: str = "info"  # "info", "warning", "critical"
    message: str = ""
    old_state: Optional[ContainerState] = None
    new_state: Optional[ContainerState] = None


# ---------------------------------------------------------------------------
# Monitor Engine
# ---------------------------------------------------------------------------

class MonitorEngine:
    """Polls Docker daemon for container state changes and resource usage."""

    def __init__(
        self,
        config: Config,
        docker_client=None,
        event_handlers: Optional[List[Callable[[MonitorEvent], None]]] = None,
    ):
        self.config = config.monitor
        self.docker_client = docker_client
        self._event_handlers = event_handlers or []
        self._running = False
        self._container_states: Dict[str, ContainerState] = {}

    # -- Public API --

    def register_handler(self, handler: Callable[[MonitorEvent], None]) -> None:
        """Register a callback to receive MonitorEvents."""
        self._event_handlers.append(handler)

    def start(self) -> None:
        """Start the monitoring loop (runs in current thread)."""
        if self._running:
            logger.warning("Monitor engine is already running")
            return
        self._running = True
        logger.info("Monitor engine started (poll_interval=%ds)", self.config.poll_interval)

        while self._running:
            try:
                self._poll()
            except DockerException as exc:
                logger.error("Docker error during poll: %s", exc)
            except Exception as exc:
                logger.exception("Unexpected error in monitor loop: %s", exc)
            finally:
                if self._running:
                    time.sleep(self.config.poll_interval)

    def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        logger.info("Monitor engine stopped")

    def poll_once(self) -> List[MonitorEvent]:
        """Execute a single poll cycle and return emitted events.

        Useful for testing and one-shot monitoring.
        """
        return self._poll()

    # -- Private --

    def _poll(self) -> List[MonitorEvent]:
        """Run one poll cycle. Returns list of MonitorEvents."""
        events: List[MonitorEvent] = []

        if self.docker_client is None:
            logger.warning("No docker client configured — skipping poll")
            return events

        try:
            containers = self.docker_client.containers.list(all=True)
        except Exception:
            logger.exception("Failed to list containers")
            return events

        for container in containers:
            name = container.name
            cid = container.short_id
            status = container.status

            # Filter by config whitelist if set
            if self.config.containers and name not in self.config.containers:
                continue

            new_state = self._build_state(container, name, cid, status)
            old_state = self._container_states.get(cid)

            if old_state and old_state.status != status:
                evt = self._state_change_event(old_state, new_state)
                events.append(evt)
                self._emit(evt)
                logger.info("State change for %s: %s -> %s",
                            name, old_state.status, status)

            if old_state and status == "exited" and new_state.exit_code and new_state.exit_code != 0:
                evt = MonitorEvent(
                    timestamp=new_state.timestamp,
                    container_id=cid,
                    container_name=name,
                    event_type="crash",
                    severity="critical",
                    message=f"Container {name} exited with code {new_state.exit_code}",
                    old_state=old_state,
                    new_state=new_state,
                )
                events.append(evt)
                self._emit(evt)
                logger.critical(evt.message)

            # Resource threshold check
            if status == "running":
                cpu_threshold = self.config.resource_thresholds.cpu
                mem_threshold = self.config.resource_thresholds.memory

                if new_state.cpu_percent > cpu_threshold:
                    evt = MonitorEvent(
                        timestamp=new_state.timestamp,
                        container_id=cid,
                        container_name=name,
                        event_type="threshold_breach",
                        severity="warning",
                        message=f"Container {name} CPU at {new_state.cpu_percent:.1f}% (threshold {cpu_threshold}%)",
                        new_state=new_state,
                    )
                    events.append(evt)
                    self._emit(evt)

                mem_pct = (new_state.memory_usage_bytes / new_state.memory_limit_bytes * 100
                          if new_state.memory_limit_bytes else 0)
                if mem_pct > mem_threshold:
                    evt = MonitorEvent(
                        timestamp=new_state.timestamp,
                        container_id=cid,
                        container_name=name,
                        event_type="threshold_breach",
                        severity="warning",
                        message=f"Container {name} memory at {mem_pct:.1f}% (threshold {mem_threshold}%)",
                        new_state=new_state,
                    )
                    events.append(evt)
                    self._emit(evt)

            self._container_states[cid] = new_state

        return events

    def _build_state(self, container, name: str, cid: str, status: str) -> ContainerState:
        """Build a ContainerState snapshot from a Docker container object."""
        attrs = container.attrs.get("State", {})
        exit_code = attrs.get("ExitCode") if status == "exited" else None

        # Resource stats (best-effort)
        cpu_percent = 0.0
        mem_usage = 0
        mem_limit = 0
        try:
            stats = container.stats(stream=False)
            cpu_delta = stats.get("cpu_stats", {}).get("cpu_usage", {}).get(
                "total_usage"
            ) - stats.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
            sys_delta = stats.get("cpu_stats", {}).get("system_cpu_usage", 0) - stats.get(
                "precpu_stats", {}
            ).get("system_cpu_usage", 0)
            if sys_delta:
                cpu_percent = (cpu_delta / sys_delta) * 100
            mem_stats = stats.get("memory_stats", {})
            mem_usage = mem_stats.get("usage", 0)
            mem_limit = mem_stats.get("limit", 0)
        except Exception:
            # Stats may not be available for stopped containers
            pass

        return ContainerState(
            name=name,
            id=cid,
            status=status,
            exit_code=exit_code,
            cpu_percent=cpu_percent,
            memory_usage_bytes=mem_usage,
            memory_limit_bytes=mem_limit,
        )

    @staticmethod
    def _state_change_event(old: ContainerState, new: ContainerState) -> MonitorEvent:
        severity = "critical" if new.status == "exited" and new.exit_code != 0 else "info"
        return MonitorEvent(
            timestamp=new.timestamp,
            container_id=new.id,
            container_name=new.name,
            event_type="state_change",
            severity=severity,
            message=f"Container {new.name} changed from {old.status} to {new.status}",
            old_state=old,
            new_state=new,
        )

    def _emit(self, event: MonitorEvent) -> None:
        """Dispatch an event to all registered handlers."""
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Error in event handler: %s", handler)
