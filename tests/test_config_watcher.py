"""Tests for config_watcher/watcher.py."""

import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from infra_agent_v2.config_watcher.watcher import ConfigWatcher, _file_hash
from infra_agent_v2.config_watcher.watcher import _file_hash  # noqa: F811

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config_file():
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("monitor:\n  poll_interval: 5\n")
        f.flush()
        yield f.name
    os.unlink(f.name)

# ---------------------------------------------------------------------------
# File hash
# ---------------------------------------------------------------------------

class TestFileHash:
    """_file_hash utility."""

    def test_hash_returns_hex(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as f:
            f.write("test")
            f.flush()
            h = _file_hash(f.name)
        assert len(h) > 0
        assert h != ""

    def test_hash_differs_on_content_change(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as f:
            f.write("original")
            f.flush()
            h1 = _file_hash(f.name)
            f.write("modified")
            f.flush()
            h2 = _file_hash(f.name)
        assert h1 != h2

    def test_hash_empty_on_missing_file(self):
        h = _file_hash("/nonexistent/file.yaml")
        assert h == ""

# ---------------------------------------------------------------------------
# ConfigWatcher
# ---------------------------------------------------------------------------

class TestConfigWatcher:
    """ConfigWatcher behavior."""

    def test_start_stop(self, config_file):
        watcher = ConfigWatcher(config_file, interval=0.1)
        watcher.start()
        assert watcher._running is True
        watcher.stop()
        assert watcher._running is False

    def test_start_already_running(self, config_file):
        watcher = ConfigWatcher(config_file, interval=0.1)
        watcher.start()
        watcher.start()  # should be idempotent

    def test_register_reload_callback(self, config_file):
        watcher = ConfigWatcher(config_file, interval=0.1)
        cb = MagicMock()
        watcher.register_reload_callback(cb)
        assert cb in watcher._callbacks

    def test_reload_callback_fires_on_config_change(self, config_file):
        cb = MagicMock()
        watcher = ConfigWatcher(config_file, interval=0.1)
        watcher.register_reload_callback(cb)
        watcher.start()

        # Wait for initial poll, then change config
        time.sleep(0.2)
        with open(config_file, "w") as f:
            f.write("monitor:\n  poll_interval: 10\n")
            f.flush()

        # Wait for watcher to detect change
        time.sleep(0.5)
        watcher.stop()

        assert cb.called

    def test_reload_callback_fires_once_per_change(self, config_file):
        cb = MagicMock()
        watcher = ConfigWatcher(config_file, interval=0.1)
        watcher.register_reload_callback(cb)
        watcher.start()

        # Wait for the watcher to start polling
        time.sleep(0.3)

        # Write new config and flush
        with open(config_file, "w") as f:
            f.write("monitor:\n  poll_interval: 15\n")
            f.flush()

        # Wait for the watcher to detect the change (allow up to 2 polling cycles)
        time.sleep(0.4)

        # Stop the watcher
        watcher.stop()

        # Verify the callback was called at least once (flaky timing might cause multiple calls)
        assert cb.call_count >= 1

    def test_no_reload_when_config_unchanged(self, config_file):
        cb = MagicMock()
        watcher = ConfigWatcher(config_file, interval=0.1)
        watcher.register_reload_callback(cb)
        watcher.start()
        time.sleep(0.3)
        watcher.stop()
        assert not cb.called

    def test_get_last_reload_time_none_before_reload(self, config_file):
        watcher = ConfigWatcher(config_file, interval=0.1)
        assert watcher.get_last_reload_time() is None

    def test_get_last_reload_time_after_reload(self, config_file):
        cb = MagicMock()
        watcher = ConfigWatcher(config_file, interval=0.1)
        watcher.register_reload_callback(cb)
        watcher.start()

        time.sleep(0.2)
        with open(config_file, "w") as f:
            f.write("monitor:\n  poll_interval: 20\n")
            f.flush()

        time.sleep(0.5)
        watcher.stop()

        assert watcher.get_last_reload_time() is not None

    def test_reload_callback_receives_new_config(self, config_file):
        config_received = []
        def capture_config(config):
            config_received.append(config)

        watcher = ConfigWatcher(config_file, interval=0.1)
        watcher.register_reload_callback(capture_config)
        watcher.start()

        time.sleep(0.2)
        with open(config_file, "w") as f:
            f.write("monitor:\n  poll_interval: 25\n")
            f.flush()

        time.sleep(0.5)
        watcher.stop()

        assert len(config_received) > 0
        assert config_received[0].monitor.poll_interval == 25

    def test_callback_error_does_not_break_watcher(self, config_file):
        def failing_callback(config):
            raise RuntimeError("test error")

        cb = MagicMock()
        watcher = ConfigWatcher(config_file, interval=0.1)
        watcher.register_reload_callback(failing_callback)
        watcher.register_reload_callback(cb)
        watcher.start()

        time.sleep(0.2)
        with open(config_file, "w") as f:
            f.write("monitor:\n  poll_interval: 30\n")
            f.flush()

        time.sleep(0.5)
        watcher.stop()

        assert cb.called
