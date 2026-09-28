# shuozhongwen · 说中文

[English](./README.en.md)

一个给 AI agent 用的中文写作插件：写或改一篇中文文章，要同时做到三件事——**事实不动、没有 AI 腔、写得好**。

只做减法去 AI 味，结果往往是白开水：套话删光了，文章也没了。这个插件换了个顺序：先认文体、定下这篇要写的“发现”和主线，再动笔；写完交给一个**全新的评委**审读，评委每一条判断都必须引原文作证据，引不出来的分数作废；没过线就按证据改，换新评委再审，过线就停。统计意义上的“AI 相似度”只当护栏，不当目标。

支持 Claude Code（完整插件，含子代理和钩子），也能装进 Codex、Cursor、Gemini CLI 等支持 Agent Skills 的 agent；评委可以用任何兼容 OpenAI 接口的模型。

## 它怎么工作

输入 `/shuozhongwen 题目或稿件路径`，按七步走：

1. **认文体，定标准**：实用文本（周报、通知、方案）要准确简洁；议论文字要观点立得住；文学性文字（散文、游记、小说、书评）要写得好。文体决定后面的过线标准。
2. **定主线和发现，锁事实**：改别人的稿子，先列事实账本（数字、专名、术语、因果方向等 8 项），一个字不动；原文没有的细节一律不编，列进“建议作者补充”。
3. **写或改**：从含义出发整篇写，删掉的套话要换成具体细节。
4. **编辑审读和事实核查**：两个全新的子代理并行，只看到文体、正文和评分标准，看不到改稿经过和上一轮评语。评委按六项打分：具体可感、自己的发现、语言与意象、节奏、结构与张力、声音。
5. **按证据改**：`review_zh.py` 逐项核对评委引的证据是不是原文原句，再判是否过线。没过就照最弱项的改法改，改完换新评委，最多三轮。
6. **过硬闸**：`polish_check.py` 查不可见字符、四条机械扫描（章节编号、元话语、半角标点、“不是 X 而是 Y”）和 AI 相似度。
7. **交稿**：正文加一份修改报告。

过线标准：文学性文字六项平均 ≥ 4、每项 ≥ 3；实用和议论文字平均 ≥ 3.5、每项 ≥ 3；不是白开水；事实存疑为 0。

## 安装

需要 Python 3.10 以上。核心脚本只用标准库，不用装依赖。

### Claude Code

```bash
claude plugin marketplace add lan593674-byte/shuozhongwen
```

```bash
claude plugin install shuozhongwen@shuozhongwen
```

也可以在 Claude Code 里用 `/plugin` 菜单添加。装好后输入 `/shuozhongwen` 使用，评委和事实核查是 `shuozhongwen:judge`、`shuozhongwen:factcheck` 两个子代理，跟当前会话用同一个模型。

### Codex、Cursor、Gemini CLI 等其他 agent

```bash
git clone https://github.com/lan593674-byte/shuozhongwen.git
```

```bash
python shuozhongwen/install.py codex
```

`codex` 可以换成 `agents`（`~/.agents/skills`）、`cursor`、`gemini`，或者用 `--dest 目录` 指定任意 skills 目录。脚本会把技能复制过去，并把里面的路径指回你 clone 的仓库，所以装完仓库别挪地方；`git pull` 之后重跑一次。卸载加 `--uninstall`。

没有子代理的 agent，评委有两种办法：用下面的 `judge_api.py` 调一个模型，或者让你在一个全新的对话里贴评分标准和正文。技能里写明了不允许在当前会话里自己给自己打分。

### 用别的模型当评委

`scripts/judge_api.py` 通过任意兼容 OpenAI 接口的服务调用评委，每次都是无状态的新请求，提示词直接读 `agents/judge.md`、`agents/factcheck.md`，和子代理用的是同一份。

```bash
export SHUOZHONGWEN_API_BASE=https://api.deepseek.com/v1
export SHUOZHONGWEN_API_KEY=你的密钥
export SHUOZHONGWEN_MODEL=deepseek-chat
python scripts/judge_api.py 稿件.txt --genre 游记散文
```

OpenRouter、Kimi、通义、火山方舟、本地 Ollama（`http://localhost:11434/v1`）都可以。特意让一个和写作者不同的模型当评委，可以减少“自己给自己打高分”的偏差。

## 单独使用的工具

