# LaTeX 写作、模板与引用

整合 latex-output、template-parser 和 latex-guide 的写作相关内容。仅在用户要求、已提供模板或目标要求时使用，不安装环境或导入绘图能力。Markdown 默认为正文格式；写作论证仍执行 [chapters.md](chapters.md) 与 [core.md](core.md)。

## 读取实际模板

查看用户指定模板或论文项目 `latex-templates/` 的 `.cls`、`.sty` 和主文件。识别学校/期刊/通用类、章节命令、摘要与关键词、封面/声明/致谢/附录、引用系统、宏包依赖、版式与编译要求。保留原模板，在新文件中填内容，不修改模板来绕过格式要求。

| 类型 | 识别线索与适配 |
|---|---|
| 学位论文 | thesis/dissertation、学位/学校/专业宏、封面、frontmatter/mainmatter/backmatter |
| 期刊/会议 | 期刊或组织类名、作者/机构宏、摘要/关键词、页数和匿名选项 |
| 通用文档 | article/report/book；中文可用已有 ctexart/ctexbook/ctexrep |

学校模板示例包括 ThuThesis 的 `\thusetup`、国科大类、PKU/ZJU 等；期刊示例包括 IEEEtran、elsarticle、acmart。只按实际文件和当年官方模板写，不凭例子自拟命令、年份样式或所有模板共有的结构。

模板缺文件、特殊结构、编码或无法解析时明确哪部分未满足；可继续准备正文和已知结构。只有用户选择通用格式时才回退，不静默换掉目标模板。默认 UTF-8，转换前保留原件并核对内容。

## 章节与文件结构

`\chapter` 对应 book/report 类章节，article/期刊通常用 `\section`；下一级为 `\subsection` 和 `\subsubsection`。不是所有类都支持 chapter。章节文件可由主文件 `\input`，需要独立分页时按模板使用 `\include`。

```text
论文项目/
  latex-templates/          原模板
  chapters/                对应大纲的 .tex 文件
  main.tex                 主文件
  references.bib           真实参考文献
  plan/                    写作决策与验证
```

上述为项目示例，独立小文档不强制拆文件。章编号与内容来自当前大纲，不能照模板固化 Related Work 或旧章架构。

## 小型独立正文模板

确认无特殊模板要求且现有编译器支持时可采用以下最小形状。所有示例文字是模板，不是最终稿：

```latex
\documentclass[UTF8]{ctexart}
\usepackage{amsmath,amssymb,booktabs}
\begin{document}
\title{实际论文题目}
\author{实际作者或匿名格式}
\date{}
\maketitle
\begin{abstract}
经正文与真实结果核对的摘要。
\end{abstract}
\section{引言}
经证据映射形成的论证。
\section{研究方法}
实际方法与适用条件。
\section{结果与讨论}
实际数据支持的比较与边界。
\section{结论}
回应研究问题的发现。
\end{document}
```

英文通用文档可按目标用 article；学校篇章用其实际类。宏包只加载实际需要且与模板兼容者，不把预设宏包列表全部引入。

## 公式、算法与文本

公式使用数学环境，定义符号、单位、条件和编号；不把正文分析塞进复杂公式。常用形状：

```latex
文本中的 $x$ 与 $y$ 保留原数学含义。
\begin{equation}
  y = f(x)
  \label{eq:method}
\end{equation}
\begin{align}
  z &= g(x) \\
  y &= h(z)
\end{align}
```

公式与算法必须来自实际材料，不能为版式补造机制。正文不使用 `\item` 代替论证；自然段用空行分隔。图表已有时只适配引用与说明，不生成图片。

## 表格与已有图片

三线表可使用现有 booktabs；字段、数字、单位与表注来自 [results.md](results.md) 的表格契约。示例：

```latex
\begin{table}[htbp]
\centering
\caption{实际比较对象与指标}
\label{tab:comparison}
\begin{tabular}{lcc}
\toprule
方法 & 指标与单位 & 适用条件 \\
\midrule
实际方法 & 实际数值 & 实际条件 \\
\bottomrule
\end{tabular}
\end{table}
```

不为“最好结果”默认加粗或用模板虚构基线。按目标允许的表格强调处理。已有图片用 `\includegraphics` 时核对实际相对路径和 graphicx 支持；图注描述测量条件，不扩大结论。`\label` 通常放在 caption 后，正文用 `\ref` 或目标规定的命令。

## 参考文献与交叉引用

使用真实来源和稳定键值，所有 cite 键在 bibliography 中存在，参考文献不得填虚构作者/题名/DOI。BibTeX 字段依类型：article 的作者/题名/刊物/年/卷期页/DOI，inproceedings 的会议和页码，book 的出版社与版本，预印本的编号及状态。

```bibtex
@article{verified_source_id,
  author = {经核实的作者},
  title = {经核实的题名},
  journal = {经核实的刊名},
  year = {经核实的年份}
}
```

示例只说明字段，写真实 `.bib` 时每项取已核实值。保留技术缩写大小写时依 BibTeX 规则保护；页码范围用双连字符。不能把缺 DOI 当作不真实来源。

BibTeX 形状为 `\bibliographystyle{实际样式}` 与 `\bibliography{references}`；BibLaTeX 形状为模板规定的 `\usepackage[...] {biblatex}`、`\addbibresource` 和 `\printbibliography`。不要混用系统或擅自改后端。`\citep`/`\citet` 仅在相应引用包提供时使用，`\cite` 依目标体例。引用真实性仍读 [literature.md](literature.md)。

## Markdown 转换与保护

标题映射到实际文档类的层级，直接引文映射到 quote 或模板引用环境，代码映射到 texttt 或实际代码环境。正文列表先检查是否应改为连贯段落，不把所有列表自动变 itemize。加粗只有合法模板或有意强调时保留；不能把旧 Markdown 装饰移成 textbf。

文本中的 `# $ % & _ { } ~ ^` 依所在语境转义，已有数学和命令保持原样，不能二次转义。保留 `\cite`、`\ref`、标签、公式、专名和 protected spans。中文标点与 LaTeX 命令分开处理。

## 验证与交付

检查实际 `.tex` 文件、所有输入文件、引用键、标签、表格列数、特殊字符和模板依赖。编译使用当前可用的编辑器/编译工具，读完整诊断；只有真实成功才说可编译。独立 `.tex` 在支持的 Codex 环境优先内置编辑器与编译工具，不要求安装 TeX 或插件。

多文件模板需要类文件/资源而编译服务不支持时，保留源码并说明未验证的依赖；不能把“编辑器打开”当编译通过。实际已有终端 TeX 工程可记录其既有命令与后端，中文常需 XeLaTeX/LuaLaTeX，BibTeX/Biber 按模板，不固定重复次数来替代检查。

遇 Undefined control sequence 查实际命令/宏包，Missing $ inserted 查数学与文本语境，File not found 查路径，Package clash 查已有包及参数；先核对模板，避免随意加包。投稿前核对版式、字号、行距、字体、编号、盲审和当前官方要求，不把上游样例页边距或过往会议包当通用标准。
