#!/usr/bin/env python3
"""Run the shuozhongwen judge and fact check through any OpenAI-compatible API.

For agents without subagents (or when you want a different model than the
writer to judge): each call is a brand-new, stateless request that sees only
the rubric, the genre and the text. The rubric is read from agents/judge.md
and agents/factcheck.md, the same prompts the Claude Code subagents use.

The replies are saved as JSON and checked with review_zh.py (evidence rule,
gate, fact doubts), exactly as in the subagent flow.

Configuration (environment variables):
  SHUOZHONGWEN_API_BASE  default https://api.openai.com/v1
                         e.g. https://api.deepseek.com/v1, https://openrouter.ai/api/v1,
                         http://localhost:11434/v1 (Ollama)
  SHUOZHONGWEN_API_KEY   falls back to OPENAI_API_KEY; not needed for local servers
  SHUOZHONGWEN_MODEL     model name, required unless --model is given

Usage:
  judge_api.py 稿件 --genre 城市随笔散文 [--model M] [--no-facts] [--out-dir 目录] [--json]
Exit code 0 = passed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import review_zh

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "agents"


def rubric(name: str) -> str:
    """Body of agents/<name>.md without its frontmatter."""
    text = (AGENTS / f"{name}.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.strip()


def chat(system: str, user: str, model: str, base: str, key: str | None) -> str:
    body = {"model": model, "temperature": 0.2,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(), headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                d = json.load(r)
            content = (d.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            if content.strip():
                return content
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"{model} returned no answer")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path", help="稿件文件")
    p.add_argument("--genre", required=True, help="文体，如 城市随笔散文、周报、知乎回答")
    p.add_argument("--model", default=os.environ.get("SHUOZHONGWEN_MODEL"))
    p.add_argument("--no-facts", action="store_true", help="不做事实核查")
    p.add_argument("--out-dir", help="审读和核查 JSON 的保存目录，默认与稿件同目录")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    if not a.model:
        p.error("set SHUOZHONGWEN_MODEL or pass --model")
    base = os.environ.get("SHUOZHONGWEN_API_BASE", "https://api.openai.com/v1")
    key = os.environ.get("SHUOZHONGWEN_API_KEY") or os.environ.get("OPENAI_API_KEY")

    src = Path(a.path)
    text = src.read_text(encoding="utf-8").strip()
    out = Path(a.out_dir) if a.out_dir else src.parent
    out.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=2) as ex:
        jr = ex.submit(chat, rubric("judge"), f"文体：{a.genre}\n\n正文：\n<<<\n{text}\n>>>", a.model, base, key)
        fr = None if a.no_facts else ex.submit(chat, rubric("factcheck"), f"正文：\n<<<\n{text}\n>>>", a.model, base, key)
        review_raw = jr.result()
        facts_raw = fr.result() if fr else None

    (out / f"{src.stem}.review.json").write_text(review_raw, encoding="utf-8")
    if facts_raw is not None:
        (out / f"{src.stem}.facts.json").write_text(facts_raw, encoding="utf-8")

    r = review_zh.check_review(text, review_zh.load_json(review_raw), a.genre)
    f = review_zh.check_facts(text, review_zh.load_json(facts_raw)) if facts_raw is not None else None
    if a.json:
        print(json.dumps({"model": a.model, "review": r, "facts": f}, ensure_ascii=False, indent=1))
    else:
        print(f"评委模型：{a.model}")
        print(review_zh.report(r, f))
    return 0 if r["passed"] and (f is None or f["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
