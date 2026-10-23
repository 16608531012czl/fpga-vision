# OV5640 FPGA 视觉增强与电子放大阅读

PYNQ-Z2 · OV5640 DVP · 720p HDMI · Vivado 2018.3 · PYNQ 2.4

本次更新覆盖仓库内上一版工程文件，提交历史保留。当前版本将实时缩放、分屏和状态文字移入 PL，
采集与画布渲染并行，支持连续自动对焦、EC11 调参、冻结/平移和 1/2/4 倍放大。

**已实测：采集及 PL 渲染均为 19.971 FPS，120 秒无 DMA、溢出或坏帧错误。**
用户确认增强侧清晰度接近原图；暗部亮度跳动明显减轻或消失，文字仍清晰。

- [本次发布、安装及启动](docs/github_release_20261023_zh.md)
- [PL 算法、参数与功能边界](docs/pl_upgrade_zh.md)
- [完整实测报告](reports/PL_UPGRADE_zh.md)
- [上板压缩包](delivery/visual_aid_v4_ec11_board.zip) · [SHA256](delivery/visual_aid_v4_ec11_board.zip.sha256)
- [中文工程说明](README_zh.md)

默认 detail / stable：**DN=0、SH=4、NR=1、CT=0**。长按 EC11 恢复此预设。
局部映射使用 8×6 分块均值与双线性增益过渡，尚不是完整 CLAHE。
20 FPS 是本机当前通过验证的相机档位；HDMI 60Hz 刷新单独计数。

光照模块本轮停用。算法改善与清晰度为用户实物观察，未进行仪器 SNR、MTF 或端到端延迟测量。

## 源码重建

```powershell
.\build.ps1 -Step system
.\build.ps1 -Step test
.\build.ps1 -Step sim
.\build.ps1 -Step full
.\build.ps1 -Step bit
```

使用成套 bit/HWH 与软件。源码 `software/board/` 保存当前已验收文件；禁止混用旧版。
原有许可证及第三方来源见 [LICENSE](LICENSE) 和 [THIRD_PARTY.md](THIRD_PARTY.md)。
