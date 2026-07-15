"""Thread-safe, local text-to-speech support for accessible feedback."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class SpeechHandler:
    """Speak queued text through a local ``pyttsx3`` engine without blocking."""

    def __init__(self, rate: int = 175, volume: float = 1.0) -> None:
        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._state_lock = threading.RLock()
        self._closed = False
        self._engine: object | None = None
        self._engine_ready = threading.Event()
        self._rate = rate
        self._volume = volume
        self._worker = threading.Thread(
            target=self._run,
            name="mythos-speech-worker",
            daemon=True,
        )
        self._worker.start()
        # Initialization stays off FastAPI's event loop and on the same thread
        # that will later call the Windows SAPI/pyttsx3 engine.
        self._engine_ready.wait(timeout=2.0)

    @staticmethod
    def _create_engine(rate: int, volume: float) -> object | None:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", max(80, int(rate)))
            engine.setProperty("volume", max(0.0, min(float(volume), 1.0)))
            return engine
        except ImportError:
            logger.warning("Offline speech is unavailable because pyttsx3 is not installed.")
        except Exception:
            logger.warning("Local text-to-speech is unavailable; voice feedback will be skipped.")
            logger.debug("Text-to-speech engine initialization details", exc_info=True)
        return None

    @property
    def available(self) -> bool:
        """Whether the local offline speech engine is ready to accept work."""
        with self._state_lock:
            return self._engine_ready.is_set() and not self._closed and self._engine is not None

    def speak_text(self, text: str) -> bool:
        """Queue text for non-blocking speech playback.

        The method returns immediately. ``False`` means no local speech engine is
        available, the handler was shut down, or the supplied text was blank.
        Speech content never leaves the device.
        """
        message = text.strip() if isinstance(text, str) else ""
        if not message:
            return False

        with self._state_lock:
            if self._closed:
                return False
            if self._engine_ready.is_set() and self._engine is None:
                return False
            self._queue.put(message)
        return True

    def shutdown(self, timeout: float = 2.0) -> None:
        """Stop accepting work and signal the speech thread during shutdown."""
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            self._queue.put(None)
        self._worker.join(timeout=max(0.0, timeout))

    def _run(self) -> None:
        """Run all pyttsx3 operations on one dedicated worker thread."""
        engine = self._create_engine(rate=self._rate, volume=self._volume)
        with self._state_lock:
            self._engine = engine
            self._engine_ready.set()

        while True:
            message = self._queue.get()
            try:
                if message is None:
                    return
                if engine is not None:
                    engine.say(message)
                    engine.runAndWait()
            except Exception:
                logger.exception("Local speech playback failed")
            finally:
                self._queue.task_done()
