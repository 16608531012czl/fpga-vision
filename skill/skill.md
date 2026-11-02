---
name: pynq-portable-validation
description: 为 PYNQ PS/PL 工程执行版本封存、环境预检、Overlay 元数据核对、结果比对和分层验收，适用于换题目后的部署与复现排错。
---

# 通用 PYNQ 工程验证

先阅读 [README.md](README.md) 选择入口；脚本只需 Python 3.6+ 标准库，板端元数据模式另外需要目标镜像提供的 PYNQ。

1. 收集用户的目标板卡、FPGA 型号、PYNQ/Python/Vivado 版本、bit/HWH、IP 接口与原始证据。缺失项填“未知”，不要套用来源项目的型号、管脚或寄存器。
2. 用 `scripts/pynq_check.py seal/verify` 固定载荷；用 `env` 检查执行环境；主机检查通过后，再在目标 PYNQ 上用 `metadata` 核对 IP 名称、VLNV、地址和地址范围。该命令使用 `download=False`，不证明板上已加载相同设计。
3. 算法/数据不符时运行 `compare`；实现检查运行 `timing`，还须审阅原始约束、CDC 与告警。不要将时序摘要等同于完整签核。
4. 需要实际编程、MMIO、DMA 或外设时，使用 [references/bringup.md](references/bringup.md) 的分层流程并由项目自己的驱动执行。保留超时与清理失败，不为了重试而释放仍被硬件使用的内存。
5. 对照 [references/pitfalls.md](references/pitfalls.md) 定位问题。使用 [references/prompts.md](references/prompts.md) 和 `templates/acceptance.md` 整理协作与证据；原始失败不覆盖，历史结果与新结果分开。

来源及实际验证范围见 [references/evidence.md](references/evidence.md)。换板卡复用的是方法、脚本及模板；bit/HWH、引脚约束、PS 配置和硬件验收必须重新适配。XRT/xclbin、部分重配置、Scatter-Gather DMA 不在本包自动检查范围。
