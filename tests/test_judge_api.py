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
            content = replies["judge"] if user.startswith("文体：") else replies["facts"]
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
