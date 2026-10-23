# OV5640 时序、帧率、自动对焦与EC11升级

独立工作目录：`C:\fpga\visual_aid_v4_ec11_20261022`。

当前入口：[PL 图像链路、细节优先及稳定亮度说明](docs/pl_upgrade_zh.md)。
实时缩放、分屏和状态文字已移入 PL，采集与缩放并行；默认 detail / stable，
采用 DN=0、SH=4、NR=1、CT=0 保留文字细节。当前实板结果以 `reports/PL_UPGRADE_zh.md` 为准。
本轮导出位置为桌面 `FPGAvision/releases/visual_aid_v4_pl_upgrade_20261023`。
下文性能与 AF 部分保留上一轮基线信息。

本版新增硬件旋钮解码、USM/Laplacian/边缘引导处理、Sobel诊断、实时调参和状态显示，保留暗光提亮。
本轮进一步优化流水线与软件缓冲区处理，默认请求20帧，启动连续自动对焦；实际结果见交付状态。
运行方法及性能边界见[性能与对焦说明](docs/performance_af_zh.md)。光照模块按用户要求暂不参与运行。

本次光照通信改到PMOD B：SCL接物理第3脚（T11），SDA接物理第4脚（T10）。
必须加载同一发布包内的FPGA文件；原Arduino SCL/SDA接法不适用于本版本。EC11仍接AR8/AR9/AR10。
旧版备份在reports/attempts/before_pmod_b及before_performance；本轮导出到桌面releases/visual_aid_v4_performance_af_20261023。

上板包：`delivery/visual_aid_v4_ec11_board.zip`。
安装、接线、控制和验收：见[升级说明](docs/upgrade_ec11_zh.md)。

本轮实际通过项以reports内新生成的记录为准；原工程文档中的历史实板数据不作为本版测试结论。

构建：`build.ps1 -Step system` 创建独立工程；`-Step test`主机检查；`-Step sim`和`-Step full`运行仿真；`-Step bit`生成并校验配套硬件包。

旧工程保留于 `C:\Users\CHENZHELONG\Desktop\FPGAvision\visual_aid_v3`；本次不更改旧发布物。
# 当前升级入口

PL 缩放分屏、颜色降噪、保色重建、局部映射和 15/31 窗口操作见
[PL 图像链路说明](docs/pl_upgrade_zh.md)。本版实测以 `reports/PL_UPGRADE_zh.md`
和 `reports/pl_upgrade_summary.json` 为准；历史性能报告对应各自发布版本。

