"""Claude Code MessageDisplay hook for shuozhongwen.

1. Strips invisible Unicode carriers from the assistant text before it is shown.
2. When a message is complete and has at least SHUOZHONGWEN_SCORE_MIN (default
   250) characters of prose outside code, appends one line with the Chinese
   stylometry score (score_zh) to the displayed text.

Display-only: the transcript keeps the original text, and the reply itself is
never rewritten. A message may arrive in several deltas; they are buffered per
message_id until the final one. Logs counts, ids and scores (never response
text) to SHUOZHONGWEN_LOG_DIR, default <plugin root>/logs.
Set SHUOZHONGWEN_SCORE=0 to turn the score line off.
"""

import json
import os
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


def score_footer(text: str, status: dict) -> str:
    if os.environ.get("SHUOZHONGWEN_SCORE", "1") == "0":
        return ""
    import score_zh

    minimum = int(os.environ.get("SHUOZHONGWEN_SCORE_MIN", "250"))
    length = score_zh.han_len(score_zh.strip_code(text))
    status["chars"] = length
    if length < minimum:
        return ""
    report = score_zh.score_text_stylometry(text, path="<reply>")
    if report.score is None:
        return ""
    status.update(score=round(report.score, 3), tier=report.density_tier)
    pct = report.human_percentile
    where = (f"比 {pct}% 的人类段落更像 AI" if report.density_tier == "high" and pct is not None
             else "在人类文字的常见区间内")
    items = "、".join(f.split("（")[0] for f in report.findings) if report.density_tier == "high" else ""
    tail = f"｜可改：{items}" if items else ""
    return f"\n\n---\n*AI 相似度 {report.score:.2f}（{TIER_ZH.get(report.density_tier, report.density_tier)}，{where}）{tail}*"


def buffered_text(event: dict, cleaned: str) -> str | None:
    """Accumulate deltas of one message; return the whole text on the final delta."""
    mid = str(event.get("message_id") or "")
    final = bool(event.get("final", True))
    if not mid:
        return cleaned if final else None
    PENDING.mkdir(parents=True, exist_ok=True)
    buf = PENDING / f"{''.join(c for c in mid if c.isalnum() or c in '-_')}.txt"
    if not final:
        with buf.open("a", encoding="utf-8") as f:
            f.write(cleaned)
        return None
    earlier = buf.read_text(encoding="utf-8") if buf.exists() else ""
    buf.unlink(missing_ok=True)
    for old in PENDING.glob("*.txt"):  # drop buffers of messages that never finished
        if time.time() - old.stat().st_mtime > 86400:
            old.unlink(missing_ok=True)
    return earlier + cleaned


def main():
    event = json.load(sys.stdin)
    try:
        from text_unicode import clean_text

        cleaned, stats = clean_text(event["delta"], normalize_spaces=False)
        status = {"removed": stats["removed_count"], "replaced": stats["replaced_count"]}
    except Exception as error:
        cleaned = "[回复清理失败，本批文字未展示；请检查 shuozhongwen 的清理程序。]"
        status = {"error": type(error).__name__}
    display = cleaned
    if "error" not in status:
        try:
            full = buffered_text(event, cleaned)
            if full is not None:
                display = cleaned + score_footer(full, status)
        except Exception as error:  # scoring must never block the reply
            status["score_error"] = type(error).__name__
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
