"""Tests for correlation/correlator.py."""

from datetime import datetime, timezone

import pytest

from infra_agent_v2.config import Config
from infra_agent_v2.correlation.correlator import CorrelationGroup, IncidentCorrelator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _event(container_name: str, severity: str, timestamp: str, event_type: str = "state_change"):
    return {
        "container_name": container_name,
        "container_id": f"cid-{container_name}",
        "severity": severity,
        "timestamp": timestamp,
        "event_type": event_type,
    }

@pytest.fixture
def correlator(config):
    """Return an IncidentCorrelator with a configurable window."""
    return IncidentCorrelator(config)

# ---------------------------------------------------------------------------
# CorrelationGroup
# ---------------------------------------------------------------------------

class TestCorrelationGroup:
    """CorrelationGroup dataclass behavior."""

    def test_create_group(self):
        group = CorrelationGroup(group_id="abc", start_time=datetime.now(timezone.utc))
        assert group.group_id == "abc"
        assert len(group.events) == 0

    def test_add_event(self):
        group = CorrelationGroup(group_id="abc", start_time=datetime.now(timezone.utc))
        group.add_event(_event("web", "warning", "2026-01-01T00:00:00+00:00"))
        assert len(group.events) == 1
        assert group.highest_severity == "warning"

    def test_highest_severity_updates(self):
        group = CorrelationGroup(group_id="abc", start_time=datetime.now(timezone.utc))
        group.add_event(_event("web", "info", "2026-01-01T00:00:00+00:00"))
        group.add_event(_event("db", "critical", "2026-01-01T00:00:01+00:00"))
        assert group.highest_severity == "critical"

    def test_containers_involved_unique(self):
        group = CorrelationGroup(group_id="abc", start_time=datetime.now(timezone.utc))
        group.add_event(_event("web", "warning", "2026-01-01T00:00:00+00:00"))
        group.add_event(_event("web", "warning", "2026-01-01T00:00:01+00:00"))
        assert group.containers_involved == ["web"]

    def test_to_dict(self):
        group = CorrelationGroup(group_id="abc", start_time=datetime.now(timezone.utc))
        group.add_event(_event("web", "warning", "2026-01-01T00:00:00+00:00"))
        d = group.to_dict()
        assert d["group_id"] == "abc"
        assert d["event_count"] == 1
        assert "start_time" in d
        assert "end_time" in d

    def test_severity_order_critical_over_info(self):
        result = CorrelationGroup._higher_severity("info", "critical")
        assert result == "critical"

    def test_severity_order_warning_over_info(self):
        result = CorrelationGroup._higher_severity("warning", "info")
        assert result == "warning"

# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------

class TestIncidentCorrelator:
    """Full correlation pipeline."""

    def test_first_event_creates_group(self, correlator):
        now = datetime.now(timezone.utc)
        event = _event("web", "warning", now.isoformat())
        group = correlator.correlate(event)
        assert len(group.events) == 1
        assert group.containers_involved == ["web"]

    def test_same_container_within_window_correlates(self, correlator):
        now = datetime.now(timezone.utc)
        event1 = _event("web", "info", now.isoformat())
        event2 = _event("web", "warning", now.isoformat())
        g1 = correlator.correlate(event1)
        g2 = correlator.correlate(event2)
        assert g1.group_id == g2.group_id
        assert len(g1.events) == 2

    def test_different_container_within_window_correlates(self, correlator):
        now = datetime.now(timezone.utc)
        event1 = _event("web", "info", now.isoformat())
        event2 = _event("db", "warning", now.isoformat())
        g1 = correlator.correlate(event1)
        g2 = correlator.correlate(event2)
        assert g1.group_id == g2.group_id

    def test_get_active_groups(self, correlator):
        now = datetime.now(timezone.utc)
        correlator.correlate(_event("web", "warning", now.isoformat()))
        active = correlator.get_active_groups()
        assert len(active) == 1

    def test_get_group_by_id(self, correlator):
        now = datetime.now(timezone.utc)
        g = correlator.correlate(_event("web", "warning", now.isoformat()))
        found = correlator.get_group(g.group_id)
        assert found is not None
        assert found.group_id == g.group_id

    def test_get_group_not_found(self, correlator):
        found = correlator.get_group("nonexistent")
        assert found is None

    def test_flush_expired(self, correlator):
        # Manually set an old start time to simulate expiration
        group = correlator.correlate(_event("web", "warning", "2026-01-01T00:00:00+00:00"))
        group.start_time = datetime.now(timezone.utc).replace(year=2020)  # very old
        expired = correlator.flush_expired()
        assert len(expired) == 1
        assert expired[0].group_id == group.group_id

    def test_reset_clears_everything(self, correlator):
        now = datetime.now(timezone.utc)
        correlator.correlate(_event("web", "warning", now.isoformat()))
        correlator.reset()
        assert len(correlator.get_active_groups()) == 0
        assert correlator._groups == {}

    def test_correlator_creates_groups_for_unrelated_events(self, correlator):
        now = datetime.now(timezone.utc)
        event1 = _event("web", "info", now.isoformat())
        event2 = _event("db", "info", now.isoformat())
        g1 = correlator.correlate(event1)
        g2 = correlator.correlate(event2)
        # Should be in the same group since they're within the window
        assert g1.group_id == g2.group_id

    def test_correlator_highest_severity(self, correlator):
        now = datetime.now(timezone.utc)
        correlator.correlate(_event("web", "info", now.isoformat()))
        correlator.correlate(_event("db", "critical", now.isoformat()))
        active = correlator.get_active_groups()
        assert active[0].highest_severity == "critical"
