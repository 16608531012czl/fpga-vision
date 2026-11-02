# 测试数据与参考结果

`xsim_reading/` 为仿真输入与黄金参考，DUT 的正确性由 testbench 在线断言确认，不能将黄金参考冒充实际输出。`history/` 为历史验证记录，`optimization.csv` 为带版本及可比性边界的优化对照。

最新版报告附录 H.4 的指标表位于 `../report/metrics/summary.csv`，来源映射为 `../report/metrics/sources.json`。实板原始数据在 `../board/results/`。本次没有生成新采集图片或新实板性能结果。
