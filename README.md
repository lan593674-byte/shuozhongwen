# shuozhongwen · 说中文

[English](./README.en.md)

一个给 AI agent 用的中文写作插件：写或改一篇中文文章，要同时做到三件事——**事实不动、没有 AI 腔、写得好**。

只做减法去 AI 味，结果往往是白开水：套话删光了，文章也没了。初稿写得差，多半也不是句子的毛病，是动笔时手里没有素材、没想清楚要写什么，只好拿套话和套路撑篇幅。所以这个插件先备料、列提纲，再写初稿；写完再查套路，交给一个**全新的评委**审读，评委每一条判断都必须引原文作证据，引不出来的分数作废；没过线就按证据改，换新评委再审；文学性文字过线后再精修一轮，新旧两稿盲评，新稿两次都胜才换。统计意义上的“AI 相似度”只当护栏，不当目标。

支持 Claude Code（完整插件，含子代理和钩子），也能装进 Codex、Cursor、Gemini CLI 等支持 Agent Skills 的 agent；评委可以用任何兼容 OpenAI 接口的模型。

## 它怎么工作

输入 `/shuozhongwen 题目或稿件路径`，按七步走：

1. **认文体，定标准**：实用文本（周报、通知、方案）要准确简洁；议论文字要观点立得住；文学性文字（散文、游记、小说、书评）要写得好。文体照题目要做的事来定，决定后面的过线标准。
2. **写前准备**：复述任务（写给谁、要做哪几件事、多长）；备素材：改稿和根据你的材料新写时先列数据清单（数字、专名、术语、引用、因果方向等），用到的一个字不动；只给题目时先查资料；游记、回忆这类要靠你亲身经历的文字，你没给经历，就先问你三五个具体问题再写，不替你编。然后用一句话定下这篇要让读者得到什么，列出一段一行的提纲，每行先写这段开头用的那件事，再写它说明什么；说明文还要对着任务查核心问题有没有正面回答、时间链因果链有没有断档。文体本来就带的部分（论坛帖和文章的标题、书信的称呼落款）照惯例带上。
3. **写初稿**：照提纲整篇写，一段一件事，先写事实和细节，判断跟在后面，第一句就进入题目；结尾落在题目的核心问题上，不另起新话题。注意力放在内容上，套路检查放到写完以后。
4. **写完自查**：`polish_check.py` 查不可见字符、四条机械扫描（章节编号、元话语、半角标点、“不是 X 而是 Y”）、结构套路和 AI 相似度；再对着提纲和数据清单回读。
5. **编辑审读和事实核查**：两个全新的评委并行，只看到文体、任务、正文和评分标准，看不到写作经过和上一轮评语。评委按六项打分：具体可感、自己的发现（说明文看取舍）、语言与意象、节奏、结构与张力、声音，并判断有没有偏题。
6. **按证据改**：`review_zh.py` 逐项核对评委引的证据是不是原文原句，再判是否过线。没过就回到提纲重写有问题的那一段，素材不够就列给作者或回去补查，不靠硬造的判断句、警句、设问充数；改完换新评委，最多三轮。只差篇幅、素材又确实不够的，不凑字，只提示不拦。
7. **精修**（只对文学性文字）：过线后在副本上再改一轮，补素材里没用上的细节，删替读者解释人物想法的句子；新旧两稿交给全新的对比评委，两种顺序各问一次，两次都判新稿更好、新稿复审也过线，才交新稿。
8. **交稿**：正文，后面单起一行 `【修改报告】` 接修改报告。

过线标准：文学性文字六项平均 ≥ 4、每项 ≥ 3；实用和议论文字平均 ≥ 3.5、每项 ≥ 3；不是白开水；没有偏题；评委认出的模板腔（段首短判断成串、报幕句、总结翻转、滥用引号、编造“我”的经历、开场白和资料交代等）最多 1 处。设问、单句成段、前后呼应这类人也常用的手法只提醒、不拦（依据见 `calibration/TEMPLATE_AUDIT.md`）。只给题目、没有材料的稿子事实存疑为 0。

### 数据保真（改稿和根据材料新写时强制）

