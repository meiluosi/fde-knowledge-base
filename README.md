# fde-knowledge-base · v0.1.0

FDE 系列的企业知识库判断 Skill：针对文档检索（RAG）类项目，先摸底真实文档与知识状况，再判断问题该不该走检索、治理谁来做、拿什么评、原文怎么兜底；系统在跑但质量上不去时，分检索、生成与知识本身三层定位。上游是 fde-problem-framing（业务问题定义）和 fde-route-selection（技术路线）；本 Skill 不需要安装它们，也不修改它们的仓库。

## 安装与使用

将整个 `fde-knowledge-base` 文件夹放入宿主的 skills 目录，保留目录名与 SKILL.md。Codex 常用 `${CODEX_HOME:-$HOME/.codex}/skills/`。也可不安装，直接让助手读取本目录 SKILL.md。

```sh
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R -n fde-knowledge-base "${CODEX_HOME:-$HOME/.codex}/skills/"
```

如宿主未重新发现技能，开启新会话。以根路径安装后检查 references/、templates/ 等子目录是否齐全。尚未在任何宿主做实机测试。

可直接说：
- “客户要建知识库，写方案前我该先摸哪些底？”
- “这批问题哪些该走文档检索，哪些该改道？”
- “答案质量上不去，帮我按检索侧和生成侧分开查。”
- “帮我设计评测集，要能分开检索错和生成错。”
- “这是供应商的知识库方案，帮我审查。”

## 工程内容
- SKILL.md：入口与四种模式路由。
- references/：模式、文档摸底、知识状况与治理、路径适配、最简替代方案、四层任务、五环节与候选改动、诊断流程、原文兜底、评测集、证据、衔接。
- templates/：知识库判断卡、摸底表、治理章程、评测集、诊断日志、审查报告。
- examples/hr-policy-qa：教学假设示例，不是客户事实。
- scripts/audit_sample.py：按层抽样、通过率 Wilson 区间；scripts/retrieval_metrics.py：召回、精度、排序；scripts/layer_report.py：四层任务逐题标注汇总。只对用户提供的记录做算术，不验证记录真伪。
- tests/：脚本与包结构测试，加人工回归用的行为用例。
- DEVELOPMENT.md：来源与相对原材料的方法修订；ROADMAP.md：推进计划。

## 与其他 Skill 的分工
| 事项 | 归谁 |
|---|---|
| 业务问题是否成立、该不该上 AI | fde-problem-framing |
| 用什么手段（规则/提示词/检索/微调）、模型比选、成本与部署约束 | fde-route-selection |
| 路线含文档检索后：知识够不够、怎么治、怎么评、卡在哪、怎么呈现 | **本 Skill** |
| 评测执行、试点判定 | fde-pilot |
| 对客户说“这是知识治理问题”的措辞 | fde-comms |

## 运行验证
Python 3.9+，仅用标准库。
```sh
python3 -m unittest discover -s tests -v
python3 scripts/audit_sample.py rate --pass 45 --total 50
python3 scripts/audit_sample.py sample --manifest files.csv --strata-col type --n 50 --seed 7
python3 scripts/retrieval_metrics.py --input labelled.jsonl --k 3,5,10
python3 scripts/layer_report.py --input layers.csv
```
命令里的数字与文件是占位。单元测试和静态检查不能证明模型必然遵守流程，更不能证明某个知识库方案有效；行为用例见 tests/behavioral-cases.md，须在目标宿主重跑。

## 参考与致谢

本系列各 Skill 在方法设计上不同程度参考了《FDE:AI落地实战指南》，以及作者本人的 FDE 实践经历。各 Skill 的流程、模板、规则与脚本是在此基础上改写和扩展的方法。示例中的人物、数字与场景均为虚构，不是客户事实。

## 许可
MIT，见 [LICENSE](LICENSE)。示例为教学假设，不含客户数据；使用时自行确保不把客户材料提交进公开仓库。

## 范围
不负责：行业入门、业务问题定义、模型选型与成本、检索系统实施、评测执行、法律与安全合规结论。工具与模型清单不入库。
