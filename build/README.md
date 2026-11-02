# 可复现构建与实现报告

`reproduce.py` 提供 host、quick、full、project、implement 和 all 阶段；按根目录 README 的次序执行。工具基线为 Vivado 2018.3，Windows 原生启动由 invoke_vivado.ps1 处理，生成目录为 build/work。

| 位置 | 内容 |
|---|---|
| reference_reports/ | 原实板硬件对应的资源、时序、DRC 与 CDC 报告 |
| rebuilt_reports/ | 2026-10-30 从零重建的综合、布线与时序报告；时钟约束和 Clock Summary 在原始时序报告中 |
| rebuilt/ | 重建 bit/HWH、源码指纹和配置数据与 PYNQ 运行时字典一致性证据 |
| results/ | 历史测试和构建原始输出 |
| results/submission_20261102/ | 本次重新执行的软件、技能、预检、时序门槛和硬件比较结果 |
| provenance/ | 引脚/IP/硬件来源、本次输入文件指纹与命名变更说明 |

本次未重新综合实现或上板，历史报告的日期与硬件来源保留。原始报告包含警告，应阅读具体约束与 CDC 内容，DRC 零错误不代表无警告。