改一份已有的稿子，或者根据你给的材料写一篇新文章时，插件会先加载约束技能 `baozhen`：原稿和材料里的数字、表格、引用和参考文献、术语、“可能”“主要”这类限定词、因果方向和论断，一个都不改、不删、不加。新写时材料里的数据可以不全用，但用到的照搬，不换算、不取整、不推算新数字，材料没有的数据不从网上补。即使原稿或材料的数据看起来错了，或者事实核查判它存疑，也只写进修改报告的“待作者核对”，由作者决定。评委要求“补细节”“补观点”时，也只能列给作者，不能替作者编。

### 清除零宽字符和乱码：`/shuozhongwen qingli`

`/shuozhongwen qingli 路径`（也可以用 `/shuozhongwen:qingli`）检测并清除文件、文件夹、Word/PowerPoint/Excel/EPUB 文档或一段文字里的零宽字符等不可见字符和乱码（U+FFFD、控制字符、“锟斤拷”“烫烫烫”，以及编码读错造成的“涓枃”“Ã©”这类错乱，能还原的会还原成原字）。空格、换行、编码、文档格式都不动；改之前自动备份原文件。清完逐条报告清除了什么、在哪一行、哪些地方原来的字已经丢失需要作者补。命令行：`python scripts/qingli.py 路径 [--check]`。

### 论文特化：`/shuozhongwen lunwen`

在 Claude Code 里也可以用单独的命令 `/shuozhongwen:lunwen`，插件菜单里能直接点到。

用于学术论文、毕业论文、课程设计报告、实验报告和综述，只改语言，不碰研究：

- 只去 AI 腔（虚动词、空泛修饰、机械衔接、模板排比、整段重复），保持书面学术语体，不口语化、不加比喻、不改人称；章节编号、图表、公式、引用、参考文献原样保留，不增删段落和表格。
- 语言由专门的学术语言评委（`lunwen-judge`）审：表述准确、简洁、学术语体、衔接与逻辑、一致、去模板腔，平均 ≥ 3.5、每项 ≥ 3。
- 学术严谨性审查技能 `xueshu`（只在这个模式启用）：一个全新的审查子代理（`rigor`）对照原稿和改稿，找出改稿里任何严谨性退步（数据、限定词、因果、论断、术语、引用、语体），退步必须为 0；原稿本身的问题（数据自洽、结论超出证据、可能的数据泄漏、引用不对应等）列给作者，不改正文。
- 交稿附修改对照表（原句 → 改句 → 改了什么），作者可以逐条接受或拒绝。

## 安装

需要 Python 3.10 以上。核心脚本只用标准库，不用装依赖。

### Claude Code

```bash
claude plugin marketplace add lan593674-byte/shuozhongwen
```

```bash
claude plugin install shuozhongwen@shuozhongwen
```

也可以在 Claude Code 里用 `/plugin` 菜单添加。装好后输入 `/shuozhongwen` 使用，评委、事实核查和对比评委是 `shuozhongwen:judge`、`shuozhongwen:factcheck`、`shuozhongwen:compare` 三个子代理，跟当前会话用同一个模型。

### Codex、Cursor、Gemini CLI 等其他 agent

```bash
git clone https://github.com/lan593674-byte/shuozhongwen.git
```

```bash
python shuozhongwen/install.py codex
```

`codex` 可以换成 `agents`（`~/.agents/skills`）、`cursor`、`gemini`，或者用 `--dest 目录` 指定任意 skills 目录。脚本会把技能复制过去，并把里面的路径指回你 clone 的仓库，所以装完仓库别挪地方；`git pull` 之后重跑一次。卸载加 `--uninstall`。

没有子代理的 agent，评委有两种办法：用下面的 `judge_api.py` 调一个模型，或者让你在一个全新的对话里贴评分标准和正文。技能里写明了不允许在当前会话里自己给自己打分。

### 用别的模型当评委（推荐）

写稿的模型给自己打分会偏松：它认不出自己的套路，还会把这些套路当成好文章。所以插件优先让另一个模型当评委。

插件自带一个 MCP 服务（`scripts/judge_mcp.py`，Claude Code 装插件时自动启动），提供 `judge`、`factcheck`、`lunwen_judge`、`rigor`、`compare`、`judge_status` 六个工具。每次调用都是一次全新的请求，只带评分标准和正文，返回结果已经按 `review_zh.py` 核对过。`/shuozhongwen` 流程里会先调用它，没配置时再退回到子代理。

