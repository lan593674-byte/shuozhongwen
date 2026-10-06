#!/usr/bin/env python3
"""Run the shuozhongwen judges through any OpenAI-compatible API.

For agents without subagents, or to have a different model than the writer
judge the draft (a model grading its own habits is too lenient): each call is
a brand-new, stateless request that sees only the rubric and the text. The
rubrics are read from agents/*.md, the same prompts the Claude Code subagents
use. Replies are saved as JSON and checked with review_zh.py (evidence rule,
templates, gate, fact doubts), exactly as in the subagent flow.

Which API and model: judge_config.py (one config file, ~/.shuozhongwen/judge.json;
environment variables SHUOZHONGWEN_API_BASE / _MODEL / _API_KEY override it).
The same calls are offered to Claude Code as MCP tools by judge_mcp.py.

Usage:
  judge_api.py 稿件 --genre 城市随笔散文 [--task 题目原话] [--model M] [--no-facts] [--own] [--out-dir 目录] [--json]
  judge_api.py 改稿 --genre 课程设计报告 --paper --original 原稿   (/shuozhongwen lunwen)
Exit code 0 = passed.
"""

from __future__ import annotations

import argparse
import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import judge_config  # noqa: E402
import review_zh  # noqa: E402
from doc_text import read_any  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "agents"


def rubric(name: str) -> str:
    """Body of agents/<name>.md without its frontmatter."""
    text = (AGENTS / f"{name}.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.strip()


def _read_reply(r) -> str:
    """The answer text of a chat completion, streamed (server-sent events) or not.
    Reasoning tokens (reasoning_content) are skipped: only the answer counts."""
    if "event-stream" not in (r.headers.get("Content-Type") or ""):
        d = json.load(r)
        return (d.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    parts = []
    for raw in r:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            choice = (json.loads(data).get("choices") or [{}])[0]
        except json.JSONDecodeError:
            continue
        parts.append((choice.get("delta") or {}).get("content") or "")
    return "".join(parts)


def chat(system: str, user: str, model: str, base: str, key: str | None, timeout: int = 900) -> str:
    # Streamed, with no token cap: reasoning models think for minutes before the
    # first answer token, and a silent connection that long gets dropped on the way
    # (RemoteDisconnected); a stream keeps bytes flowing while the model thinks.
    body = {"model": model, "temperature": 0.2, "stream": True,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(), headers=headers)
    attempts = 5
    for attempt in range(attempts):
        wait = 10 * (attempt + 1)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                content = _read_reply(r)
            if content.strip():
                return content
        except urllib.error.HTTPError as error:
            if error.code in (400, 401, 403, 404) or attempt == attempts - 1:
                raise RuntimeError(f"HTTP {error.code}: {error.read()[:300].decode('utf-8', 'replace')}") from None
            if error.code == 429:  # rate or concurrency limit (Ark: InflightBatchsizeExceeded): back off longer
                wait = 30 * (attempt + 1)
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException):
            # dropped connections (RemoteDisconnected) are transient: retry like timeouts
            if attempt == attempts - 1:
                raise
        time.sleep(wait)
    raise RuntimeError(f"{model} returned no answer")


def prompt(role: str, text: str, genre: str = "", original: str = "", task: str = "") -> str:
    if role in ("judge", "lunwen-judge"):
        head = f"文体：{genre}\n\n" + (f"任务：{task}\n\n" if task and role == "judge" else "")
        return f"{head}正文：\n<<<\n{text}\n>>>"
    if role == "factcheck":
        return f"正文：\n<<<\n{text}\n>>>"
    if role == "rigor":
        return f"原稿：\n<<<\n{original}\n>>>\n\n改稿：\n<<<\n{text}\n>>>"
    raise ValueError(role)


def call_role(role: str, text: str, genre: str = "", original: str = "", model: str | None = None,
              task: str = "") -> tuple[str, str]:
    """One fresh, stateless request for one judge role. Returns (model, raw reply)."""
    r = judge_config.resolve(role, model)
    if not r["model"]:
        raise RuntimeError(judge_config.ready(role)[1])
    return r["model"], chat(rubric(role), prompt(role, text, genre, original, task), r["model"], r["base"], r["key"],
                            r["timeout"])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path", help="稿件文件")
    p.add_argument("--genre", required=True, help="文体，如 城市随笔散文、周报、知乎回答")
    p.add_argument("--task", default="", help="任务：用户的题目或要求原话（评委据此判是否偏题）")
    p.add_argument("--model", help="临时指定模型，覆盖配置文件")
    p.add_argument("--no-facts", action="store_true", help="不做事实核查（论文模式本来就不做，外部事实由严谨性审查列给作者）")
    p.add_argument("--own", action="store_true", help="只给题目、没有材料的稿子：事实存疑要改到 0；不加则存疑只列给作者")
    p.add_argument("--paper", action="store_true", help="论文模式：用 lunwen-judge 审语言")
    p.add_argument("--original", help="论文模式：原稿文件，给了就同时跑严谨性审查（agents/rigor.md）")
    p.add_argument("--out-dir", help="审读和核查 JSON 的保存目录，默认与稿件同目录")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    judge_role = "lunwen-judge" if a.paper else "judge"
    ok, why = judge_config.ready(judge_role) if not a.model else (True, "")
    if not ok:
        p.error(why)

    src = Path(a.path)
    text = read_any(src).strip()
    original = read_any(a.original).strip() if a.original else None
    facts_on = not a.no_facts and not a.paper
    out = Path(a.out_dir) if a.out_dir else src.parent
    out.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=3) as ex:
        jr = ex.submit(call_role, judge_role, text, a.genre, "", a.model, a.task)
        fr = ex.submit(call_role, "factcheck", text, "", "", a.model) if facts_on else None
        gr = ex.submit(call_role, "rigor", text, "", original, a.model) if original is not None else None
        model, review_raw = jr.result()
        facts_raw = fr.result()[1] if fr else None
        rigor_raw = gr.result()[1] if gr else None

    (out / f"{src.stem}.review.json").write_text(review_raw, encoding="utf-8")
    if facts_raw is not None:
        (out / f"{src.stem}.facts.json").write_text(facts_raw, encoding="utf-8")
    if rigor_raw is not None:
        (out / f"{src.stem}.rigor.json").write_text(rigor_raw, encoding="utf-8")

    r = review_zh.check_review(text, review_zh.load_json(review_raw), a.genre, paper=a.paper, model=model)
    f = review_zh.check_facts(text, review_zh.load_json(facts_raw), own=a.own) if facts_raw is not None else None
    g = review_zh.check_rigor(original, text, review_zh.load_json(rigor_raw)) if rigor_raw is not None else None
    if a.json:
        print(json.dumps({"model": model, "review": r, "facts": f, "rigor": g}, ensure_ascii=False, indent=1))
    else:
        print(f"评委模型：{model}")
        print(review_zh.report(r, f, g))
    return 0 if r["passed"] and (f is None or f["passed"]) and (g is None or g["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
