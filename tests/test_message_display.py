"""MessageDisplay hook: cleaning, buffering across deltas, score footer."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "message_display.py"
LONG = ("在当今快速发展的时代，人工智能正在深刻地改变我们的生活方式。首先，我们需要进行全面的分析；其次，我们需要作出合理的规划。\n\n" * 4
        + "总而言之，只有不断创新，才能在激烈的竞争中立于不败之地。让我们携手并进，共同迎接更加美好的未来。\n")


def run(event: dict, tmp_path: Path, **env) -> str:
    e = {**os.environ, "SHUOZHONGWEN_LOG_DIR": str(tmp_path), **env}
    out = subprocess.run([sys.executable, "-X", "utf8", str(HOOK)], input=json.dumps(event, ensure_ascii=False),
                         capture_output=True, text=True, encoding="utf-8", env=e, check=True)
    return json.loads(out.stdout)["hookSpecificOutput"]["displayContent"]


def test_short_reply_is_only_cleaned(tmp_path):
    out = run({"message_id": "m1", "index": 0, "final": True, "delta": "短\u200b回复"}, tmp_path)
    assert out == "短回复"


def test_long_reply_gets_score_footer(tmp_path):
    out = run({"message_id": "m2", "index": 0, "final": True, "delta": LONG}, tmp_path)
    assert out.startswith(LONG)
    assert "AI 相似度" in out.split("---")[-1]


def test_deltas_are_buffered_and_scored_once(tmp_path):
    half = len(LONG) // 2
    first = run({"message_id": "m3", "index": 0, "final": False, "delta": LONG[:half]}, tmp_path)
    last = run({"message_id": "m3", "index": 1, "final": True, "delta": LONG[half:]}, tmp_path)
    assert first == LONG[:half]
    assert last.startswith(LONG[half:]) and "AI 相似度" in last
    assert not list((tmp_path / "pending").glob("*.txt"))


def test_score_can_be_switched_off(tmp_path):
    out = run({"message_id": "m4", "index": 0, "final": True, "delta": LONG}, tmp_path, SHUOZHONGWEN_SCORE="0")
    assert out == LONG
