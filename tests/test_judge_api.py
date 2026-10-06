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
            key = ("compare" if "稿子 A：" in user else "judge" if user.startswith("文体：")
                   else "rigor" if user.startswith("原稿：") else "facts")
            content = replies[key](user) if callable(replies[key]) else replies[key]
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
               "SHUOZHONGWEN_API_KEY": "", "OPENAI_API_KEY": "", "PYTHONUTF8": "1",
               "SHUOZHONGWEN_JUDGE_CONFIG": str(tmp_path / "none.json")}
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
               "SHUOZHONGWEN_API_KEY": "", "OPENAI_API_KEY": "", "PYTHONUTF8": "1",
               "SHUOZHONGWEN_JUDGE_CONFIG": str(tmp_path / "none.json")}
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


def test_config_file_picks_model_per_role_and_key_from_dotenv(tmp_path, monkeypatch):
    import judge_config

    env = tmp_path / ".env"
    env.write_text("OTHER=1\nMY_KEY='secret-123'\n", encoding="utf-8")
    cfg = tmp_path / "judge.json"
    cfg.write_text(json.dumps({"api_base": "http://x/v1/", "model": "m-main", "models": {"rigor": "m-rigor"},
                               "api_key_file": {"path": str(env), "var": "MY_KEY"}}), encoding="utf-8")
    for v in ("SHUOZHONGWEN_API_BASE", "SHUOZHONGWEN_MODEL", "SHUOZHONGWEN_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("SHUOZHONGWEN_JUDGE_CONFIG", str(cfg))
    j, r = judge_config.resolve("judge"), judge_config.resolve("rigor")
    assert (j["model"], r["model"], j["base"], j["key"]) == ("m-main", "m-rigor", "http://x/v1", "secret-123")
    assert "secret-123" not in judge_config.describe()
    monkeypatch.setenv("SHUOZHONGWEN_MODEL", "env-model")
    assert judge_config.resolve("rigor")["model"] == "env-model"


def test_mcp_server_lists_tools_and_judges_through_the_configured_model(tmp_path):
    from test_review_zh import QUOTES as Q, TEXT as T, review as rv

    replies = {"judge": json.dumps(rv(4, Q), ensure_ascii=False), "rigor": "{}", "facts": "{}"}
    srv, seen = _serve(replies)
    cfg = tmp_path / "judge.json"
    cfg.write_text(json.dumps({"api_base": f"http://127.0.0.1:{srv.server_port}/v1", "model": "mock"}), encoding="utf-8")
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "judge", "arguments": {"genre": "城市随笔散文", "text": T}}}]
    env = {**__import__("os").environ, "SHUOZHONGWEN_JUDGE_CONFIG": str(cfg), "SHUOZHONGWEN_API_KEY": "", "OPENAI_API_KEY": "",
           "SHUOZHONGWEN_API_BASE": "", "SHUOZHONGWEN_MODEL": ""}
    try:
        p = subprocess.run([sys.executable, str(SCRIPT.parent / "judge_mcp.py")], input="\n".join(json.dumps(m, ensure_ascii=False) for m in msgs) + "\n",
                           capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
    finally:
        srv.shutdown()
    out = {d["id"]: d for d in map(json.loads, p.stdout.splitlines())}
    assert {t["name"] for t in out[2]["result"]["tools"]} == {"judge", "factcheck", "lunwen_judge", "rigor", "compare",
                                                             "judge_status"}
    text = out[3]["result"]["content"][0]["text"]
    assert "评委模型：mock" in text and "结论：通过" in text
    assert len(seen) == 1 and len(seen[0]["messages"]) == 2  # one fresh request, rubric + text only


def test_judge_prompt_carries_the_task_only_when_given():
    import judge_api
    with_task = judge_api.prompt("judge", "正文内容", "课程论坛帖（说明文）", task="介绍亚北极的普遍描述，并对比克里人")
    assert with_task.startswith("文体：课程论坛帖（说明文）\n\n任务：介绍亚北极的普遍描述，并对比克里人\n\n正文：")
    assert "任务" not in judge_api.prompt("judge", "正文内容", "周报")
    assert "任务" not in judge_api.prompt("lunwen-judge", "正文内容", "课程设计报告", task="改语言")


def test_chat_retries_a_dropped_connection(monkeypatch):
    import socket
    calls = {"n": 0}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            calls["n"] += 1
            if calls["n"] == 1:  # close without answering: RemoteDisconnected on the client
                self.close_connection = True
                self.connection.shutdown(socket.SHUT_RDWR)
                return
            body = json.dumps({"choices": [{"message": {"content": "收到"}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(judge_api.time, "sleep", lambda s: None)
    try:
        assert judge_api.chat("s", "u", "m", f"http://127.0.0.1:{srv.server_port}/v1", None, timeout=10) == "收到"
    finally:
        srv.shutdown()
    assert calls["n"] == 2


def test_chat_reads_a_streamed_reply_and_skips_reasoning():
    events = [{"choices": [{"delta": {"reasoning_content": "先想一想"}}]},
              {"choices": [{"delta": {"content": "{\"a\": "}}]},
              {"choices": [{"delta": {"content": "1}"}}]}]

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body["stream"] is True and "max_tokens" not in body
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for e in events:
                self.wfile.write(("data: " + json.dumps(e, ensure_ascii=False) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert judge_api.chat("s", "u", "m", f"http://127.0.0.1:{srv.server_port}/v1", None, timeout=10) == '{"a": 1}'
    finally:
        srv.shutdown()


def test_chat_backs_off_on_a_rate_limit(monkeypatch):
    calls, waits = {"n": 0}, []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            calls["n"] += 1
            if calls["n"] <= 2:
                self.send_response(429)
                self.end_headers()
                self.wfile.write(b'{"error": {"code": "InflightBatchsizeExceeded"}}')
                return
            body = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(judge_api.time, "sleep", waits.append)
    try:
        assert judge_api.chat("s", "u", "m", f"http://127.0.0.1:{srv.server_port}/v1", None, timeout=10) == "ok"
    finally:
        srv.shutdown()
    assert calls["n"] == 3 and waits == [30, 60]


def test_compare_prompt_puts_text_in_a_and_original_in_b():
    p = judge_api.prompt("compare", "甲稿正文", "短篇小说", "乙稿正文", task="写末班公交车")
    assert p.startswith("文体：短篇小说\n\n任务：写末班公交车\n\n稿子 A：")
    assert p.index("甲稿正文") < p.index("稿子 B：") < p.index("乙稿正文")
    assert "verdict" not in judge_api.rubric("compare") and "better" in judge_api.rubric("compare")


def _cli_compare(tmp_path, picks_new: bool):
    new, base = tmp_path / "新稿.txt", tmp_path / "原稿.txt"
    new.write_text("新稿：司机把电池放在后门边，一路看着后视镜。", encoding="utf-8")
    base.write_text("原稿：司机让他上了车，心里有些不安。", encoding="utf-8")

    def pick(user):
        a = user.split("稿子 A：", 1)[1].split("稿子 B：", 1)[0]
        new_is_a = "新稿：" in a
        better = ("A" if new_is_a else "B") if picks_new else ("B" if new_is_a else "A")
        return json.dumps({"better": better, "margin": "略微", "reason": "细节更实"}, ensure_ascii=False)

    srv, seen = _serve({"compare": pick})
    try:
        env = {**__import__("os").environ, "SHUOZHONGWEN_API_BASE": f"http://127.0.0.1:{srv.server_port}/v1",
               "SHUOZHONGWEN_API_KEY": "", "OPENAI_API_KEY": "", "PYTHONUTF8": "1",
               "SHUOZHONGWEN_JUDGE_CONFIG": str(tmp_path / "none.json")}
        r = subprocess.run([sys.executable, str(SCRIPT), str(new), "--compare", str(base), "--genre", "短篇小说",
                            "--task", "写末班公交车", "--model", "mock", "--json"],
                           capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
    finally:
        srv.shutdown()
    return r, seen


def test_compare_replaces_only_when_the_new_draft_wins_both_orders(tmp_path):
    r, seen = _cli_compare(tmp_path, picks_new=True)
    assert r.returncode == 0, r.stdout + r.stderr
    c = json.loads(r.stdout)["compare"]
    assert c["replace"] and [v["winner"] for v in c["votes"]] == ["new", "new"]
    # two fresh requests, one per order, each with the compare rubric and both drafts only
    assert len(seen) == 2 and all(len(b["messages"]) == 2 for b in seen)
    firsts = sorted(b["messages"][1]["content"].split("稿子 A：", 1)[1][:8] for b in seen)
    assert any("新稿" in f for f in firsts) and any("原稿" in f for f in firsts)
    assert (tmp_path / "新稿.compare1.json").exists() and (tmp_path / "新稿.compare2.json").exists()

    r, _ = _cli_compare(tmp_path, picks_new=False)
    assert r.returncode == 1 and not json.loads(r.stdout)["compare"]["replace"]
