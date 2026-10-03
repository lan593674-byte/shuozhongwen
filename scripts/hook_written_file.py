#!/usr/bin/env python3
"""Check a file an agent just wrote, driven by a PostToolUse hook. Never edits it.

Reads a hook payload on stdin (Claude Code PostToolUse shape):

    {"tool_name": "Write", "tool_input": {"file_path": "..."}, "cwd": "...", "session_id": "..."}

and checks the file for invisible characters (零宽字符等), garbled text (乱码)
and AI/C2PA provenance marks. The result is not shown as a pop-up: it is saved
for the session (hook_state.py) and the MessageDisplay hook appends it to the
end of the next reply, after the AI-likeness line. Cleaning is a separate,
explicit command: /shuozhongwen qingli (scripts/qingli.py).

Earlier versions could rewrite the file in place ("clean" mode). That was
removed: a hook that silently changes files the user is editing, and reports
a cleanup for a line-ending difference, does more harm than good. The --mode
flag, the hook_mode option and WATERMARKS_HOOK_MODE are accepted and ignored.

Always exits 0 and prints nothing on stdout, so it never interrupts a tool call.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import MAX_INPUT_BYTES, eprint  # noqa: E402

# Tools whose payload names a single file the agent just wrote. The hook
# matcher should filter these too; this is the defensive second check.
FILE_WRITING_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit", "Update"})

EXIT_QUIET = 0


def target_path(payload: dict) -> Path | None:
    """The file the tool call wrote, or None when the payload names no file."""
    if payload.get("tool_name") not in FILE_WRITING_TOOLS:
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(raw, str) or not raw.strip():
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        # Hook payloads may carry a project-relative path; cwd is the session's.
        path = Path(payload.get("cwd") or Path.cwd()) / path
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", default=None, help="ignored; the hook only checks")
    parser.parse_args(argv)

    raw = sys.stdin.read()
    if not raw.strip():
        return EXIT_QUIET
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        eprint("shuozhongwen: hook payload was not valid JSON")
        return EXIT_QUIET
    if not isinstance(payload, dict):
        eprint("shuozhongwen: hook payload was not a JSON object")
        return EXIT_QUIET

    path = target_path(payload)
    if path is None or not path.is_file():
        return EXIT_QUIET
    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            return EXIT_QUIET
        import file_check
        import hook_state

        result = file_check.check_path(path)
        hook_state.record(payload.get("session_id"), {
            "path": str(path), "name": path.name, "kind": result["kind"],
            "counts": result["counts"], "provenance": result["provenance"], "skipped": result["skipped"],
        })
    except Exception as error:  # a hook must never take the session down with it
        eprint(f"shuozhongwen: check failed on {path}: {type(error).__name__}: {error}")
    return EXIT_QUIET


if __name__ == "__main__":
    raise SystemExit(main())
