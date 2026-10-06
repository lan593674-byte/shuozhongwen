"""Claude Code MessageDisplay hook for shuozhongwen. Check only, never cleans.

When a message is complete it may append a footer to the displayed text:

1. AI 相似度: when the reply has at least SHUOZHONGWEN_SCORE_MIN (default 250)
   characters of prose outside code, one line with the Chinese stylometry score.
   A /shuozhongwen delivery puts the article first and the revision report after
   a 【修改报告】 line; only the article is scored then, because the report's
   lists and key-value lines alone push any article into the high tier.
2. 检测: right after it, what the checks found: invisible characters or
   garbled text in the reply itself, and in files written since the last
   reply (saved by the PostToolUse hook, see scripts/hook_state.py). This
   line is appended to every reply, however short; only the AI-likeness line
   has a minimum length.

The reply text itself is shown exactly as written (earlier versions stripped
invisible characters from it; now they are reported instead, and removed only
by /shuozhongwen qingli). Display-only: the transcript is never touched.
A message may arrive in several deltas; they are buffered per message_id until
the final one. Logs counts, ids and scores (never response text) to
SHUOZHONGWEN_LOG_DIR, default <plugin root>/logs.
Set SHUOZHONGWEN_SCORE=0 to turn the score line off, SHUOZHONGWEN_CHECK=0 to
turn the check line off.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
LOGS = Path(os.environ.get("SHUOZHONGWEN_LOG_DIR") or ROOT / "logs")
PENDING = LOGS / "pending"
TIER_ZH = {"low": "低", "medium": "中", "high": "高"}
MAX_FILES_LISTED = 5
# The revision report that follows a /shuozhongwen delivery: 【修改报告】, ## 修改报告, **修改报告**
REPORT_HEAD = re.compile(r"^[ \t]*(?:#{1,6}[ \t]*|\*\*)?【?修改报告】?(?:\*\*)?[ \t]*[:：]?[ \t]*$", re.M)


def article_part(text: str) -> tuple[str, bool]:
    """The part of a reply to score: everything before the revision report, if there is one."""
    m = REPORT_HEAD.search(text)
    if not m:
        return text, False
    return text[:m.start()].rstrip().removesuffix("---").rstrip(), True


def score_line(text: str, status: dict) -> str:
    if os.environ.get("SHUOZHONGWEN_SCORE", "1") == "0":
        return ""
    import score_zh

    minimum = int(os.environ.get("SHUOZHONGWEN_SCORE_MIN", "250"))
    text, split = article_part(text)
    length = score_zh.han_len(score_zh.strip_code(text))
    status["chars"] = length
    if length < minimum:
        return ""
    report = score_zh.score_text_stylometry(text, path="<reply>")
    if report.score is None:
        return ""
    status.update(score=round(report.score, 3), tier=report.density_tier, article_only=split)
    pct = report.human_percentile
    where = (f"比 {pct}% 的人类段落更像 AI" if report.density_tier == "high" and pct is not None
             else "在人类文字的常见区间内")
    items = "、".join(f.split("（")[0] for f in report.findings) if report.density_tier == "high" else ""
    tail = f"｜可改：{items}" if items else ""
    what = "正文 AI 相似度（不含修改报告）" if split else "AI 相似度"
    return f"*{what} {report.score:.2f}（{TIER_ZH.get(report.density_tier, report.density_tier)}，{where}）{tail}*"


def check_line(text: str, session_id: str | None, status: dict) -> str:
    if os.environ.get("SHUOZHONGWEN_CHECK", "1") == "0":
        return ""
    import file_check
    import garble
    import hook_state

    reply = garble.inspect(text)["counts"]
    files = hook_state.consume(session_id)
    status.update(reply_issues=sum(reply.values()), files=len(files))
    parts = [f"回复里有{garble.summary(reply)}" if reply else "回复无零宽字符和乱码"]
    bad = [(f, file_check.describe(f)) for f in files]
    bad = [(f, d) for f, d in bad if d]
    if files:
        if bad:
            listed = "；".join(f"{f['name']}：{d}" for f, d in bad[:MAX_FILES_LISTED])
            more = f"；另有 {len(bad) - MAX_FILES_LISTED} 个" if len(bad) > MAX_FILES_LISTED else ""
            parts.append(f"写入的 {len(files)} 个文件里 {len(bad)} 个有问题：{listed}{more}")
        else:
            parts.append(f"写入的 {len(files)} 个文件无零宽字符和乱码")
    tail = "｜清除可用 /shuozhongwen qingli" if reply or bad else ""
    return f"*检测：{'；'.join(parts)}{tail}*"


def footer(text: str, session_id: str | None, status: dict) -> str:
    lines = []
    try:
        s = score_line(text, status)
        if s:
            lines.append(s)
    except Exception as error:  # scoring must never block the reply
        status["score_error"] = type(error).__name__
    try:
        c = check_line(text, session_id, status)
        if c:
            lines.append(c)
    except Exception as error:
        status["check_error"] = type(error).__name__
    return "\n\n---\n" + "\n".join(lines) if lines else ""


def buffered_text(event: dict, delta: str) -> str | None:
    """Accumulate deltas of one message; return the whole text on the final delta."""
    mid = str(event.get("message_id") or "")
    final = bool(event.get("final", True))
    if not mid:
        return delta if final else None
    PENDING.mkdir(parents=True, exist_ok=True)
    buf = PENDING / f"{''.join(c for c in mid if c.isalnum() or c in '-_')}.txt"
    if not final:
        with buf.open("a", encoding="utf-8") as f:
            f.write(delta)
        return None
    earlier = buf.read_text(encoding="utf-8") if buf.exists() else ""
    buf.unlink(missing_ok=True)
    for old in PENDING.glob("*.txt"):  # drop buffers of messages that never finished
        if time.time() - old.stat().st_mtime > 86400:
            old.unlink(missing_ok=True)
    return earlier + delta


def main():
    event = json.load(sys.stdin)
    delta = event.get("delta") or ""
    display = delta
    status: dict = {}
    try:
        full = buffered_text(event, delta)
        if full is not None:
            display = delta + footer(full, event.get("session_id"), status)
    except Exception as error:  # the reply must always be shown
        status["error"] = type(error).__name__
    try:
        LOGS.mkdir(parents=True, exist_ok=True)
        with (LOGS / "display.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(),
                "message_id": event.get("message_id"), "index": event.get("index"),
                "final": event.get("final"), **status}) + "\n")
    except OSError:
        pass
    json.dump({"hookSpecificOutput": {"hookEventName": "MessageDisplay",
        "displayContent": display}}, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
