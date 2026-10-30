# FPGA Vision

基于 PYNQ-Z2 与 OV5640 的实时视觉辅助系统。硬件基于 Zynq-7020，软件运行于 PYNQ 2.4，工程使用 Vivado 2018.3。

| 目录 | 内容 |
| --- | --- |
| src/ | 硬件 RTL、约束、参考模型和板端软件 |
| sim/ | 仿真结果和参考数据 |
| build/ | 构建脚本、时序和资源报告 |
| board/ | 上板文件和运行程序 |
| data/ | 测试数据及历史结果 |
| skill/ | 校验工具 |
| report/ | 项目原理和优化说明 |

在 Windows 主机安装 Python、NumPy、OpenCV 和 Vivado 2018.3 后执行 `python build/reproduce.py host`；仿真与硬件构建通过 `python build/reproduce.py full --vivado <vivado路径>`、`project`、`implement` 分步执行。上板程序位于 `src/ps/runtime/`，应保持 bit/HWH 配套。

工程数据按版本保留。
