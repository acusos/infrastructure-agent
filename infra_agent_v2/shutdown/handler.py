"""Graceful shutdown handler for Infra Agent v2."""

from __future__ import annotations

import os
import signal
import threading
from typing import Callable, List, Optional

from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.shutdown")

class ShutdownHandler:
    """Manages graceful shutdown of the Infra Agent."""

    def __init__(
        self,
        on_state_save: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        timeout: int = 30,
    ):
        self._on_state_save = on_state_save
        self._on_stop = on_stop
        self._timeout = timeout
        self._shutting_down = False
        self._lock = threading.Lock()
        self._shutdown_callbacks: List[Callable[[], None]] = []
        self._original_handlers: dict = {}

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    def register_shutdown_callback(self, cb: Callable[[], None]) -> None:
        self._shutdown_callbacks.append(cb)

    def register(self) -> None:
        self._original_handlers[signal.SIGINT] = signal.getsignal(signal.SIGINT)
        self._original_handlers[signal.SIGTERM] = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        logger.info("Signal handlers registered (SIGINT, SIGTERM)")

    def unregister(self) -> None:
        for sig, handler in self._original_handlers.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass
        logger.info("Signal handlers unregistered")

    def _handle_signal(self, sig: int, frame: Optional[object] = None) -> None:
        sig_name = signal.Signals(sig).name if hasattr(signal, 'Signals') else str(sig)
        logger.info("Received %s — initiating graceful shutdown", sig_name)
        self.shutdown()

    def shutdown(self, reason: str = "signal") -> None:
        with self._lock:
            if self._shutting_down:
                logger.warning("Shutdown already in progress")
                return
            self._shutting_down = True

        logger.info("Graceful shutdown initiated (reason=%s)", reason)
        self._persist_state()
        self._run_shutdown_callbacks()
        self._stop_subsystems()
        logger.info("Graceful shutdown complete")

    def _persist_state(self) -> None:
        if self._on_state_save is None:
            logger.info("No state save callback registered; skipping")
            return
        try:
            self._on_state_save()
            logger.info("Runtime state persisted successfully")
        except Exception:
            logger.exception("Failed to persist runtime state")

    def _run_shutdown_callbacks(self) -> None:
        for i, cb in enumerate(self._shutdown_callbacks):
            try:
                cb()
            except Exception:
                logger.exception("Shutdown callback %d failed", i)

    def _stop_subsystems(self) -> None:
        if self._on_stop is None:
            return
        try:
            self._on_stop()
        except Exception:
            logger.exception("Error stopping subsystems")

    def force_exit(self, code: int = 0) -> None:
        logger.critical("Forcing process exit with code %d", code)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        os._exit(code)
