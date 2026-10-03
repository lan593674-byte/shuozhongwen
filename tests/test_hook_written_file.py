"""PostToolUse hook: check the file an agent just wrote, never change it.

Driven exactly as the harness does: payload on stdin. The hook prints nothing
and always exits 0; what it found is recorded per session for the
MessageDisplay hook, which appends it to the end of the next reply.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts" / "hook_written_file.py"
MARKED = ROOT / "tests" / "fixtures" / "sample_watermarked.txt"
ZW = chr(0x200B)


def run_hook(payload, logs: Path, *args: str, env: dict[str, str] | None = None):
    full_env = {**os.environ, "SHUOZHONGWEN_LOG_DIR": str(logs), **(env or {})}
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        text=True, encoding="utf-8", capture_output=True, env=full_env, check=False,
    )


def write_event(path: Path, cwd: Path | None = None, tool: str = "Write", session: str = "s1") -> dict:
    return {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": {"file_path": str(path)},
            "tool_response": {"status": "success"}, "cwd": str(cwd or path.parent), "session_id": session}


def findings(logs: Path, session: str = "s1") -> list[dict]:
    f = logs / "findings" / f"{session}.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


@pytest.fixture
def logs(tmp_path) -> Path:
    return tmp_path / "logs"


def test_marked_file_is_recorded_and_left_untouched(tmp_path, logs):
    path = tmp_path / "draft.md"
    path.write_bytes(MARKED.read_bytes())
    before = path.read_bytes()
    r = run_hook(write_event(path), logs)
    assert r.returncode == 0 and r.stdout == ""
    assert path.read_bytes() == before
    [item] = findings(logs)
    assert item["name"] == "draft.md" and item["counts"].get("invisible")


def test_clean_file_is_recorded_as_clean(tmp_path, logs):
    path = tmp_path / "clean.md"
    path.write_text("普通的文字，没有问题。\n", encoding="utf-8")
    run_hook(write_event(path), logs)
    [item] = findings(logs)
    assert item["counts"] == {} and item["kind"] == "text"


def test_crlf_frontmatter_file_is_not_touched_and_not_reported(tmp_path, logs):
    # the false alarm that started this: a CRLF SKILL.md reported as "cleaned"
    path = tmp_path / "SKILL.md"
    data = b"---\r\nname: x\r\ndescription: y\r\n---\r\n\r\n# Title\r\nbody\r\n"
    path.write_bytes(data)
    r = run_hook(write_event(path, tool="Edit"), logs, "--mode", "clean", env={"WATERMARKS_HOOK_MODE": "clean"})
    assert r.returncode == 0 and r.stdout == ""
    assert path.read_bytes() == data
    assert findings(logs)[0]["counts"] == {}


def test_garbled_text_is_recorded(tmp_path, logs):
    path = tmp_path / "notes.txt"
    path.write_text("丢了\ufffd一个字，锟斤拷，正文" + ZW + "里有零宽。", encoding="utf-8")
    run_hook(write_event(path), logs)
    counts = findings(logs)[0]["counts"]
    assert counts["replacement"] == 1 and counts["placeholder"] == 1 and counts["invisible"] == 1


def test_relative_path_resolves_against_payload_cwd(tmp_path, logs):
    path = tmp_path / "rel.md"
    path.write_text("文字" + ZW, encoding="utf-8")
    payload = write_event(path)
    payload["tool_input"]["file_path"] = "rel.md"
    run_hook(payload, logs)
    assert findings(logs)[0]["name"] == "rel.md"


def test_notebook_edit_payload_uses_notebook_path(tmp_path, logs):
    nb = tmp_path / "n.ipynb"
    nb.write_text(json.dumps({"cells": [{"source": ["x" + ZW]}]}, ensure_ascii=False), encoding="utf-8")
    run_hook({"tool_name": "NotebookEdit", "tool_input": {"notebook_path": str(nb)}, "cwd": str(tmp_path),
              "session_id": "s1"}, logs)
    assert findings(logs)[0]["counts"].get("invisible")


@pytest.mark.parametrize("payload", [
    {"tool_name": "Bash", "tool_input": {"command": "ls"}},
    {"tool_name": "Write", "tool_input": {}},
    {"tool_name": "Write", "tool_input": {"file_path": "  "}},
    {"tool_name": "Write"},
    {},
    "not json at all",
    '["a", "list"]',
    "",
])
def test_payloads_without_a_written_file_are_silent(payload, logs):
    r = run_hook(payload, logs)
    assert r.returncode == 0 and r.stdout == "" and "Traceback" not in r.stderr
    assert findings(logs) == []


def test_missing_and_oversized_files_are_skipped(tmp_path, logs):
    sys.path.insert(0, str(ROOT / "scripts"))
    from common import MAX_INPUT_BYTES

    big = tmp_path / "huge.md"
    big.write_bytes(b"x" * (MAX_INPUT_BYTES + 1))
    for p in (tmp_path / "never.md", big):
        r = run_hook(write_event(p), logs)
        assert r.returncode == 0 and r.stdout == ""
    assert findings(logs) == []


def test_sessions_are_kept_apart(tmp_path, logs):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("a", encoding="utf-8")
    b.write_text("b", encoding="utf-8")
    run_hook(write_event(a, session="one"), logs)
    run_hook(write_event(b, session="two"), logs)
    assert [x["name"] for x in findings(logs, "one")] == ["a.md"]
    assert [x["name"] for x in findings(logs, "two")] == ["b.md"]
