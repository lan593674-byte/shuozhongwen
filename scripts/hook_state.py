"""Hand file-check results from the PostToolUse hook to the MessageDisplay hook.

The file hook only checks; what it finds is appended to the end of the next
reply, after the AI-likeness line. Both hooks run as separate processes, so
the findings are kept in a small JSON-lines file per session under the log
directory (SHUOZHONGWEN_LOG_DIR, default <plugin root>/logs). Nothing here
stores file contents, only names, counts and short labels.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_AGE = 86400


def log_dir() -> Path:
    return Path(os.environ.get("SHUOZHONGWEN_LOG_DIR") or ROOT / "logs")


def _findings_file(session_id: str | None) -> Path:
    sid = "".join(c for c in str(session_id or "default") if c.isalnum() or c in "-_") or "default"
    return log_dir() / "findings" / f"{sid}.jsonl"


def record(session_id: str | None, finding: dict) -> None:
    path = _findings_file(session_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(finding, ensure_ascii=False) + "\n")
    except OSError:
        pass


def consume(session_id: str | None) -> list[dict]:
    """Return and clear the session's findings; one entry per file, latest wins."""
    path = _findings_file(session_id)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        path.unlink(missing_ok=True)
    except OSError:
        return []
    latest: dict[str, dict] = {}
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        latest[item.get("path", "")] = item
    for old in path.parent.glob("*.jsonl"):  # sessions that ended without another reply
        try:
            if time.time() - old.stat().st_mtime > MAX_AGE:
                old.unlink(missing_ok=True)
        except OSError:
            pass
    return list(latest.values())
