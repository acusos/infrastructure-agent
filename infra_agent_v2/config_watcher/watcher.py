"""Config file watcher for Infra Agent v2.

Watches the config file for changes and triggers a reload when detected.
Uses a polling approach (no external deps) to avoid adding watchdog dependency.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from datetime import datetime, timezone
from typing import Callable, List, Optional

from infra_agent_v2.config import Config, load_config
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.config_watcher")

# ---------------------------------------------------------------------------
# Change tracking
# ---------------------------------------------------------------------------

def _file_hash(path: str) -> str:
    """Return a hash of the file contents, or empty string on error."""
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except (OSError, IOError):
        return ""

# ---------------------------------------------------------------------------
# ConfigWatcher
# ---------------------------------------------------------------------------

class ConfigWatcher:
    """Watches a config file for changes and triggers reload callbacks."""

    def __init__(
        self,
        config_path: str,
        interval: float = 5.0,
        reload_callbacks: Optional[List[Callable[[Config], None]]] = None,
    ):
        self.config_path = config_path
        self.interval = interval
        self._callbacks: List[Callable[[Config], None]] = reload_callbacks or []
        self._current_hash = _file_hash(config_path)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_reload: Optional[datetime] = None

    def register_reload_callback(self, cb: Callable[[Config], None]) -> None:
        """Register a callback to run when config is reloaded."""
        self._callbacks.append(cb)
        name = getattr(cb, "__qualname__", type(cb).__name__)
        logger.info("Registered config reload callback: %s", name)

    def start(self) -> None:
        """Start watching the config file."""
        if self._running:
            logger.warning("Config watcher already running")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._watch_loop, daemon=True, name="config-watcher",
        )
        self._thread.start()
        logger.info("Config watcher started (interval=%.1fs, path=%s)", self.interval, self.config_path)

    def stop(self) -> None:
        """Stop the watcher."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=self.interval + 1)
            self._thread = None
        logger.info("Config watcher stopped")

    def _watch_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            time.sleep(self.interval)
            new_hash = _file_hash(self.config_path)
            if new_hash and new_hash != self._current_hash:
                self._current_hash = new_hash
                self._reload_config()

    def _reload_config(self) -> None:
        """Reload config and fire callbacks."""
        try:
            new_config = load_config(self.config_path)
            logger.info("Config reloaded from %s at %s", self.config_path, datetime.now(timezone.utc).isoformat())
            self._last_reload = datetime.now(timezone.utc)
        except Exception as exc:
            logger.error("Failed to reload config from %s: %s", self.config_path, exc)
            return

        for cb in self._callbacks:
            try:
                cb(new_config)
            except Exception as exc:
                logger.error("Config reload callback %s failed: %s", cb.__qualname__, exc)

    def get_last_reload_time(self) -> Optional[str]:
        """Return ISO timestamp of last reload."""
        if self._last_reload is None:
            return None
        return self._last_reload.isoformat()
