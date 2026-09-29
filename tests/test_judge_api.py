"""judge_api: rubric loading and a full run against a local mock OpenAI-compatible server."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import judge_api
from test_review_zh import QUOTES, TEXT, review

SCRIPT = Path(judge_api.__file__)


def test_rubric_strips_frontmatter():
    body = judge_api.rubric("judge")
    assert not body.startswith("---") and "证据规则" in body
    assert "verdict" in judge_api.rubric("factcheck")


def _serve(replies):
    seen = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(body)
            user = body["messages"][-1]["content"]
            key = "judge" if user.startswith("文体：") else "rigor" if user.startswith("原稿：") else "facts"
            content = replies[key]
            out = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, seen


def test_end_to_end_with_mock_server(tmp_path):
    draft = tmp_path / "稿.txt"
    draft.write_text(TEXT, encoding="utf-8")
    replies = {"judge": "```json\n" + json.dumps(review(4, QUOTES), ensure_ascii=False) + "\n```",
               "facts": json.dumps({"claims": [{"text": "一三四九年的地震", "verdict": "ok"}]}, ensure_ascii=False)}
    srv, seen = _serve(replies)
    try:
        env = {**__import__("os").environ, "SHUOZHONGWEN_API_BASE": f"http://127.0.0.1:{srv.server_port}/v1",
               "SHUOZHONGWEN_API_KEY": "", "OPENAI_API_KEY": "", "PYTHONUTF8": "1"}
        r = subprocess.run([sys.executable, str(SCRIPT), str(draft), "--genre", "城市随笔散文", "--model", "mock", "--json"],
                           capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
    finally:
        srv.shutdown()
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout)["review"]["passed"]
    assert (tmp_path / "稿.review.json").exists() and (tmp_path / "稿.facts.json").exists()
    # each request is stateless: only the rubric and the text, nothing else
    assert len(seen) == 2 and all(len(b["messages"]) == 2 for b in seen)


def test_paper_mode_runs_lunwen_judge_and_rigor(tmp_path):
    import review_zh
    from test_review_zh import PAPER_ORIG, PAPER_REV

    orig, rev = tmp_path / "原稿.txt", tmp_path / "改稿.txt"
    orig.write_text(PAPER_ORIG, encoding="utf-8")
    rev.write_text(PAPER_REV, encoding="utf-8")
    quotes = ["随机森林表现最好，原因在于数据的规模", "线性模型无法有效捕捉票房数据中的非线性关系"] * 3
    judge = {"scores": {k: {"score": 4, "evidence": q, "fix": ""} for (k, _), q in zip(review_zh.PAPER_DIMENSIONS, quotes)}}
    rigor = {"regressions": [{"original": "这可能与数据的规模和特征的尺度有关", "revised": "原因在于数据的规模和特征的尺度",
                              "type": "模态", "note": "推测改成了结论"}], "issues": []}
    replies = {"judge": json.dumps(judge, ensure_ascii=False), "rigor": json.dumps(rigor, ensure_ascii=False), "facts": "{}"}
    srv, seen = _serve(replies)
    try:
        env = {**__import__("os").environ, "SHUOZHONGWEN_API_BASE": f"http://127.0.0.1:{srv.server_port}/v1",
               "SHUOZHONGWEN_API_KEY": "", "OPENAI_API_KEY": "", "PYTHONUTF8": "1"}
        r = subprocess.run([sys.executable, str(SCRIPT), str(rev), "--genre", "课程设计报告", "--paper",
                            "--original", str(orig), "--model", "mock", "--json"],
                           capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
    finally:
        srv.shutdown()
    out = json.loads(r.stdout)
    assert r.returncode == 1 and out["review"]["passed"] and not out["rigor"]["passed"]
    assert out["facts"] is None and len(seen) == 2  # paper mode: no literary fact check
    systems = [b["messages"][0]["content"] for b in seen]
    assert any("学术期刊语言编辑" in x for x in systems) and any("审稿人" in x for x in systems)
