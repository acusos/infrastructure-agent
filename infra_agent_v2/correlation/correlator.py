"""Incident correlation engine for Infra Agent v2.

Groups events that occur within a configurable time window into a single
correlated incident, so the orchestrator can treat related events (e.g., a
container crash + a health-check failure on the same host) as one problem
instead of many.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from infra_agent_v2.config import Config
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.correlation")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CorrelationGroup:
    """A group of related events treated as one incident."""
    group_id: str
    start_time: datetime
    events: List[dict] = field(default_factory=list)
    highest_severity: str = "info"
    containers_involved: List[str] = field(default_factory=list)

    def add_event(self, event: dict) -> None:
        """Add an event to this group, updating severity and containers."""
        self.events.append(event)
        self.highest_severity = self._higher_severity(
            self.highest_severity, event.get("severity", "info")
        )
        container = event.get("container_name", event.get("container_id", "unknown"))
        if container not in self.containers_involved:
            self.containers_involved.append(container)

    @staticmethod
    def _higher_severity(a: str, b: str) -> str:
        order = {"critical": 0, "warning": 1, "info": 2}
        return a if order.get(a, 3) <= order.get(b, 3) else b

    def to_dict(self) -> dict:
        return {
            "group_id": self.group_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self._end_time().isoformat(),
            "event_count": len(self.events),
            "highest_severity": self.highest_severity,
            "containers_involved": self.containers_involved,
            "events": self.events,
        }

    def _end_time(self) -> datetime:
        if not self.events:
            return self.start_time
        timestamps = []
        for ev in self.events:
            ts = ev.get("timestamp", "")
            if ts:
                try:
                    timestamps.append(datetime.fromisoformat(ts))
                except ValueError:
                    pass
        return max(timestamps) if timestamps else self.start_time

# ---------------------------------------------------------------------------
# Correlator
# ---------------------------------------------------------------------------

class IncidentCorrelator:
    """Groups events into correlated incidents based on time windows.

    Two events are correlated if they occur within *correlation_window_seconds*
    of each other, OR if they involve the same container and the window has
    not expired.
    """

    SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

    def __init__(self, config: Config):
        self.config = config.monitor
        self._window = timedelta(seconds=self.config.poll_interval * 30)
        self._groups: Dict[str, CorrelationGroup] = {}
        self._container_groups: Dict[str, str] = {}

    def correlate(self, event: dict) -> CorrelationGroup:
        """Process an event and return the CorrelationGroup it belongs to.

        1. Check if any existing group is still within the time window.
        2. If the event's container is already in a group, join it.
        3. Otherwise, create a new group.
        """
        now = datetime.now(timezone.utc)
        event_time = self._parse_timestamp(event.get("timestamp", "")) or now

        # Try to match by container
        container = event.get("container_name", event.get("container_id", ""))
        container_group_id = self._container_groups.get(container)

        if container_group_id and container_group_id in self._groups:
            group = self._groups[container_group_id]
            if now - group.start_time <= self._window:
                group.add_event(event)
                return group
            # Expired — remove stale mapping
            del self._groups[container_group_id]
            del self._container_groups[container]

        # Try to match by time window (any active group)
        for gid, group in self._groups.items():
            if now - group.start_time <= self._window:
                # Same network / host context — correlate
                group.add_event(event)
                if container and container not in self._container_groups:
                    self._container_groups[container] = gid
                return group

        # No matching group — create a new one
        new_group = CorrelationGroup(
            group_id=uuid.uuid4().hex[:12],
            start_time=now,
        )
        new_group.add_event(event)
        self._groups[new_group.group_id] = new_group
        if container:
            self._container_groups[container] = new_group.group_id
        logger.info("Created new correlation group %s", new_group.group_id)
        return new_group

    def get_active_groups(self) -> List[CorrelationGroup]:
        """Return all groups still within the correlation window."""
        now = datetime.now(timezone.utc)
        active: List[CorrelationGroup] = []
        expired_gids = []
        for gid, group in self._groups.items():
            if now - group.start_time <= self._window:
                active.append(group)
            else:
                expired_gids.append(gid)
        for gid in expired_gids:
            del self._groups[gid]
        return active

    def get_group(self, group_id: str) -> Optional[CorrelationGroup]:
        """Return a specific correlation group by ID."""
        return self._groups.get(group_id)

    def flush_expired(self) -> List[CorrelationGroup]:
        """Remove expired groups and return them for archival."""
        now = datetime.now(timezone.utc)
        expired: List[CorrelationGroup] = []
        gids_to_remove = []
        for gid, group in self._groups.items():
            if now - group.start_time > self._window:
                expired.append(group)
                gids_to_remove.append(gid)
        for gid in gids_to_remove:
            del self._groups[gid]
        # Clean up stale container mappings
        for container, gid in list(self._container_groups.items()):
            if gid not in self._groups:
                del self._container_groups[container]
        return expired

    def reset(self) -> None:
        """Clear all groups and mappings."""
        self._groups.clear()
        self._container_groups.clear()

    @staticmethod
    def _parse_timestamp(ts: str) -> Optional[datetime]:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return None
