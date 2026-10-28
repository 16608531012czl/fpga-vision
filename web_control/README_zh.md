# FPGA Vision 网页上位机

基于同仓库的 OV5640 清晰模式版本，加入局域网网页控制、实体旋钮同步与运行状态回传。无需 Node.js 或联网前端资源；模拟服务仅需 Python 标准库，板端保留 PYNQ 2.4 / Python 3.6 环境。

## 下载与安装

- [独立上板包](delivery/FPGAvision_Control_board.zip) / [SHA-256](delivery/FPGAvision_Control_board.zip.sha256)
- [实板验收记录](delivery/board_validation/ACCEPTANCE_zh.md)
- [机器可读检查结果](delivery/validation.json)

将 ZIP 上传至开发板 `/home/xilinx/jupyter_notebooks/`，停止旧图像项目后在板端终端执行：

```bash
cd /home/xilinx/jupyter_notebooks
unzip FPGAvision_Control_board.zip
cd FPGAvision_Control
sudo /usr/bin/python3 control_server.py --host 0.0.0.0 --port 8088
```

已有同名目录时，先停止服务并备份该目录，再解压新包，不要混合不同版本文件。

电脑通过网线连接 PYNQ，在浏览器打开 `http://192.168.2.99:8088`，输入终端显示的临时控制口令。IP 不同则替换为实际板子地址。`0.0.0.0` 只是监听地址。服务重启会生成新口令；本仓库不包含当前设备口令。服务未配置开机自启。

相机、EC11、光照模块接线沿用 [当前接线](../docs/wiring_zh.md)：BH1750 使用 Arduino P15/P16，距离模块关闭。不要同时运行 Jupyter 图像程序和网页图像程序。

## 操作

1. 在“运行管理”选择清晰或标准相机模式；秒数填 0 为持续运行，300 为 5 分钟。
2. 点击“启动画面”，等待初始化约一分钟。时长从图像循环开始计算。
3. 画面就绪后，选择原图、灰度、反色、二值化或彩色增强。真实视频输出至 HDMI，网页没有视频预览。
4. “增强控制方式”提供 **AUTO 自动 / MANUAL 手动**。MANUAL 关闭全局自动提亮，局部明暗补偿仍独立受开关控制。
5. 调节亮度、锐化、降噪、局部对比度；滑块松开后提交。实体旋钮、按键与网页共享同一份状态。
6. 可使用 1×/2×/4×、方向移动、冻结和左右对比。“恢复默认”恢复画质参数，保留观察状态。
7. 点击“停止运行”，等待“已停止”。关闭网页不会停止图像程序；停止后显示“上次状态”。

USM、Laplacian、Guided 是锐化算法，不是三种二值化。当前二值化使用局部均值减 C，窗口可选 15/31。Guided 是项目的边缘引导锐化实现，不等于完整标准导向滤波。

## 无板模拟

在克隆仓库的根目录运行：

```powershell
python web_control/runtime/control_server.py --simulate --port 8088
```

打开终端打印的完整链接，或打开 `http://127.0.0.1:8088` 并输入该终端口令。也可以双击本目录的 `启动模拟控制台.cmd`。模拟不会访问板子，不生成假的 FPS、照度和温度。Ctrl+C 停止服务。

## 验证结果与边界

112 项主机检查通过（95 项原项目回归 + 17 项控制测试）。实际 PYNQ Python 3.6.5 已运行，网页自动/手动按钮也经过模拟 UI 切换与实板回传显示检查。

| 实板轮次 | 采集帧 | 采集 FPS | 结束方式 |
|---|---:|---:|---|
| 初次短测 | 598 | 19.946 | 30 秒定时结束；命令脚本接入晚，未完成全部命令 |
| 完整控制测试 | 594 | 19.780 | 30 秒定时结束；含冻结与恢复 |
| 现场交互 | 1407 | 19.900 | 约 71 秒后网页手动停止 |

完整测试 11 组命令全部确认，最大 ACK 93ms，越界参数被拒绝。三轮 DMA/溢出/坏帧均为 0，无清理错误。完整测试监控温度 45.16～47.25°C。用户确认 HDMI 正常、旋钮与网页同步；日志记录 23 个旋钮事件。

未做严格同场景 A/B 性能对比、长时间稳定性测试或所有高级参数的逐项光学验收。ACK 表示参数已被主循环接受，不等于光学输出验收。板端时钟未校准，原始报告文件名保留旧日期；验收日期为 2026-10-28。

## 开发与打包

`runtime/control_server.py` 管理网页/API/进程；`runtime/visual_aid/remote_control.py` 校验指令并收发命令；`pl_runtime.py` 的图像主循环统一修改 State 和寄存器。命令按会话隔离、2 秒过期，状态 250ms 发布、网页每秒轮询，超过 3 秒无状态则禁用控制。设备守护程序核验文件、阻止并行图像进程，达到 75°C 或温度读取失败则请求停止。

主机完整回归需要 NumPy 和 OpenCV；仅模拟无需安装它们。以下命令只在电脑执行，不要升级板端依赖：

```powershell
cd web_control
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install numpy opencv-python-headless
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
python build_delivery.py
```

打包脚本使用仓库原 `software/board/build_manifest.json` 核验 bit/HWH，重新生成软件指纹与 ZIP。bit/HWH 与原已验收版本一致；上位机不要求重新综合 FPGA。

本服务用于可信局域网，不应公网转发。许可证继承仓库根目录 LICENSE 和 THIRD_PARTY.md；配套 ZIP 包含第三方许可证。
