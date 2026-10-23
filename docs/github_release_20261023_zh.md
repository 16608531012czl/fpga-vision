# OV5640 PL 升级发布（2026-10-23）

本次替换仓库中的旧工程文件，保留提交历史。当前实现是 PYNQ-Z2 / Vivado 2018.3 / PYNQ 2.4 的 OV5640 DVP 项目。

## 当前实测

- 验收发布：`2026-10-23T18:37:39.532825+08:00`。
- 720p、COLOR、1 倍、detail / stable，120 秒运行采集 2396 帧，独立采集 **19.971 FPS**。
- PL 渲染 **19.971 FPS**，完成 2395 帧，并采样确认 2395 次画布显示切换。
- DMA、FIFO 溢出、坏帧增量均为 0；正常退出，运行前后同一 boot_id。
- 建立余量 **+0.280 ns**，保持余量 **+0.032 ns**，DRC 错误 0。
- 90 项软件检查、快速/完整 720p 的九组仿真、随机背压连续流和组合图像管线检查通过。
- 实板自动检查覆盖 1/2/4 倍、冻结/平移、分屏/全屏、五种显示模式和显示缓冲区指针。
- 用户确认：清晰度接近原图；稳定亮度修正后，暗部跳动明显减轻或消失，文字仍清晰。

20 帧是当前已验证档位，HDMI 刷新为 60Hz；二者不是同一个帧率。不宣称相机硬件的绝对上限。
光学清晰度与闪烁改善为用户实物反馈，未进行仪器 SNR、MTF 或端到端延迟测量。

## 本次功能

采集与 PL 画布渲染并行，ARM 不再逐帧缩放、拼接实时画面。原始全帧与显示画布独立管理，
冻结源、渲染源、正在显示及等待显示的缓冲区均受保护。

加入 8×6 有界局部 tone mapping、块中心双线性增益过渡、保色重建、可选 PL 空间色度降噪、
15/31 窗口局部二值化和 PL 状态文字。局部映射以分块均值驱动，尚不是完整 CLAHE。

默认 **DN=0 / SH=4 / NR=1 / CT=0**，优先保留文字细节；长按 EC11 恢复此预设。
stable 提亮限制曲线变化速度和近黑增益，并扩大相机自动曝光保持区间；不依赖模糊画面减少闪烁。
选择 50Hz 防频闪，其他频率的照明环境需调整。balanced 预设仍保留较强降噪。

EC11 接线：S1→AR8，S2→AR9，KEY→AR10，3.3V 供电、共地。
光照模块本轮停用，提亮由图像统计驱动；无需额外硬件。

## 安装及启动

下载 `delivery/visual_aid_v4_ec11_board.zip`，解压到 `/home/xilinx/jupyter_notebooks`。
确保其他摄像头/HDMI 程序已退出；同时使用包内 `.bit`、`.hwh` 和脚本，不混用历史版本。

```bash
cd /home/xilinx/jupyter_notebooks/visual_aid_v4_ec11
sudo python3 preflight.py
sudo python3 run_board.py --stage live --pipeline pl --camera-fps 20 --mode color --quality-preset detail --tone-profile stable --no-sensors --af continuous --io-confirmed --seconds 0 --report logs/live_manual.json
```

按 Ctrl+C 正常退出。连续自动对焦启动包含 4077 字节固件完整回读，通常需约一分钟。
源码重建及算法边界见 `pl_upgrade_zh.md`；精确报告见 `reports/PL_UPGRADE_zh.md`。
