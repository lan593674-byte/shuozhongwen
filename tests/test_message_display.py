"""MessageDisplay hook: check only, buffering across deltas, score and check footer."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "message_display.py"
WRITE_HOOK = Path(__file__).resolve().parents[1] / "scripts" / "hook_written_file.py"
LONG = ("在当今快速发展的时代，人工智能正在深刻地改变我们的生活方式。首先，我们需要进行全面的分析；其次，我们需要作出合理的规划。\n\n" * 4
        + "总而言之，只有不断创新，才能在激烈的竞争中立于不败之地。让我们携手并进，共同迎接更加美好的未来。\n")
ZW = chr(0x200B)


def run(event: dict, tmp_path: Path, **env) -> str:
    e = {**os.environ, "SHUOZHONGWEN_LOG_DIR": str(tmp_path), **env}
    out = subprocess.run([sys.executable, "-X", "utf8", str(HOOK)], input=json.dumps(event, ensure_ascii=False),
                         capture_output=True, text=True, encoding="utf-8", env=e, check=True)
    return json.loads(out.stdout)["hookSpecificOutput"]["displayContent"]


def write(path: Path, tmp_path: Path, session: str = "s1") -> None:
    subprocess.run([sys.executable, str(WRITE_HOOK)], input=json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": str(path)}, "cwd": str(path.parent), "session_id": session}),
        text=True, encoding="utf-8", capture_output=True, env={**os.environ, "SHUOZHONGWEN_LOG_DIR": str(tmp_path)},
        check=True)


def test_every_reply_gets_the_check_line_however_short(tmp_path):
    out = run({"message_id": "m1", "index": 0, "final": True, "delta": "好"}, tmp_path)
    assert out == "好\n\n---\n*检测：回复无零宽字符和乱码*"


def test_reply_is_never_modified_only_reported(tmp_path):
    out = run({"message_id": "m1", "index": 0, "final": True, "delta": "短" + ZW + "回复"}, tmp_path)
    assert out.startswith("短" + ZW + "回复")
    assert "检测：回复里有零宽/不可见字符 1" in out and "/shuozhongwen qingli" in out


def test_long_reply_gets_score_then_check_line(tmp_path):
    out = run({"message_id": "m2", "index": 0, "final": True, "delta": LONG}, tmp_path)
    assert out.startswith(LONG)
    tail = out.split("---")[-1].strip().splitlines()
    assert "AI 相似度" in tail[0] and tail[1] == "*检测：回复无零宽字符和乱码*"


def test_written_files_are_reported_once_after_the_ai_line(tmp_path):
    bad, good = tmp_path / "bad.md", tmp_path / "good.md"
    bad.write_text("正文" + ZW + "，丢字\ufffd。", encoding="utf-8")
    good.write_text("干净。", encoding="utf-8")
    write(bad, tmp_path)
    write(good, tmp_path)
    out = run({"message_id": "m5", "index": 0, "final": True, "delta": LONG, "session_id": "s1"}, tmp_path)
    check = out.split("---")[-1].strip().splitlines()[1]
    assert "写入的 2 个文件里 1 个有问题：bad.md：零宽/不可见字符 1、替换符 U+FFFD（字符已丢失） 1" in check
    assert "good.md" not in check
    again = run({"message_id": "m6", "index": 0, "final": True, "delta": "好的", "session_id": "s1"}, tmp_path)
    assert again == "好的\n\n---\n*检测：回复无零宽字符和乱码*"  # files consumed: reported once
    assert bad.read_text(encoding="utf-8").count(ZW) == 1  # never cleaned


def test_short_reply_reports_written_files(tmp_path):
    f = tmp_path / "ok.md"
    f.write_text("干净。", encoding="utf-8")
    write(f, tmp_path, session="s2")
    out = run({"message_id": "m7", "index": 0, "final": True, "delta": "改好了。", "session_id": "s2"}, tmp_path)
    assert out.endswith("*检测：回复无零宽字符和乱码；写入的 1 个文件无零宽字符和乱码*")


def test_deltas_are_buffered_and_scored_once(tmp_path):
    half = len(LONG) // 2
    first = run({"message_id": "m3", "index": 0, "final": False, "delta": LONG[:half]}, tmp_path)
    last = run({"message_id": "m3", "index": 1, "final": True, "delta": LONG[half:]}, tmp_path)
    assert first == LONG[:half]
    assert last.startswith(LONG[half:]) and "AI 相似度" in last
    assert not list((tmp_path / "pending").glob("*.txt"))


def test_score_and_check_can_be_switched_off(tmp_path):
    out = run({"message_id": "m4", "index": 0, "final": True, "delta": LONG}, tmp_path,
              SHUOZHONGWEN_SCORE="0", SHUOZHONGWEN_CHECK="0")
    assert out == LONG


REPORT = """---

【修改报告】

- 文体：课程论坛帖（说明文）
- 主线：亚北极的普遍描述放到克里人身上对得上，放到整个北方森林不都对。
- 数据核对：材料数据清单 9 条，文章用了其中 6 条，逐条对过，全部一致。
- 编辑审读：第 1 轮；六项：具体 4 / 发现 3 / 语言 4 / 节奏 4 / 结构 4 / 声音 3；白开水：否。
- 照改的意见：删掉了开头的报幕句；把“材料里只有两条”这类交代删掉。
- 事实核查：存疑 0 条。
- 待作者核对：无。
- 建议作者补充的细节：你自己对克里人反对水电工程的看法（如果题目要求表态）。
- 硬闸：不可见字符 0；四条机械扫描全过；结构套路 0 处；AI 相似度 0.38（中）。
"""


def test_delivery_scores_the_article_not_the_report(tmp_path):
    # 《一件小事》 alone is low; with a revision report appended the whole reply
    # scores high, which is what the footer used to show for every delivery.
    article = (Path(__file__).resolve().parents[1] / "calibration" / "human" / "鲁迅_一件小事.txt").read_text(encoding="utf-8")
    out = run({"message_id": "m5", "index": 0, "final": True, "delta": article + "\n\n" + REPORT}, tmp_path)
    line = out.split("\n---\n")[-1].strip().splitlines()[0]
    assert line.startswith("*正文 AI 相似度（不含修改报告）") and "（低" in line
    plain = run({"message_id": "m6", "index": 0, "final": True, "delta": article}, tmp_path)
    assert plain.split("\n---\n")[-1].strip().splitlines()[0].startswith("*AI 相似度 ")
