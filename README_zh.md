# FPGA Vision · OV5640 视觉辅助器

当前版本：**2026-10-28，Arduino 光照 + 清晰模式 + 流畅状态栏 + Jupyter 自定义时长**。
PYNQ-Z2 / Vivado 2018.3 / PYNQ 2.4，OV5640 DVP 输入、HDMI OUT 输出。

## 获取与运行

- [下载配套上板包](delivery/visual_aid_v4_camera_detail_20261028_board.zip) · [SHA256](delivery/visual_aid_v4_camera_detail_20261028_board.zip.sha256)
- [打开一键 Notebook 文件](delivery/FPGAvision_OneClick.ipynb)
- [Jupyter 安装及日常操作](docs/jupyter_zh.md) · [当前接线](docs/wiring_zh.md) · [旋钮及按键](docs/controls_current_zh.md)

板端已安装时，打开 `FPGAvision_OneClick.ipynb`，选择 **Cell → Run All**。
在“运行秒数”输入正整数，再点“按设定时长运行”；300=5分钟，600=10分钟，3600=1小时。
点击绿色“启动画面（持续）”可一直运行，红色“停止”结束。计时从实时画面开始，约一分钟的相机初始化另计。
关闭网页不会停止程序；运行中先停止再修改时长。首次安装需要完整项目和 widgets 环境，见上述说明。

## 功能与控制

原图/灰度/反色/二值化/彩色增强；1×/2×/4×缩放、平移、冻结、左右对比、自动提亮和连续自动对焦。
EC11短按选参数、旋转调数值、长按约1秒恢复画质预设。左上角 `EDIT` 显示当前项目。
Jupyter可选择相机清晰/标准模式；标准模式只回退相机ISP，PL仍用detail预设。

BH1750：3.3V供电、共地、ADDR接地；SCL→Arduino SCL/J3-10/P15，SDA→Arduino SDA/J3-9/P16。
**本版不用旧PMOD B的T11/T10接法。** 距离模块关闭，光照保持启用，启动使用 `--no-distance`。

## 验证

当前版120秒实板运行：2398帧，约19.980FPS；DMA/溢出/坏帧均为0，板温46.39–48.48°C。
用户确认近景文字清楚、远景正常，LUX遮挡后下降，状态栏操作顺畅。
自定义5秒自动结束及持续运行手动停止均已实测，无清理错误。
95项主机软件检查通过；本次上传未重新综合或加载硬件。
轻度锐化的边缘改善不代表光学分辨率提高，距离模块及所有场景最优效果未验收。

详见 [当前发布说明](docs/github_release_20261028_zh.md)、[相机实测](reports/CAMERA_VALIDATION_zh.md) 和 `reports/jupyter_duration_test/`。
基础构建清单中的pending字段保留为生成时状态，后续实测以这些记录为准。

## 工程

`rtl/`、`sim/`、`software/`、`vivado/`、`vendor/` 为源码、测试、运行文件、硬件脚本和第三方IP。
`source_manifest.json` 记录本次快照文件指纹；bit/HWH与软件负载保持已验收版本。
`docs/`中的旧日期文档与 `reports/historical_20261023/` 为历史资料，当前接线、目录、操作以上述入口为准。
主机端执行 `python tools/test_software.py` 检查软件；`python tools/package_current.py` 重新生成含Jupyter面板的上板包。
主机检查需 NumPy、OpenCV；不要向PYNQ 2.4安装主机依赖。Vivado完整重建和checkpoint变体边界见发布说明。

新代码按 [MIT](LICENSE)；第三方来源见 [THIRD_PARTY.md](THIRD_PARTY.md)。
