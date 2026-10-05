#!/usr/bin/env python3
"""Where the external judge model lives: one config file, so the API can change in one place.

Used by judge_api.py (command line) and judge_mcp.py (MCP server). Any
OpenAI-compatible chat endpoint works: DeepSeek, Kimi, Qwen, Volcengine Ark,
OpenRouter, a local Ollama ...

Config file: SHUOZHONGWEN_JUDGE_CONFIG, default ~/.shuozhongwen/judge.json

    {
      "api_base": "https://ark.cn-beijing.volces.com/api/plan/v3",
      "model": "kimi-k3",
      "models": {"factcheck": "deepseek-v4.1-flash"},       optional, per role
      "api_key_env": "ARK_API_KEY",                          one of these three
      "api_key_file": {"path": "D:/x/.env", "var": "KEY"},   reads KEY=... from a .env file
      "api_key": "sk-...",                                   plain text, least safe
      "timeout": 900
    }

Roles: judge, factcheck, lunwen-judge, rigor. Environment variables
SHUOZHONGWEN_API_BASE, SHUOZHONGWEN_MODEL and SHUOZHONGWEN_API_KEY (or
OPENAI_API_KEY) override the file. The key is read when a call is made and is
never printed.

Usage:
  judge_config.py show
  judge_config.py set --base URL --model NAME [--role factcheck=NAME ...] [--clear-roles]
                      [--key-env VAR | --key-file PATH:VAR | --key KEY] [--timeout S]
  judge_config.py test [--role judge]      one tiny request to check the setup
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROLES = ("judge", "factcheck", "lunwen-judge", "rigor")
DEFAULT_TIMEOUT = 900


def config_path() -> Path:
    return Path(os.environ.get("SHUOZHONGWEN_JUDGE_CONFIG") or Path.home() / ".shuozhongwen" / "judge.json")


def load() -> dict:
    p = config_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _dotenv(path: str, var: str) -> str | None:
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            if line.startswith(var + "="):
                return line.split("=", 1)[1].strip().strip("\"'")
    except OSError:
        return None
    return None


def api_key(cfg: dict | None = None) -> str | None:
    cfg = load() if cfg is None else cfg
    for env in ("SHUOZHONGWEN_API_KEY", "OPENAI_API_KEY"):
        if os.environ.get(env):
            return os.environ[env]
    if cfg.get("api_key_env") and os.environ.get(cfg["api_key_env"]):
        return os.environ[cfg["api_key_env"]]
    kf = cfg.get("api_key_file")
    if isinstance(kf, dict) and kf.get("path") and kf.get("var"):
        key = _dotenv(kf["path"], kf["var"])
        if key:
            return key
    return cfg.get("api_key") or None


def resolve(role: str = "judge", model: str | None = None) -> dict:
    """{"base", "model", "key", "timeout", "source"} for one role; key may be None (local servers)."""
    cfg = load()
    base = os.environ.get("SHUOZHONGWEN_API_BASE") or cfg.get("api_base") or "https://api.openai.com/v1"
    chosen = (model or os.environ.get("SHUOZHONGWEN_MODEL")
              or (cfg.get("models") or {}).get(role) or cfg.get("model"))
    return {"base": base.rstrip("/"), "model": chosen, "key": api_key(cfg),
            "timeout": int(cfg.get("timeout") or DEFAULT_TIMEOUT),
            "source": str(config_path()) if cfg else "environment"}


def describe() -> str:
    cfg = load()
    lines = [f"配置文件：{config_path()}（{'存在' if cfg else '不存在'}）"]
    for role in ROLES:
        r = resolve(role)
        lines.append(f"  {role}：{r['model'] or '（未设置模型）'} @ {r['base']}")
    key = api_key(cfg)
    how = ("环境变量" if any(os.environ.get(v) for v in ("SHUOZHONGWEN_API_KEY", "OPENAI_API_KEY")) else
           f"环境变量 {cfg['api_key_env']}" if cfg.get("api_key_env") and os.environ.get(cfg["api_key_env"]) else
           f"{cfg['api_key_file'].get('path')} 里的 {cfg['api_key_file'].get('var')}" if isinstance(cfg.get("api_key_file"), dict) and key else
           "配置文件明文" if cfg.get("api_key") else "")
    lines.append(f"  密钥：{'已找到（' + how + '）' if key else '没找到（本地模型可以不要密钥）'}")
    lines.append(f"  超时：{resolve()['timeout']} 秒")
    return "\n".join(lines)


def ready(role: str = "judge") -> tuple[bool, str]:
    r = resolve(role)
    if not r["model"]:
        return False, "还没配置评委模型。运行 judge_config.py set --base 接口地址 --model 模型名 --key-env 环境变量名"
    return True, ""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    s = sub.add_parser("set")
    s.add_argument("--base")
    s.add_argument("--model")
    s.add_argument("--role", action="append", default=[], help="角色=模型，如 factcheck=deepseek-v4.1-flash")
    s.add_argument("--clear-roles", action="store_true", help="去掉所有按角色单独指定的模型，全部用 --model")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--key-env", help="从这个环境变量读密钥")
    g.add_argument("--key-file", help="从 .env 文件读密钥，格式 路径:变量名")
    g.add_argument("--key", help="把密钥明文写进配置文件（不推荐）")
    s.add_argument("--timeout", type=int)
    t = sub.add_parser("test")
    t.add_argument("--role", default="judge")
    a = p.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if a.cmd == "show":
        print(describe())
        return 0
    if a.cmd == "set":
        cfg = load()
        if a.base:
            cfg["api_base"] = a.base
        if a.model:
            cfg["model"] = a.model
        if a.clear_roles:
            cfg.pop("models", None)
        for item in a.role:
            role, _, name = item.partition("=")
            if role not in ROLES or not name:
                p.error(f"--role 要写成 角色=模型，角色是 {', '.join(ROLES)}")
            cfg.setdefault("models", {})[role] = name
        if a.key_env or a.key_file or a.key:
            for k in ("api_key_env", "api_key_file", "api_key"):
                cfg.pop(k, None)
        if a.key_env:
            cfg["api_key_env"] = a.key_env
        if a.key_file:
            path, _, var = a.key_file.rpartition(":")
            if not path or not var:
                p.error("--key-file 要写成 路径:变量名")
            cfg["api_key_file"] = {"path": path, "var": var}
        if a.key:
            cfg["api_key"] = a.key
        if a.timeout:
            cfg["timeout"] = a.timeout
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(describe())
        return 0
    ok, why = ready(a.role)
    if not ok:
        print(why)
        return 1
    from judge_api import chat

    r = resolve(a.role)
    try:
        reply = chat("只回复两个字：收到", "测试", r["model"], r["base"], r["key"], timeout=min(r["timeout"], 120))
    except Exception as error:  # report, never show the key
        print(f"调用失败：{type(error).__name__}: {error}")
        return 1
    print(f"{a.role} 用 {r['model']} 调用成功，回复：{reply.strip()[:40]}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
