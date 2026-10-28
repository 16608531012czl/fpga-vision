# FPGA Vision 当前发布（2026-10-28）

目标为 PYNQ-Z2 / Vivado 2018.3 / PYNQ 2.4，OV5640 DVP 摄像头 + HDMI OUT。
此版以普通后续提交替换 main 文件快照，保留旧提交历史。

## 当前功能

720p PL 实时处理、五种显示模式、1/2/4倍放大、ROI 平移、冻结、左右对比、EC11 画质调节、连续自动对焦。
BH1750 使用 Arduino SCL/P15、SDA/P16，ADDR 接地，3.3V供电。LUX 显示并参与自动提亮。
六行状态栏带显示平滑和限频更新；清晰模式可选 OV5640 内部轻度锐化。
Jupyter 面板支持自定义正整数秒数、持续运行、手动停止与板温显示。

## 验证边界

- 当前相机版 120 秒联合运行：2398 帧，19.980 FPS，DMA/溢出/坏帧为0；板温46.39–48.48°C，无传感器/清理错误。
- 用户确认画面正常、照度遮挡后下降、状态栏清楚且操作顺畅、近景清楚且远景正常。
- 自定义5秒测试和持续运行手动停止均通过，详见 `reports/jupyter_duration_test`。
- 95项主机软件检查通过；原软件运行文件、bit/HWH与已验收版本逐字节一致。
- 当前Arduino传感器管脚实现的建立/保持余量为 +0.189/+0.014ns，DRC错误0。
- 本次GitHub发布只整理文档和完整交付包，没有重新综合、布局布线或加载硬件。
- 旧九组XSim快速/完整结果为同一数据通路的继承证据，位于 `reports/historical_20261023`，并非本次重新仿真。
- 轻度锐化提高边缘响应不等于光学分辨率提高；距离模块和所有场景下的最优清晰度未验收。

`software/board/build_manifest.json` 的基础硬件状态及 camera 软件变体中的 pending 字段是打包时的旧状态；之后实测以 `reports/CAMERA_VALIDATION_zh.md` 和相机验证汇总为准。
不改写这些旧状态来伪造重新构建或新增测试。29个运行负载文件的SHA256保留原样。
Jupyter守护脚本作为额外文件打包，Notebook放在解压根目录，避免旧包漏掉面板文件。

## 入口

- [当前接线](wiring_zh.md)
- [无需终端的日常操作](jupyter_zh.md)
- [旋钮及按键](controls_current_zh.md)
- 配套包：`delivery/visual_aid_v4_camera_detail_20261028_board.zip` 及 `.sha256`
- 打包：仓库根目录运行 `python tools/package_current.py`，不连接板子、不加载硬件。
- 主机软件检查：`python tools/test_software.py`。

## 重建与历史文件

`vivado/pins.xdc` 和 `docs/pins.json` 已是本版Arduino管脚。完整源码路径使用原有 `vivado/create_system.tcl`、`implement_system.tcl` 和构建脚本。
`vivado/implement_arduino_variant.tcl` 是当时复用已接受网表的构建入口，需要原 `build/source_optimized.dcp`；该中间checkpoint不在仓库，散列见 `reports/arduino_variant_lineage.json`。
跨电脑完整重建需要Vivado 2018.3，并核对本机路径与原工程保护步骤；不能把现成bit的实测结果当作新重建结果。
历史文档中的PMOD B、旧目录和 `--no-sensors` 只适用于旧快照；当前运行请按本页入口，保留 `--no-distance`。
