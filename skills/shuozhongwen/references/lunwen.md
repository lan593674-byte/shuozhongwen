# 论文流程：lunwen

保持 `/shuozhongwen lunwen` 与 `/shuozhongwen:lunwen`，接收稿件、选题、章节要求、文献或翻译任务。`R`、`S`、Python 用法沿用入口。写作依据为 `research/`，不再沿用旧版“只能改语言、禁止调整段落”的通用限制。

## 范围与参考

读取原稿、资料、模板和已有计划，确定论文类型、学科、问题、方法、读者、语言、结构、长度与交付。只问影响正文的缺项；研究未确定时按 `research/planning.md` 讨论推荐方案。短段润色不扩成整篇工程；新写或结构重写可以规划组织，纯语言润色保留原结构。

必读 `research/core.md`、`R/skills/baozhen/SKILL.md`、`R/skills/xueshu/SKILL.md`。无原稿也要记录证据清单、原始数据与缺口。

| 任务 | 必读参考 |
|---|---|
| 中型、多章、整篇写作/重稿 | `research/planning.md`、`research/chapters.md` |
| 引言、背景、相关工作 | `research/evidence.md`、`research/literature.md` |
| 文献综述、检索、引用整理 | `research/literature.md` |
| 章节、方法、摘要、结论 | `research/chapters.md` |
| 文科/社科 | `research/humanities.md` |
| 医学/生物 | `research/medical.md` |
| 法学 | `research/law.md` |
| 实验结果、讨论 | `research/results.md`；涉及统计再读 `research/statistics.md` |
| 润色、去 AI 化、扩缩写、中英翻译、图表标题文字 | `research/revision-translation.md` |
| 投稿自审、审稿意见、返修 | `research/peer-review.md` |
| LaTeX 正文、公式、引用、模板 | `research/latex.md` |
| 声称章节/终稿完成之前 | `research/verification.md` |

这些是内部参考，不增加命令。不引入绘图、生图、绘图数据清单或环境安装；结果写作需要的数据出处、表结构和指标口径仍须记录。

## 执行

1. **读全文、锁保真**：`.docx` 用 `python S/doc_text.py 原稿.docx -o 原稿.txt` 读取段落、表格、脚注与尾注；Word 原生公式以受保护的 OMML XML 块展示，不把分式、上下标拼成普通数字。提取结果供读取核对，不直接当最终排版稿；原文档与图/公式原件保留，未读取的图像、嵌入对象单列缺口，不声称已核查。保留数值、单位、有效位、术语、引用归属、公式、论断强度和局限。已有表格/图/公式的事实内容不改，封面、署名、分工、致谢等未授权部分不动。授权结构重组、引用格式统一、有来源的新增内容记录映射，不偷偷改研究。
2. **计划和前置证据**：中型及以上建立/更新 `plan/` 与 task packet。整篇重稿先锁 chapter architecture（文件、职责、目标字数/下限、前置证据、占位政策），按章使用独立作者并保存 provenance。无多代理能力时说明限制，按章独立上下文处理，不伪造代理记录。引言/相关工作先建 evidence map、paragraph blueprint；实验/结果先建 experiment protocol、table schema。关键材料缺失返回 NEEDS_CONTEXT，不以摘要级短稿或捏造数字冒充完整章。
3. **形成论证**：方法按输入→处理→输出→设计理由→实验对应组织；文献按共同问题、证据、差异与局限分析，不逐篇罗列。结果区分观察、解释和可支持结论，保留指标与边界。摘要在主体后写。过程说明、用户要求与缺口留在计划；模拟数据只用于明确标记的规划稿，不能写成真实实验或进入投稿终稿。
4. **两阶段检查**：先查范围、结构、字数、格式、证据和数据，再查论证、语言、信息完整与学科规范。长任务更新 progress、notes，收尾 capability-use audit 记录应读/实际参考、已读/未读材料及原因、产物、实际验证与剩余缺口。已有连续写作授权时不逐章重复审批。

## 独立评分、严谨审核与改写

优先现有 MCP：`judge_status` 后并行 `lunwen_judge`（文体 + 全文）、`rigor`（原稿全文 + 新稿全文）。新写时原稿为空，审核当前稿证据与严谨问题，不虚构基线。论文不用普通文学评委。完整研究自审按 `research/peer-review.md`，与语言评分分开。

未配置时用全新独立子代理，分别只给 `R/agents/lunwen-judge.md`、`R/agents/rigor.md` 标准及全文，不提供改稿经过或上轮分数。已有接口可用：

```text
python S/judge_api.py 新稿 --genre 论文类型 --paper --original 原稿
```

新写时省略 `--original`，不需要创建假原稿。保存原始 JSON，运行：

```text
python S/review_zh.py 新稿 --genre 论文类型 --paper --review 审读.json --original 原稿 --rigor 严谨.json
```

六项仍为 accuracy、concision、register、coherence、consistency、naturalness，1–5 分，平均 ≥ 3.5、每项 ≥ 3，证据来自全文。有原稿时双原文证据支持的严谨性退步为 0；研究本身的问题单列，关键证据缺失不能称已验证。评委不可用时明确“未完成独立评审”，不能自己冒充。

上面的复审命令在新写时也省略 `--original 原稿`，`--rigor` 仍必须提供独立审查结果。审核证据无效时换新评委重审，不能把作废的退步当成“0 退步通过”。

先恢复丢失的条件、对象、方法、口径和局限，再修语言与组织。删空话不能损失事实，不为简洁持续压缩。需要改数字、补未知结果、加强结论的意见列为待处理。改后重核保真、换新评委，最多三轮；过线即停，未过报告实际状态。

## 检查与交付

```text
python S/polish_check.py 新稿 --paper
python S/score_zh.py 新稿 --explain
```

允许章编号、本文/本研究、有效引用、主题句和必要收束。结构信号用于定位，不按数量否决。`polish_check.py` 通过要求为不可见字符 0、未保护的中文正文格式通过、AI 相似度不在 high；篇幅不足不能评估时单列“未评”。偏高只修真实问题，不损失信息、不刷低分；修后仍 high 就报告该检查未通过。保留数值、tier 和篇幅限制，不声称第三方 AI 率或查重率。未执行/失败分别报告。

默认交付 Markdown、纯文本或用户要求的 LaTeX，不擅自生成 Word 成品或更换模板。提供正文、修改对照（润色逐处可追踪，重写按段映射）、保真核对、两阶段检查、独立评分、严谨问题和实际验证。前置证据、真实数据或模板要求未满足时，不声称可直接提交。