| 命令 | 作用 |
|---|---|
| `python scripts/score_zh.py 稿件 --explain` | AI 相似度，附“比多少人类段落更像 AI”和各项特征 |
| `python scripts/haohao_scan.py 稿件` | 机械扫描：章节编号、元话语、半角标点、“不是 X 而是 Y” |
| `python scripts/polish_check.py 稿件` | 交付硬闸，上面两项加不可见字符 |
| `python scripts/review_zh.py 稿件 --genre 文体 --review 审读.json` | 核对评委 JSON 的证据并判是否过线，不调用模型 |
| `python scripts/clean_text.py 稿件 -o 输出 --stats` | 清掉零宽字符等不可见字符 |
| `python scripts/inspect_file.py 文件` | 检查文件里的来源元数据（C2PA、EXIF/XMP、Office 属性等） |
| `python scripts/clean_file.py 文件 -o 输出` | 清理这些元数据，支持 PNG、JPEG、WebP、SVG、PDF、DOCX、XLSX、PPTX、EPUB、HTML、Markdown、MP4 等 |

Windows 上把 `python3`/`python` 换成你机器上的 Python 命令即可，建议加 `-X utf8`。

## Claude Code 里的两个钩子

装了插件后，这两个钩子一直生效，与 `/shuozhongwen` 无关：

- **写文件后**（PostToolUse）：检查 Claude 刚写的文件里有没有不可见字符和来源元数据。默认只报告；在插件选项里把 `hook_mode` 设成 `clean` 就直接清理。
- **显示回复前**（MessageDisplay）：清掉回复里的不可见字符；250 字以上的回复末尾附一行 AI 相似度。只改显示，不改会话记录。

| 环境变量 | 作用 |
|---|---|
| `SHUOZHONGWEN_SCORE=0` | 关掉回复末尾的评分行 |
| `SHUOZHONGWEN_SCORE_MIN` | 评分的最短字数，默认 250 |
| `SHUOZHONGWEN_LOG_DIR` | 钩子日志目录，默认插件目录下的 `logs/`；只记计数和分数，不记回复原文 |
| `WATERMARKS_HOOK_MODE` | 不通过插件选项时设置写文件钩子的模式（`check`/`clean`） |

## AI 相似度是怎么来的，能说明什么

`score_zh.py` 是一个带符号约束的逻辑回归，看 19 项中文文体统计：句长和段长的起伏、连接词密度、省略号和感叹号、“我们”“的”的密度、双字词重复度、套话标记等。校准用了 339 篇人类文字（经典名作、2020 年以前的知乎高赞回答和贴吧长帖、起点网文免费章节，全部人工审过，剔除营销和搬运）和 8 个模型生成的 101 篇文字。

- 分组交叉验证：`high` 档阈值定在人类段落的第 95 百分位，AI 段落命中 66%，人类段落误判 5%。
- 留一模型检验（该模型的样本完全不参与训练）：各模型命中 47%–81%。
- 留出测试：贴吧口语长帖误判 0%，网络小说误判 4%。

详见 `calibration/RESULTS.md`、`calibration/TEST_RESULTS.md`。

**它只说明统计信号像不像校准集里的 AI 文本**，不代表任何商业检测器的结论，也不是用来“骗过检测”的。插件里它只是护栏：落在人类的常见区间就算过，不为了压分去改文章，因为压分最省事的办法（堆重复词、乱加标点）只会把文章改坏。

评委的有效性检验见 `calibration/REVIEW_VALIDATION.md`：经典名作平均 4.4–4.6 分，知乎高赞约 3 分，一篇被改成白开水的罗马游记 2 分左右并被判为白开水，改好的版本 4 分以上。

## 已知局限

- 评委和写作者是同一个模型时，存在自我偏好的可能；全新子代理只去掉了上下文干扰。在意的话用 `judge_api.py` 换一个模型当评委。
- 评分是伪精确：用的是评委的证据和改法，分数只是门槛。过线就停，不为刷分再改。
- AI 相似度对“被要求写得自然一点”的 AI 文本明显更难认出；对公文等没进校准集的文体，误判率未知。
- 校准用的人类语料有版权，**不随仓库分发**。`calibration/` 里有抓取和导入脚本，自己准备语料后运行 `python calibration/calibrate.py` 可以重新校准。

## 目录

```
.claude-plugin/     Claude Code 插件清单和 marketplace
skills/shuozhongwen/ 技能本体：SKILL.md 和 references/（规则、写法、症状库、扫描正则）
agents/             评委和事实核查的提示词（Claude Code 子代理，也被 judge_api.py 读取）
scripts/            评分、扫描、审读核对、文件清理等脚本
hooks/              Claude Code 钩子
calibration/        校准和检验脚本、结果、AI 样本
docs/haohao-shuohua/ 好好说话的原始说明
tests/              python -m pytest -q
install.py          给其他 agent 安装技能
```

## 致谢与许可

本项目基于两个 MIT 许可的开源项目改写：Job-Yang 的 [haohao-shuohua（好好说话）](https://github.com/Job-Yang/jobyang-ai-skills)，以及 Guillaume Meyer 的 [watermarks-remover](https://github.com/guillaumemeyer/watermarks-remover)。详见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)。

本项目以 [MIT 许可](./LICENSE) 发布。
