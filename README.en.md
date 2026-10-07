# shuozhongwen · 说中文

[中文](./README.md)

Chinese writing rebuilt around the writing content of [research-writing-skill](https://github.com/Norman-bury/research-writing-skill), pinned at `6f7959554b4614d879d79cb4ece9ed04a7c8a88c`. Its writing rules take precedence over conflicting legacy rules. Fresh evidence-backed scoring, revision, data fidelity and calibrated AI-likeness checks remain.

The three commands remain `/shuozhongwen`, `/shuozhongwen lunwen` (or `/shuozhongwen:lunwen`), and `/shuozhongwen qingli` (or `/shuozhongwen:qingli`). `baozhen` and `xueshu` remain internal constraints.

## Writing scope

Includes planning, task packets, evidence maps, literature synthesis, chapter arguments, humanities/social science, medical and legal writing, results and statistical reporting, translation, information-preserving revision, peer review and revision responses, and LaTeX writing. Drawing, image generation and environment installation are excluded. References are internal documents, not additional skill commands.

De-AI revision does not mean compression. Preserve objects, data scopes, methods, metrics, conditions and conclusion limits. Use natural syntax and continuous paragraphs; useful topic sentences, transitions, citations and chapter numbering remain valid. Scope the workflow to the actual request and honor existing authorization to continue writing.

Keep the six scoring keys and 1–5 scale: literary average at least 4, other writing and academic language at least 3.5, each at least 3. Verify quoted evidence. Structural counts are hints rather than automatic rejection. Revised papers must have zero evidence-backed rigor regressions. Research concerns are reported separately. Each reviewer is fresh; revise at most three rounds.

Fidelity protects facts and meaning, while authorized restructuring and citation-format/number mapping are allowed and recorded. Verified new sources do not silently replace supplied data. Derived values need task authorization and an explicit calculation record. Mock results are planning data only.

qingli, automatic backups, cleanup scripts and display/file-check hooks retain their existing behavior.

## Install

Python 3.10+. Core scripts use only the standard library.

### Claude Code

```bash
claude plugin marketplace add lan593674-byte/shuozhongwen
```

```bash
claude plugin install shuozhongwen@shuozhongwen
```

Then type `/shuozhongwen`. The judge and fact checker are the `shuozhongwen:judge` and `shuozhongwen:factcheck` subagents, running on the same model as your session.

### Codex, Cursor, Gemini CLI and other agents

```bash
git clone https://github.com/lan593674-byte/shuozhongwen.git
```

```bash
python shuozhongwen/install.py codex
```

Replace `codex` with `agents` (`~/.agents/skills`), `cursor`, `gemini`, or pass `--dest DIR`. The script copies the skill and points its paths back to your clone, so keep the clone where it is and re-run after `git pull`. `--uninstall` removes it.

Agents without subagents can use `judge_api.py` below, or ask you to paste the rubric and text into a brand-new chat. The skill forbids the writing session from grading itself.

### Another model as the judge (recommended)

A model grading its own draft is too lenient: it does not see its own habits and tends to reward them. The plugin ships an MCP server (`scripts/judge_mcp.py`, started by Claude Code with the plugin) with the tools `judge`, `compare`, `factcheck`, `lunwen_judge`, `rigor` and `judge_status`. Each call is a fresh request carrying only the rubric, the current task requirements and the text, and the result is already checked by `review_zh.py`. The `/shuozhongwen` workflow uses it first and falls back to subagents when it is not configured.

Endpoint, model and key live in one config file (`~/.shuozhongwen/judge.json`, or wherever `SHUOZHONGWEN_JUDGE_CONFIG` points), so switching APIs means editing one place:

```bash
python scripts/judge_config.py set --base https://api.deepseek.com/v1 --model deepseek-chat --key-env DEEPSEEK_API_KEY
```

```bash
python scripts/judge_config.py test
```

Keys can come from an environment variable (`--key-env`), a .env file (`--key-file PATH:VAR`) or plain text (`--key`, not recommended); they are read at call time and never displayed. `--role factcheck=MODEL` sets a model per role. OpenRouter, Kimi, Qwen, Volcengine Ark and local Ollama all work. Outside Claude Code use the CLI: `python scripts/judge_api.py draft.txt --genre 游记散文`.

## Checks and limitations

Use `scripts/review_zh.py` to validate review evidence, `scripts/polish_check.py` for combined checks, and `scripts/score_zh.py --explain` for calibrated stylometry. Academic review uses `--paper --original ORIGINAL --rigor RIGOR.json`. Preserve raw review JSON and report checks actually run, fidelity results, scores, concerns and unfinished work.

AI-likeness, tier and human percentile are statistical signals, not a commercial detector's AI percentage or plagiarism rate. Insufficient text is not a zero score. Do not optimize away valid information to lower the score. The model and calibration phrase patterns are preserved; historic reviewer calibration is not validation of the revised rubric.

Both Claude Code hooks only inspect files/replies and add display reports. They do not clean files or change conversation history. Use qingli for cleanup. Calibration human corpora remain for personal study/research only, with original copyright and no commercial use.

## Credits and license

Adapted writing content from [research-writing-skill](https://github.com/Norman-bury/research-writing-skill), along with retained components of [haohao-shuohua](https://github.com/Job-Yang/jobyang-ai-skills) and [watermarks-remover](https://github.com/guillaumemeyer/watermarks-remover). See [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md). Released under the [MIT License](./LICENSE).
