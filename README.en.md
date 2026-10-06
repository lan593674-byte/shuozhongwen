# shuozhongwen · 说中文 ("Speak Chinese")

[中文](./README.md)

A Chinese-writing plugin for AI agents. It writes or revises a Chinese article with three goals at once: **keep the facts intact, lose the machine-translated "AI tone", and actually write well**.

Stripping AI tells alone tends to leave flat, lifeless prose. A weak first draft is rarely a sentence-level problem either: the writer had no concrete material and no clear point, so templates and stock phrases filled the space. This plugin therefore gathers material and outlines before drafting; only after the draft is written does it scan for templates and hand the text to a **fresh judge** that must back every score with a verbatim quote from the text (a score it cannot quote is void); it revises from that evidence with a new judge each round and stops once the bar is met; literary pieces then get one polishing round, kept only if a blind comparison prefers it in both orders. The statistical "AI-likeness" score is a guardrail, never a target.

Works as a full Claude Code plugin (subagents and hooks included) and as an Agent Skill for Codex, Cursor, Gemini CLI and other agents. The judge can be any model behind an OpenAI-compatible API.

## How it works

Type `/shuozhongwen <topic or path to draft>`:

1. **Genre and standard**: practical text (reports, notices, plans) must be accurate and concise; argument must hold up; literary writing (essays, travel writing, fiction, reviews) must be good writing. The genre follows what the task asks for and sets the pass bar.
2. **Prepare before writing**: restate the task (reader, what to cover, length); gather material: when revising or writing from your material, a data ledger first (numbers, names, terms, citations, causal directions), used verbatim; with only a topic, research first; for pieces that rest on your own experience (travel writing, memoir) it asks you three to five concrete questions instead of inventing. Then one sentence on what the reader should come away with, and a one-line-per-paragraph outline in which each line starts from the fact that opens the paragraph; for expository text, a check that the task's core question gets a direct answer and no link in the chain is missing. Parts the genre always carries (a title for forum posts and articles, salutation and sign-off for letters) are included.
3. **Draft** from the outline: one thing per paragraph, facts and details first, judgement after them, straight into the subject; the ending lands on the task's core question instead of opening a new topic. Attention goes to content; template checks come after the draft.
4. **Self-check**: `polish_check.py` (invisible characters, four mechanical scans, structural templates, AI-likeness), then reread against the outline and the data ledger.
5. **Editorial review and fact check** by two fresh judges that see only the genre, the task, the text and the rubric. Six dimensions: concrete detail, insight (selection, for expository text), language and imagery, rhythm, structure and tension, voice; plus whether the text is off task.
6. **Revise from evidence**: `review_zh.py` verifies each quote is verbatim and applies the bar. The weak paragraph is rewritten from the outline; missing material is asked for or researched, never faked with manufactured verdicts, aphorisms or rhetorical questions. A new judge re-reviews; at most three rounds. When only the length falls short because the material cannot fill it, the text is not padded and the length is a reminder, not a failure.
7. **Polish** (literary only): one more round on a copy after passing, adding unused details from the material and cutting sentences that explain characters' thoughts; a fresh compare judge sees both drafts in both orders, and the new one is delivered only if it wins both and passes review again.
8. **Deliver** the text, then a line `【修改报告】` and the revision report.

Pass bar: literary genres average ≥ 4 with every dimension ≥ 3; practical and argument texts average ≥ 3.5 with every dimension ≥ 3; not flat; not off task; at most one AI template the judge can quote (strings of short verdict openers, announcing sentences, wrap-up formulas, scare quotes, invented first-person experience, preambles about sources). Rhetorical questions, one-line paragraphs and callbacks are common in human prose and are only flagged, never blocking (see `calibration/TEMPLATE_AUDIT.md`). Zero doubtful facts for a piece written from a bare topic.

### Data fidelity (enforced when revising a draft or writing from your material)

Before revising a draft, or writing a new piece from material you provide, the plugin loads the `baozhen` constraint skill. When writing from material, not every figure has to be used, but whatever is used is copied exactly: no rounding, no conversions, no new numbers derived from it, and nothing filled in from the web. In both cases numbers, tables, citations and references, terms, hedges such as "possibly" or "mainly", causal direction and claims are never changed or invented, and when revising, never removed. A figure that looks wrong, even one the fact checker flags, only goes into the "for the author to check" list of the report.

### Clean invisible characters and garbled text: `/shuozhongwen qingli`

`/shuozhongwen qingli PATH` (or `/shuozhongwen:qingli`) finds and removes zero-width and other invisible characters and garbled text (U+FFFD, control characters, 锟斤拷/烫烫烫, and mojibake such as 涓枃 or Ã©, restored to the original characters when possible) in files, folders, Office/EPUB documents or pasted text. Spaces, line endings, encoding and document formatting are left alone; originals are backed up first. The report lists what was removed and where, and which spots lost characters the author must restore. CLI: `python scripts/qingli.py PATH [--check]`.

### Papers: `/shuozhongwen lunwen`

In Claude Code it is also a standalone command, `/shuozhongwen:lunwen`, listed in the plugin menu.

For academic papers, theses, course-project and lab reports: only the language changes, never the research. AI tells are removed while keeping formal academic register (no colloquialisms, no metaphors); numbering, tables, formulas, citations and references stay as they are. A dedicated academic language judge (`lunwen-judge`) scores accuracy, concision, register, coherence, consistency and template-free prose (average ≥ 3.5, each ≥ 3). The academic rigor review skill `xueshu`, active only in this mode, runs a fresh reviewer (`rigor`) over the original and the revision: any loss of rigor (data, hedges, causality, claims, terms, citations, register) must be zero, and problems in the original itself are listed for the author, not fixed. The report includes a sentence-by-sentence change table.

