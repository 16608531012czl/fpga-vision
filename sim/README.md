# 仿真与验证

testbench 与验证脚本位于 `../src/pl/sim/` 和 `../src/pl/tools/verify.py`。从根目录运行 `python build/reproduce.py full --vivado C:/Xilinx/Vivado/2018.3` 可重新执行九组完整验证。

`results/` 保留 2026-10-30 的实际 XSim 日志和源指纹；输入与黄金数据位于 `../data/xsim_reading/`。2026-11-02 复核了源指纹，没有重新执行 XSim。主机软件与技能自测的新结果见 `../build/results/submission_20261102/`。
