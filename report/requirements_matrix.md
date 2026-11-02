# 提交要求对应索引

| 要求 | 材料 |
|---|---|
| 3.3.5.1 完整源码 | src/pl/、src/ps/；采用 RTL+PS，无未使用 HLS 工程 |
| 仿真与功能确认 | src/pl/sim/、sim/results/、build/results/、board/results/ |
| 综合实现、资源、时钟、指标 | build/reference_reports/、build/rebuilt_reports/、README.md 指标表 |
| 上板与参考比对 | board/runtime_bundle.zip、board/rebuilt_runtime.zip、board/results/、data/；实物画质未量化 |
| 可复现构建 | build/reproduce.py、src/pl/vivado/；report/reproduction.md |
| 3.3.5.2 最新技能包 | skill/README.md：八类技能适用范围、用法、效果、失败来源与边界 |
| 通用 PYNQ | skill/scripts/pynq_check.py、skill/references/、skill/templates/、skill/tests/ |
| 3.3.5.3 背景、创新、框图、划分、接口 | report/design_report.pdf 正文与专题附录 |
| 优化与比较 | report/optimization.md、data/optimization.csv、设计报告附录 B/H |
| 协作与纠错 | report/ai_collaboration.md、设计报告附录 C |
| 技能提炼与边界 | skill/references/evidence.md、设计报告附录 D |
| 从零复现 | README.md、report/reproduction.md、设计报告附录 E/F/H.5 |
| 3.3.5.4 目录与文件名 | 七目录、英文文件名；README.md 为推荐结构指定文件名，智能体入口为小写 skill.md |

未测项目保留待测说明。历史性能列不伪装成同条件优化前后 A/B；不同 bit 的实板证据不混用。
