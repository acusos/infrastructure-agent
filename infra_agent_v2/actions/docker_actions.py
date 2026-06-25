"""Docker container action primitives for Infra Agent v2.

Wraps the Docker SDK to provide lifecycle operations:
start, stop, restart, kill, logs, inspect, remove, stats, list, is_running.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from infra_agent_v2.config import Config
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.docker_actions")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ActionResult:
    """Result of a Docker action."""
    container_id: str
    container_name: str
    action: str
    success: bool
    details: str = ""

# ---------------------------------------------------------------------------
# Docker Actions
# ---------------------------------------------------------------------------

class DockerActions:
    """Executes container lifecycle actions via the Docker SDK."""

    def __init__(self, config: Config, docker_client=None):
        self.config = config.docker
        self.client = docker_client or self._build_client()

    # -- Lifecycle --

    def start(self, container_id: str, timeout: int = 30) -> ActionResult:
        """Start a stopped container and wait up to *timeout* seconds."""
        try:
            container = self.client.containers.get(container_id)
            container_name = container.name
            container.start()
            if self._wait_for_state(container, "running", timeout=timeout):
                return ActionResult(container_id, container_name, "start", True)
            return ActionResult(container_id, container_name, "start", False,
                               "Container did not reach 'running' state in time")
        except Exception as exc:
            logger.error("Failed to start container %s: %s", container_id, exc)
            return ActionResult(container_id, container_id, "start", False, str(exc))

    def stop(self, container_id: str, timeout: int = 30) -> ActionResult:
        """Stop a running container."""
        try:
            container = self.client.containers.get(container_id)
            container_name = container.name
            container.stop(timeout=timeout)
            return ActionResult(container_id, container_name, "stop", True)
        except Exception as exc:
            logger.error("Failed to stop container %s: %s", container_id, exc)
            return ActionResult(container_id, container_id, "stop", False, str(exc))

    def restart(self, container_id: str, timeout: int = 30) -> ActionResult:
        """Restart a container."""
        try:
            container = self.client.containers.get(container_id)
            container_name = container.name
            container.restart(timeout=timeout)
            if self._wait_for_state(container, "running", timeout=timeout):
                return ActionResult(container_id, container_name, "restart", True)
            return ActionResult(container_id, container_name, "restart", False,
                               "Container did not reach 'running' state after restart")
        except Exception as exc:
            logger.error("Failed to restart container %s: %s", container_id, exc)
            return ActionResult(container_id, container_id, "restart", False, str(exc))

    def kill(self, container_id: str) -> ActionResult:
        """Kill a container immediately."""
        try:
            container = self.client.containers.get(container_id)
            container_name = container.name
            container.kill()
            return ActionResult(container_id, container_name, "kill", True)
        except Exception as exc:
            logger.error("Failed to kill container %s: %s", container_id, exc)
            return ActionResult(container_id, container_id, "kill", False, str(exc))

    # -- Inspection --

    def logs(self, container_id: str, tail: int = 100) -> str:
        """Return the last *tail* lines of container logs."""
        try:
            container = self.client.containers.get(container_id)
            raw = container.logs(tail=tail)
            if isinstance(raw, bytes):
                return raw.decode("utf-8", errors="replace")
            return raw
        except Exception as exc:
            logger.error("Failed to get logs for container %s: %s", container_id, exc)
            return ""

    def inspect(self, container_id: str) -> Dict[str, Any]:
        """Return full inspect JSON for a container."""
        try:
            container = self.client.containers.get(container_id)
            return container.attrs
        except Exception as exc:
            logger.error("Failed to inspect container %s: %s", container_id, exc)
            return {}

    def get_stats(self, container_id: str) -> Dict[str, Any]:
        """Return resource stats (CPU, memory) for a container."""
        try:
            container = self.client.containers.get(container_id)
            return container.stats(stream=False)
        except Exception as exc:
            logger.error("Failed to get stats for container %s: %s", container_id, exc)
            return {}

    # -- List / Query --

    def list_containers(self, all: bool = True) -> List[Dict[str, Any]]:
        """Return a list of container info dicts."""
        try:
            containers = self.client.containers.list(all=all)
            return [
                {
                    "id": c.short_id,
                    "name": c.name,
                    "status": c.status,
                }
                for c in containers
            ]
        except Exception as exc:
            logger.error("Failed to list containers: %s", exc)
            return []

    def is_running(self, container_id: str) -> bool:
        """Return True if the container is currently running."""
        try:
            container = self.client.containers.get(container_id)
            return container.status == "running"
        except Exception:
            return False

    def remove(self, container_id: str) -> ActionResult:
        """Remove a container."""
        try:
            container = self.client.containers.get(container_id)
            container_name = container.name
            container.remove(force=True)
            return ActionResult(container_id, container_name, "remove", True)
        except Exception as exc:
            logger.error("Failed to remove container %s: %s", container_id, exc)
            return ActionResult(container_id, container_id, "remove", False, str(exc))

    # -- Internal --

    @staticmethod
    def _wait_for_state(container, target_status: str, timeout: int) -> bool:
        """Poll a container until it reaches *target_status* or *timeout* elapses."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            container.reload()
            if container.status == target_status:
                return True
            time.sleep(1)
        return False

    @staticmethod
    def _build_client():
        """Build a Docker SDK client from the default socket."""
        from docker import from_env
        return from_env()
