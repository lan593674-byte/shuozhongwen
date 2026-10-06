#!/usr/bin/env python3
"""MCP server: the shuozhongwen judges run on an external model.

Claude Code starts it from the plugin's .mcp.json; any MCP client can run it
over stdio (`python judge_mcp.py`). Standard library only.

Every tool call is one brand-new, stateless request to the model configured
in judge_config.py (~/.shuozhongwen/judge.json), carrying only the rubric
(agents/*.md) and the text. The reply is checked with review_zh.py, and the
tool returns both the check report and the raw JSON.

Tools:
  judge            文体 + 正文 → 编辑审读（六项、模板腔），核对证据并判过线
  factcheck        正文 → 事实核查
  lunwen_judge     文体 + 正文 → 论文语言审读
  rigor            原稿 + 改稿 → 学术严谨性审查
  judge_status     当前用哪个接口、哪个模型、密钥找没找到（不显示密钥）
Text can be passed directly (text / original) or as a file path (path / original_path).
"""

from __future__ import annotations

import json
import sys
import threading
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import judge_api  # noqa: E402
import judge_config  # noqa: E402
import review_zh  # noqa: E402
from doc_text import read_any  # noqa: E402

PROTOCOL = "2025-06-18"
_out = threading.Lock()

TEXT_PROPS = {
    "text": {"type": "string", "description": "正文全文（和 path 二选一）"},
    "path": {"type": "string", "description": "稿件文件路径，支持 .txt .md .docx（和 text 二选一）"},
}
TOOLS = [
    {"name": "judge", "description": "用外部模型做 shuozhongwen 编辑审读：全新的一次请求，只带评分标准、文体和正文。返回核对后的结论（证据是否原文、模板腔、是否过线）和原始 JSON。",
     "inputSchema": {"type": "object", "properties": {"genre": {"type": "string", "description": "文体，如 城市随笔散文、课程论坛帖、周报"},
                                                     "task": {"type": "string", "description": "任务：用户的题目或要求原话，评委据此判是否偏题（可选）"},
                                                     **TEXT_PROPS},
                     "required": ["genre"]}},
    {"name": "factcheck", "description": "用外部模型做 shuozhongwen 事实核查：全新的一次请求，只带核查标准和正文全文。",
     "inputSchema": {"type": "object", "properties": {**TEXT_PROPS, "own": {"type": "boolean", "description": "只给题目、没有材料的稿子设为 true：存疑要改到 0"}}}},
    {"name": "lunwen_judge", "description": "用外部模型做 /shuozhongwen lunwen 的论文语言审读。",
     "inputSchema": {"type": "object", "properties": {"genre": {"type": "string"}, **TEXT_PROPS}, "required": ["genre"]}},
    {"name": "rigor", "description": "用外部模型做 /shuozhongwen lunwen 的学术严谨性审查：对照原稿和改稿找退步，列出原稿本身的问题。",
     "inputSchema": {"type": "object", "properties": {
         "original": {"type": "string", "description": "原稿全文"}, "original_path": {"type": "string", "description": "原稿文件路径"},
         **TEXT_PROPS}}},
    {"name": "judge_status", "description": "查看外部评委的配置：接口、各角色用的模型、密钥是否找到（不显示密钥）、配置文件位置。",
     "inputSchema": {"type": "object", "properties": {}}},
]


def _text(args: dict, text_key: str = "text", path_key: str = "path") -> str:
    if args.get(text_key):
        return str(args[text_key]).strip()
    if args.get(path_key):
        return read_any(args[path_key]).strip()
    raise ValueError(f"需要 {text_key} 或 {path_key}")


def run_tool(name: str, args: dict) -> str:
    if name == "judge_status":
        ok, why = judge_config.ready()
        return judge_config.describe() + ("" if ok else "\n" + why)
    role = {"judge": "judge", "factcheck": "factcheck", "lunwen_judge": "lunwen-judge", "rigor": "rigor"}[name]
    ok, why = judge_config.ready(role)
    if not ok:
        raise RuntimeError(why)
    text = _text(args)
    genre = str(args.get("genre", ""))
    original = _text(args, "original", "original_path") if role == "rigor" else ""
    model, raw = judge_api.call_role(role, text, genre, original, task=str(args.get("task", "") or ""))
    data = review_zh.load_json(raw)
    if role in ("judge", "lunwen-judge"):
        r = review_zh.check_review(text, data, genre, paper=role == "lunwen-judge", model=model)
        report = review_zh.report(r, None)
    elif role == "factcheck":
        f = review_zh.check_facts(text, data, own=bool(args.get("own")))
        report = f"事实核查：{f['claims']} 条，存疑 {len(f['doubts'])} 条" + "".join(
            f"\n  存疑：{c.get('text')} —— {c.get('note')}" for c in f["doubts"])
    else:
        g = review_zh.check_rigor(original, text, data)
        report = (f"学术严谨性：退步 {len(g['regressions'])} 处，原稿问题 {len(g['issues'])} 条"
                  + (f"，{g['void']} 条引不出原文已作废" if g["void"] else "")
                  + ("\n结论：通过" if g["passed"] else "\n结论：未通过"))
    return f"评委模型：{model}\n{report}\n\n原始 JSON（原样存成文件，交给 review_zh.py 时用）：\n{json.dumps(data, ensure_ascii=False)}"


def send(msg: dict) -> None:
    with _out:
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def handle(msg: dict) -> None:
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:  # notification
        return
    try:
        if method == "initialize":
            result = {"protocolVersion": params.get("protocolVersion") or PROTOCOL,
                      "capabilities": {"tools": {}},
                      "serverInfo": {"name": "shuozhongwen-judge", "version": "1.0.0"},
                      "instructions": "shuozhongwen 的外部模型评委。每次调用都是一次全新的请求，只带评分标准和正文。"
                                      "接口和模型在 ~/.shuozhongwen/judge.json，用 judge_status 查看。"}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            name = params.get("name")
            if name not in {t["name"] for t in TOOLS}:
                send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool {name}"}})
                return
            try:
                result = {"content": [{"type": "text", "text": run_tool(name, params.get("arguments") or {})}]}
            except Exception as error:  # tool errors go back to the model, not the protocol
                result = {"content": [{"type": "text", "text": f"{type(error).__name__}: {error}"}], "isError": True}
        else:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}})
            return
        send({"jsonrpc": "2.0", "id": mid, "result": result})
    except Exception:
        send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": traceback.format_exc(limit=2)}})


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            continue
        # judge calls take minutes; answer them in parallel so judge and factcheck can run together
        threading.Thread(target=handle, args=(msg,), daemon=False).start()


if __name__ == "__main__":
    main()
