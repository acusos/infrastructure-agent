"""Tests for state persistence engine."""

import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from infra_agent_v2.config import Config
from infra_agent_v2.state.persistence import (
    AlertSnapshot,
    CorrelationSnapshot,
    PersistedState,
    RecoverySnapshot,
    StateManager,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def state_dir():
    """Temporary directory for state files."""
    with tempfile.TemporaryDirectory() as d:
        yield d

@pytest.fixture
def state_manager(config, state_dir):
    """Return a StateManager using the temp directory."""
    return StateManager(config, state_dir=state_dir)

# ---------------------------------------------------------------------------
# State models
# ---------------------------------------------------------------------------

class TestStateModels:
    """Dataclass models."""

    def test_correlation_snapshot(self):
        snap = CorrelationSnapshot(
            group_id="g1",
            start_time="2026-01-01T00:00:00+00:00",
            events=[{"container": "web"}],
            highest_severity="critical",
            containers_involved=["web"],
        )
        assert snap.group_id == "g1"
        assert snap.highest_severity == "critical"

    def test_recovery_snapshot(self):
        snap = RecoverySnapshot(container_id="c1", last_restart_time=1234.5, restart_count=2)
        assert snap.restart_count == 2

    def test_alert_snapshot(self):
        snap = AlertSnapshot(alert_id="a1", severity="critical", title="Crash", timestamp="2026-01-01T00:00:00+00:00")
        assert snap.severity == "critical"

    def test_persisted_state_auto_uuid(self):
        state = PersistedState()
        assert state.agent_uuid

    def test_persisted_state_auto_timestamp(self):
        state = PersistedState()
        assert state.saved_at

# ---------------------------------------------------------------------------
# StateManager
# ---------------------------------------------------------------------------

class TestStateManager:
    """Persistence and restore."""

    def test_load_fresh_state(self, state_manager, state_dir):
        """No state file exists → returns fresh state."""
        state = state_manager.load()
        assert isinstance(state, PersistedState)
        assert state.version == 1

    def test_save_and_load_round_trip(self, state_manager, state_dir):
        """Save then load → state is restored."""
        # Load fresh state
        state = state_manager.load()
        state.monitor_events = 42
        state.alerts_sent = 7
        state.alert_history.append(AlertSnapshot(
            alert_id="a1",
            severity="critical",
            title="Test",
            timestamp="2026-01-01T00:00:00+00:00",
        ))
        state_manager._state = state

        # Save
        state_manager.save()

        # Reload
        loaded = state_manager.load()
        assert loaded.monitor_events == 42
        assert loaded.alerts_sent == 7
        assert len(loaded.alert_history) == 1

    def test_save_creates_directory(self, state_manager):
        """save() creates the directory if it doesn't exist."""
        state_manager.load()
        state_manager.save()
        assert state_manager._path.exists()

    def test_save_uses_atomic_write(self, state_manager):
        """save() writes to a .tmp file then renames."""
        state_manager.load()
        state_manager.save()
        # No .tmp file left
        assert not (state_manager._path / "state.tmp").exists()

    def test_load_corrupt_file_returns_fresh_state(self, state_manager, state_dir):
        """Corrupt JSON → fresh state."""
        filepath = state_manager._path / "state.json"
        filepath.write_text("NOT JSON{{{")
        state = state_manager.load()
        assert isinstance(state, PersistedState)
        assert state.version == 1

    def test_get_state_returns_none_before_load(self, state_manager):
        assert state_manager.get_state() is None

    def test_get_state_returns_state_after_load(self, state_manager):
        state_manager.load()
        assert state_manager.get_state() is not None

    def test_add_alert(self, state_manager):
        from infra_agent_v2.alerting.engine import Alert
        state_manager.load()
        alert = Alert(alert_id="a1", severity="critical", title="Crash", message="OOM")
        state_manager.add_alert(alert)
        history = state_manager.get_alert_history()
        assert len(history) == 1
        assert history[0].alert_id == "a1"

    def test_get_alert_history_limit(self, state_manager):
        state_manager.load()
        for i in range(10):
            state_manager._state.alert_history.append(AlertSnapshot(
                alert_id=f"a{i}", severity="info", title="t", timestamp="2026-01-01T00:00:00+00:00",
            ))
        history = state_manager.get_alert_history(limit=5)
        assert len(history) == 5

    def test_save_correlation_group(self, state_manager):
        from infra_agent_v2.correlation.correlator import CorrelationGroup
        state_manager.load()
        group = CorrelationGroup(
            group_id="g1",
            start_time=datetime.now(timezone.utc),
        )
        group.add_event({"container": "web", "severity": "critical"})
        state_manager.save_correlation_group(group)
        snapshots = state_manager.get_correlation_groups()
        assert len(snapshots) == 1
        assert snapshots[0].group_id == "g1"

    def test_update_state_syncs_counters(self, state_manager):
        state_manager.load()
        mock_updater = MagicMock()
        mock_updater.state.monitor_events = 10
        mock_updater.state.health_events = 5
        mock_updater.state.recovery_attempts = 3
        mock_updater.state.reports_generated = 2
        mock_updater.state.alerts_sent = 1
        state_manager.update_state(mock_updater)
        state = state_manager.get_state()
        assert state.monitor_events == 10
        assert state.health_events == 5
        assert state.recovery_attempts == 3
        assert state.reports_generated == 2
        assert state.alerts_sent == 1

    def test_custom_state_dir(self, config):
        with tempfile.TemporaryDirectory() as d:
            sm = StateManager(config, state_dir=d)
            assert str(sm._path) == d
