"""Lightweight evidence archiving for high-signal scan findings."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


EVIDENCE_ROOT = Path(__file__).resolve().parent.parent / "evidence"


def archive_result_evidence(scan_id: int, result_id: int | None, payload: dict) -> str:
    """Persist an evidence snapshot and return its path."""
    scan_dir = EVIDENCE_ROOT / f"scan_{scan_id}"
    scan_dir.mkdir(parents=True, exist_ok=True)

    platform = str(payload.get("platform") or "result").lower()
    safe_platform = re.sub(r"[^a-z0-9]+", "-", platform).strip("-") or "result"
    suffix = result_id if result_id is not None else "pending"
    path = scan_dir / f"{suffix}-{safe_platform}.json"

    # Enrich with archival timestamp
    payload_with_ts = {
        **payload,
        "_archived_at": datetime.now(timezone.utc).isoformat(),
        "_scan_id": scan_id,
        "_result_id": result_id,
    }

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload_with_ts, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    return str(path)


def list_evidence(scan_id: int) -> list[dict]:
    """List all evidence snapshots for a scan.

    Returns a list of dicts with {filename, size_bytes, created_at}.
    """
    scan_dir = EVIDENCE_ROOT / f"scan_{scan_id}"
    if not scan_dir.exists():
        return []

    evidence = []
    for entry in sorted(scan_dir.iterdir()):
        if entry.is_file() and entry.suffix == ".json":
            stat = entry.stat()
            created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat()
            evidence.append({
                "filename": entry.name,
                "size_bytes": stat.st_size,
                "created_at": created_at,
            })

    return evidence


def get_evidence_file(scan_id: int, filename: str) -> dict | None:
    """Read and return the contents of a specific evidence snapshot.

    Performs a safe path check to prevent directory traversal.
    Returns None if the file does not exist or is outside the scan directory.
    """
    scan_dir = EVIDENCE_ROOT / f"scan_{scan_id}"

    # Sanitize filename — no path components allowed
    safe_name = os.path.basename(filename)
    if not safe_name or safe_name != filename:
        return None

    target = scan_dir / safe_name
    # Ensure resolved path stays inside the scan directory
    try:
        target.resolve().relative_to(scan_dir.resolve())
    except ValueError:
        return None

    if not target.exists() or not target.is_file():
        return None

    try:
        with target.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