## Install

Python 3.10+. Core scripts use only the standard library.

### Claude Code

```bash
claude plugin marketplace add lan593674-byte/shuozhongwen
```

```bash
claude plugin install shuozhongwen@shuozhongwen
```

Then type `/shuozhongwen`. The judge, fact checker and compare judge are the `shuozhongwen:judge`, `shuozhongwen:factcheck` and `shuozhongwen:compare` subagents, running on the same model as your session.

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

A model grading its own draft is too lenient: it does not see its own habits and tends to reward them. The plugin ships an MCP server (`scripts/judge_mcp.py`, started by Claude Code with the plugin) with the tools `judge`, `factcheck`, `lunwen_judge`, `rigor`, `compare` and `judge_status`. Each call is a fresh request carrying only the rubric and the text, and the result is already checked by `review_zh.py`. The `/shuozhongwen` workflow uses it first and falls back to subagents when it is not configured.

Endpoint, model and key live in one config file (`~/.shuozhongwen/judge.json`, or wherever `SHUOZHONGWEN_JUDGE_CONFIG` points), so switching APIs means editing one place:

```bash
python scripts/judge_config.py set --base https://api.deepseek.com/v1 --model deepseek-chat --key-env DEEPSEEK_API_KEY
```

```bash
python scripts/judge_config.py test
```

Keys can come from an environment variable (`--key-env`), a .env file (`--key-file PATH:VAR`) or plain text (`--key`, not recommended); they are read at call time and never displayed. `--role factcheck=MODEL` sets a model per role. OpenRouter, Kimi, Qwen, Volcengine Ark and local Ollama all work. Outside Claude Code use the CLI: `python scripts/judge_api.py draft.txt --genre 游记散文`.

## Standalone tools

| Command | What it does |
|---|---|
| `python scripts/score_zh.py FILE --explain` | AI-likeness score with human-percentile and feature breakdown |
| `python scripts/haohao_scan.py FILE` | Mechanical scans: section numbering, meta-commentary, half-width punctuation, "not X but Y" |
| `python scripts/polish_check.py FILE` | Delivery gate: the above plus invisible characters; `--paper` skips the numbering scan, reference lists are exempt from the punctuation scan |
| `python scripts/doc_text.py FILE.docx -o FILE.txt` | Extract the text and tables of a .docx |
| `python scripts/review_zh.py FILE --genre G --review review.json` | Verify a judge's JSON and apply the bar (no model call) |
| `python scripts/clean_text.py FILE -o OUT --stats` | Strip zero-width and other invisible characters |
| `python scripts/inspect_file.py FILE` | Report provenance metadata (C2PA, EXIF/XMP, Office properties, ...) |
| `python scripts/clean_file.py FILE -o OUT` | Strip it: PNG, JPEG, WebP, SVG, PDF, DOCX, XLSX, PPTX, EPUB, HTML, Markdown, MP4 and more |

## Claude Code hooks

Both hooks only check; they never modify a file or a reply.

- **After a file write** (PostToolUse): checks the file Claude just wrote for invisible characters, garbled text and provenance metadata, and records the result (no pop-up).
- **Before a reply is shown** (MessageDisplay): every reply, however short, ends with a check line: invisible characters or garbled text in the reply and in files written meanwhile. Replies of 250+ characters also get an AI-likeness line above it (the statistics are unreliable on shorter text); for a delivery only the article before `【修改报告】` is scored, because the report's lists alone push any article into the high tier. Display only; the transcript is untouched.

Environment: `SHUOZHONGWEN_SCORE=0` turns the score line off, `SHUOZHONGWEN_SCORE_MIN` sets the minimum length, `SHUOZHONGWEN_CHECK=0` turns the check line off, `SHUOZHONGWEN_LOG_DIR` sets the log folder (counts and scores only, never reply text).

## About the AI-likeness score

A sign-constrained logistic regression over 19 Chinese stylometric features (sentence and paragraph length variation, connective density, ellipses and exclamations, pronoun and particle density, bigram repetition, stock-phrase markers, ...). Calibrated on 62 human texts (classics, Tieba long posts, free chapters of web novels, all hand-reviewed) and 101 texts from 8 models.

- The `high` threshold is fixed at 0.6 (about the human 90th percentile). Per article, 89% of the AI calibration texts reach it and 3% of human texts are misflagged; 1 of the 49 held-out human texts.
- Leave-one-model-out (per chunk): 57%–94% caught per unseen model.
- Held-out human text (per chunk): 6% misflagged for colloquial forum posts, 10% for web fiction.

It only says whether the statistics resemble the AI texts in the calibration set. It is not a verdict of any commercial detector and not a detector-evasion tool; inside the workflow it is only a guardrail. The human calibration corpus is included in `calibration/human/` and `calibration/test/` **for personal study and research only, no commercial use**; copyright stays with the original authors and platforms and the MIT license does not cover it (see `calibration/corpus/README.md`).

## Credits and license

Adapted from two MIT-licensed projects: [haohao-shuohua](https://github.com/Job-Yang/jobyang-ai-skills) by Job-Yang and [watermarks-remover](https://github.com/guillaumemeyer/watermarks-remover) by Guillaume Meyer. See [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md).

Released under the [MIT License](./LICENSE).
