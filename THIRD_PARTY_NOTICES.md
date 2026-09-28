# Third-party notices / 第三方声明

本项目整合、改写了两个 MIT 许可的开源项目。原作者的版权声明和许可全文放在 `third_party/`。

| 上游 | 作者 | 许可 | 用在哪里 |
|---|---|---|---|
| [haohao-shuohua（好好说话）](https://github.com/Job-Yang/jobyang-ai-skills) | Job-Yang | MIT，见 `third_party/LICENSE.haohao-shuohua` | `skills/shuozhongwen/references/` 的写作规则、症状库和扫描正则以此为基础改写；`docs/haohao-shuohua/` 是原始说明和配图 |
| [watermarks-remover](https://github.com/guillaumemeyer/watermarks-remover)（commit 258cf20） | Guillaume Meyer and contributors | MIT，见 `third_party/LICENSE.watermarks-remover` | `scripts/` 里不可见字符、文件来源元数据的检查与清理脚本，`hooks/` 的启动器，以及对应的测试 |

校准语料（`calibration/human/`、`calibration/test/`）的版权归原作者和平台，不适用本项目的 MIT 许可，仅供个人学习、研究使用，不可商用，见 `calibration/corpus/README.md`。

This project adapts two MIT-licensed projects. Their copyright notices and full license texts are kept in `third_party/`.