接口、模型、密钥都放在一个配置文件里（默认 `~/.shuozhongwen/judge.json`，可以用环境变量 `SHUOZHONGWEN_JUDGE_CONFIG` 指到别处），以后换 API 只改这一处：

```bash
python scripts/judge_config.py set --base https://api.deepseek.com/v1 --model deepseek-chat --key-env DEEPSEEK_API_KEY
```

```bash
python scripts/judge_config.py test
```

- 密钥三种给法：`--key-env 环境变量名`（推荐）、`--key-file 路径:变量名`（从 .env 文件读）、`--key 明文`（不推荐）。密钥只在调用时读取，`show` 和 `judge_status` 都不显示它。
- 不同角色可以用不同模型：`--role factcheck=另一个模型`；`--clear-roles` 恢复全部用 `--model`。
- OpenRouter、Kimi、通义、火山方舟、本地 Ollama（`http://localhost:11434/v1`）都可以。

不在 Claude Code 里，也可以直接用命令行：`python scripts/judge_api.py 稿件.txt --genre 游记散文 --task "题目原话"`；论文模式：`python scripts/judge_api.py 改稿.txt --genre 课程设计报告 --paper --original 原稿.docx`。

## 单独使用的工具

| 命令 | 作用 |
|---|---|
| `python scripts/score_zh.py 稿件 --explain` | AI 相似度，附“比多少人类段落更像 AI”和各项特征 |
| `python scripts/structure_scan.py 稿件` | 结构套路：段首短判断句、总结翻转套话、同一出处反复引述、四类以上套路叠加（拦）；设问自答、单句成段、给普通词打引号、冒号清单、段尾对仗警句、前后回扣、第一人称过程交代（提示）；另列出全文每处引号（能不用就不用） |
| `python scripts/haohao_scan.py 稿件` | 机械扫描：章节编号、元话语、半角标点、“不是 X 而是 Y” |
| `python scripts/polish_check.py 稿件` | 交付硬闸，上面两项加不可见字符；论文加 `--paper`（不扫章节编号），参考文献里的半角标点自动跳过 |
| `python scripts/doc_text.py 稿件.docx -o 稿件.txt` | 把 .docx 的正文和表格抽成纯文本 |
| `python scripts/review_zh.py 稿件 --genre 文体 --review 审读.json` | 核对评委 JSON 的证据并判是否过线，不调用模型 |
| `python scripts/qingli.py 路径 [--check]` | 检测并清除零宽字符和乱码（文本、文档、文件夹），报告清除了哪些 |
| `python scripts/inspect_file.py 文件` | 检查文件里的来源元数据（C2PA、EXIF/XMP、Office 属性等） |
| `python scripts/clean_file.py 文件 -o 输出` | 清理这些元数据，支持 PNG、JPEG、WebP、SVG、PDF、DOCX、XLSX、PPTX、EPUB、HTML、Markdown、MP4 等 |

Windows 上把 `python3`/`python` 换成你机器上的 Python 命令即可，建议加 `-X utf8`。

## Claude Code 里的两个钩子

装了插件后，这两个钩子一直生效，与 `/shuozhongwen` 无关。两个钩子都**只检查，不修改**任何文件或回复：

- **写文件后**（PostToolUse）：检查 Claude 刚写的文件里有没有零宽字符等不可见字符、乱码和来源元数据，结果记下来，不弹告警。
- **显示回复前**（MessageDisplay）：每条回复末尾都附一行检测报告：这条回复和这期间写入的文件有没有零宽字符、乱码，不论回复多短。250 字以上的回复在检测行上面再加一行 AI 相似度（字数太少时统计不可靠）；交稿的回复只算 `【修改报告】` 前面的正文，因为报告里的列表会把任何文章都推到高档。只改显示，不改会话记录。

例如：

```
---
AI 相似度 0.12（低，在人类文字的常见区间内）
检测：回复无零宽字符和乱码；写入的 2 个文件里 1 个有问题：notes.md：零宽/不可见字符 3｜清除可用 /shuozhongwen qingli
```

