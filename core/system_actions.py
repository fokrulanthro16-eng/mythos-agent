"""Conservative local system utilities used by the Mythos API."""

from __future__ import annotations

import logging
import os
import stat
import tempfile
import time
from pathlib import Path
from typing import Any

import psutil

from config import settings

logger = logging.getLogger(__name__)


class SystemActionError(RuntimeError):
    """Raised when a local system action cannot be performed safely."""


def clean_temp_files(min_age_seconds: int = 3600) -> dict[str, Any]:
    """Remove stale Mythos-owned temporary files without touching system temp data.

    Only the application's own directory inside the operating-system temp folder
    is considered. Links, junctions, protected entries, and recent files are
    skipped so an active diagnosis is never intentionally removed.
    """
    temp_root = Path(os.path.abspath(tempfile.gettempdir()))
    target = Path(os.path.abspath(settings.app_temp_directory))
    try:
        target.relative_to(temp_root)
    except ValueError as exc:
        raise SystemActionError("Temporary cleanup target is outside the safe area.") from exc

    result: dict[str, Any] = {
        "status": "completed",
        "files_deleted": 0,
        "directories_deleted": 0,
        "bytes_reclaimed": 0,
        "skipped_recent": 0,
        "skipped_protected": 0,
        "warnings": 0,
    }
    if not target.exists():
        return result
    if _is_reparse_point(target):
        raise SystemActionError("Temporary cleanup target is a protected link.")

    cutoff = time.time() - max(0, min_age_seconds)

    def visit(directory: Path) -> None:
        try:
            entries = list(directory.iterdir())
        except OSError:
            logger.warning("Could not inspect a Mythos temporary directory", exc_info=True)
            result["warnings"] += 1
            return

        for entry in entries:
            try:
                if _is_reparse_point(entry):
                    result["skipped_protected"] += 1
                    continue
                entry_stat = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(entry_stat.st_mode):
                    visit(entry)
                    try:
                        entry.rmdir()
                        result["directories_deleted"] += 1
                    except FileNotFoundError:
                        pass
                    except OSError:
                        # Non-empty or locked directories are safe to preserve.
                        pass
                elif stat.S_ISREG(entry_stat.st_mode):
                    if entry_stat.st_mtime > cutoff:
                        result["skipped_recent"] += 1
                        continue
                    entry.unlink()
                    result["files_deleted"] += 1
                    result["bytes_reclaimed"] += entry_stat.st_size
                else:
                    result["skipped_protected"] += 1
            except FileNotFoundError:
                # Another process may have removed a file between inspection and action.
                continue
            except OSError:
                logger.warning("Could not remove a Mythos temporary entry", exc_info=True)
                result["warnings"] += 1

    visit(target)
    if result["warnings"]:
        result["status"] = "completed_with_warnings"
    return result


def get_system_health() -> dict[str, Any]:
    """Return local CPU, memory, and current-drive usage without changing state."""
    try:
        disk_root = Path.cwd().anchor or str(Path.cwd())
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(disk_root)
        return {
            "available": True,
            "cpu": {
                "usage_percent": round(psutil.cpu_percent(interval=0.1), 1),
                "logical_cores": psutil.cpu_count(logical=True) or 0,
            },
            "memory": {
                "total_bytes": memory.total,
                "used_bytes": memory.used,
                "available_bytes": memory.available,
                "usage_percent": memory.percent,
            },
            "disk": {
                "path": disk_root,
                "total_bytes": disk.total,
                "used_bytes": disk.used,
                "free_bytes": disk.free,
                "usage_percent": disk.percent,
            },
        }
    except (OSError, ValueError, psutil.Error):
        logger.exception("Unable to gather local system metrics")
        return {
            "available": False,
            "error": "System metrics are temporarily unavailable.",
        }


def _is_reparse_point(path: Path) -> bool:
    """Treat symlinks and Windows junctions as protected, never traversable paths."""
    try:
        if path.is_symlink():
            return True
        attributes = getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        return bool(attributes & reparse_flag)
    except OSError:
        return True
