# OV5640 清晰模式与实板验证 — 2026-10-28

结论：已交付可选的相机轻度锐化模式，并通过 120 秒实时联合运行。用户反馈近景文字清楚、远景正常。它改善的是边缘呈现，不能替代光学合焦，也不能据此宣称光学分辨率提高或已达到所有场景下的最优画质。

## 修改与回退

新增 `--camera-isp` 选项。指定 `detail` 时，将 OV5640 的 ISP 锐化参数从基线 `0x5302=0x18` 调整到 `0x20`，并检查寄存器回读。其余原有相机分辨率、曝光策略、连续自动对焦、PL 管线、状态栏与光照功能保持原逻辑。

这是一种轻度锐化，可能放大暗部噪点或使字边偏重。省略该选项沿用原先画质预设映射；也可指定 `--camera-isp baseline` 回退。上一次的状态栏优化版本仍保留于 `C:\fpga\visual_aid_v4_light_ui_20261028`。

## 固定场景对照

近景纸面固定、自动曝光和增益临时锁定后，按基线—增强—基线—增强交替采样，并在结束后恢复原始寄存器。第一组可配准的图中，中心区域拉普拉斯方差分别为基线 183.05、增强 266.94；第二张基线为 178.70。增强图的黑色裁剪像素比例约 0.33%，基线约 0.14%。锐化和噪点都会影响边缘指标，这不是光学分辨率或主观清晰度的百分比。

复核发现第二张增强图相对首张基线的相位相关置信度偏低，故不用于量化结论。对照期间仍使用连续对焦，不能证明镜头位置完全未变。近景、远景的原始画面和测试记录保存在先前状态栏版本的 `reports/focus_compare_20261028_144511` 和 `reports/focus_compare_20261028_145348`，未放入发布包。

## 对焦边界

固件下载的 4077 字节回读一致，连续对焦命令应答。在固定场景的初始化阶段，曾读到固件报告对焦完成状态 `0x10`；但一次暂停对焦命令未应答，已恢复参数并改用连续对焦对照。最终 120 秒运行开始和结束的状态均为 `0x20`，不能作为光学合焦成功的证明。用户在完整实时画面下反馈近景清楚、远景正常。

## 实板联合验证

- 120 秒完成：独立采集 2398 帧，19.980 FPS；PL 渲染 2397 帧，19.980 FPS。
- DMA、FIFO 溢出和坏帧错误均为 0；159 个状态样本无光照通信错误。
- 带光照输入运行，自动亮度保持可用；距离模块关闭。
- XADC 温度 46.39–48.48°C；无清理错误、无运行警告。
- 本次无按键事件，因此不能据此额外宣称每个按键都经过本次验证。
- 95 项主机软件测试通过；FPGA bit/HWH 与通过验证的 UI 版本完全一致。

## 启动与回退

定时验证已结束。在板端运行以下命令启动持续运行的清晰模式，按 Ctrl+C 退出：

```bash
cd /home/xilinx/jupyter_notebooks/visual_aid_v4_camera_detail_20261028
sudo /usr/bin/python3 run_board.py --stage live --pipeline pl --camera-fps 20 --mode color --quality-preset detail --camera-isp detail --tone-profile stable --no-distance --af continuous --io-confirmed --seconds 0
```

如画面噪点或字边过重，把 `--camera-isp detail` 改为 `--camera-isp baseline` 再运行。相机固件初始化约需 47 秒。

## 证据

- 机器可读汇总：`camera_validation_summary.json`
- 实时报告：`board_validation_20261028/live_light_20261028_145722.json`
- 温度保护：`board_validation_20261028/live_light_20261028_145722_guard.json`
- 相机版发布包：`../delivery/visual_aid_v4_camera_detail_20261028_board.zip`
- 版本配套验证记录：`../delivery/camera_validation_20261028.json`
- 用户提供的模块指南：`C:\Users\CHENZHELONG\Desktop\FPGAvision\ZL0008\资料文档\OV5640_自动对焦照相模组应用指南(DVP_接口)__R2.13C.pdf`，第 42–45 页。