| 环境变量 | 作用 |
|---|---|
| `SHUOZHONGWEN_SCORE=0` | 关掉回复末尾的评分行 |
| `SHUOZHONGWEN_SCORE_MIN` | 评分的最短字数，默认 250 |
| `SHUOZHONGWEN_CHECK=0` | 关掉回复末尾的检测行 |
| `SHUOZHONGWEN_LOG_DIR` | 钩子日志目录，默认插件目录下的 `logs/`；只记计数和分数，不记回复原文 |

## AI 相似度是怎么来的，能说明什么

`score_zh.py` 是一个带符号约束的逻辑回归，看 19 项中文文体统计：句长和段长的起伏、连接词密度、省略号和感叹号、“我们”“的”的密度、双字词重复度、套话标记等。校准用了 62 篇人类文字（经典名作、贴吧长帖、起点网文免费章节，全部人工审过）和 8 个模型生成的 101 篇文字。

- `high` 档阈值固定为 0.6（约为人类段落的第 90 百分位）。按整篇算，校准集里 89% 的 AI 文章达到 high，人类文章 3% 被误判；留出的 49 篇人类文章误判 1 篇。
- 留一模型检验（该模型的样本完全不参与训练，按段算）：各模型命中 57%–94%。
- 留出测试（按段算）：贴吧口语长帖误判 6%，网络小说误判 10%。

详见 `calibration/RESULTS.md`、`calibration/TEST_RESULTS.md`。结构套路的每条规则在人类文字和 AI 文字里各命中多少，见 `calibration/TEMPLATE_AUDIT.md`（`python calibration/template_audit.py` 重跑）：设问、单句成段在人类文字里比 AI 多得多，所以只当提示。

**它只说明统计信号像不像校准集里的 AI 文本**，不代表任何商业检测器的结论，也不是用来“骗过检测”的。插件里它只是护栏：落在人类的常见区间就算过，不为了压分去改文章，因为压分最省事的办法（堆重复词、乱加标点）只会把文章改坏。

评委的有效性检验见 `calibration/REVIEW_VALIDATION.md`：经典名作平均 4.4–4.6 分，AI 样本 3.1–3.2 分，一篇被改成白开水的罗马游记 2 分左右并被判为白开水，改好的版本 4 分以上。

## 已知局限

- 评委和写作者是同一个模型时，存在自我偏好的可能；全新子代理只去掉了上下文干扰。在意的话用 `judge_api.py` 换一个模型当评委。
- 评分是伪精确：用的是评委的证据和改法，分数只是门槛。过线就停，不为刷分再改。
- AI 相似度对“被要求写得自然一点”的 AI 文本明显更难认出；对公文等没进校准集的文体，误判率未知。
- 校准用的人类语料随仓库公开（`calibration/human/`、`calibration/test/`），**不可用于任何商业用途，只能作为个人学习、研究使用**，版权归原作者和平台，MIT 许可不覆盖这些语料，详见 `calibration/corpus/README.md`。扩充语料后运行 `python calibration/calibrate.py` 可以重新校准。

## 目录

```
.claude-plugin/     Claude Code 插件清单和 marketplace
skills/shuozhongwen/ 技能本体：SKILL.md 和 references/（规则、写法、症状库、扫描正则）
skills/baozhen/     数据保真约束（改稿和根据材料新写时必加载）
skills/xueshu/      学术严谨性审查（只在论文模式用）
agents/             评委、事实核查、对比评委、学术语言评委、严谨性审查的提示词（Claude Code 子代理，也被 judge_api.py 读取）
scripts/            评分、扫描、审读核对、文件清理等脚本
hooks/              Claude Code 钩子
calibration/        校准和检验脚本、结果、AI 样本、人类语料（仅限个人学习，不可商用）
docs/haohao-shuohua/ 好好说话的原始说明
tests/              python -m pytest -q
install.py          给其他 agent 安装技能
```

## 致谢与许可

本项目基于两个 MIT 许可的开源项目改写：Job-Yang 的 [haohao-shuohua（好好说话）](https://github.com/Job-Yang/jobyang-ai-skills)，以及 Guillaume Meyer 的 [watermarks-remover](https://github.com/guillaumemeyer/watermarks-remover)。详见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)。

本项目以 [MIT 许可](./LICENSE) 发布。
