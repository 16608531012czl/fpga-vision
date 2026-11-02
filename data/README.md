# 测试数据与参考结果

`xsim_reading/` 为仿真输入与黄金参考，DUT 的正确性由 testbench 在线断言确认，不能将黄金参考冒充实际输出。`history/` 为历史验证记录，`optimization.csv` 为带版本及可比性边界的优化对照。

最新版报告附录 H.4 的指标表位于 `../report/metrics/summary.csv`，来源映射为 `../report/metrics/sources.json`。实板原始数据在 `../board/results/`。新增 2026-11-02 原始图片、逐段 A/B CSV 和汇总位于 `measurements_20261102/`；它们来自已有独立补测批次，本次仅导入。原 60 秒结果保留原值，新增指标采用独立名称。
