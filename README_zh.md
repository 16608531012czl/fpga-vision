# 自适应电子视觉辅助器 V3（独立工程）

工程路径：`C:\Users\CHENZHELONG\Desktop\FPGAvision\visual_aid_v3`。
旧工程 `vision_enhancer` 只作参考，未修改、未运行其中会写文件的构建脚本。
旧工程逐文件保护记录见 `reports/original_project_before.json`，复核结果见 `reports/original_project_check.json`。

## 当前完成范围

已实现软件与可综合 RTL：OV5640 8 位 DVP/RGB565 接收、跨时钟 FIFO、完整帧确认与 AXI DDR 写入；
3×3 降噪、15×15 简化局部对比度、自适应 Gamma 双缓冲 LUT、轻度锐化、灰度/反色/二值化/彩色增强；
1×/2×/4× ROI、移动、整帧冻结后继续缩放移动、同一帧同一 ROI 的左右对比；
五向键与板载按键、BH1750、VL53L0X、OV5640 自动对焦初始化、JSON 运行记录。

已删除旋转编码器、四个外置功能键和 PWM MOSFET 调光模块。补光灯独立供电/手动调光，不由 FPGA 控制。
保留光照、测距和五向导航开关；这些外设的具体模块版本仍须核对电压与引脚。

**仿真/软件完成不等于整机完成。** 本次交付不含冒充实板结果的 FPS、对焦距离或 HDMI 照片。
最新验证状态见 `reports/STATUS_zh.md` 与 `software/board/build_manifest.json`。
上板包为 `delivery/visual_aid_v3_board.zip`，包含两组配套 bit/HWH 和板端程序。
本轮仅完成电脑端工作，不以主机结果冒充增强版实板验收。

**上板时直接阅读 [完整上板操作](docs/board_bringup_zh.md)。**
该操作使用新的 `visual_aid_v3_enhanced` 板卡目录，保留已经出图的原图版本。
默认15fps为摄像头请求配置，不是增强版已测帧率。

## 在电脑上验证（Vivado 2018.3）

打开 PowerShell，执行：

```powershell
cd C:\Users\CHENZHELONG\Desktop\FPGAvision\visual_aid_v3
.\build.ps1 -Step verify
```

默认使用本机已存在的 Vivado 2018.3 和 `C:\fpga\vision\host_py313\Scripts\python.exe`。
更换电脑时使用 `-VivadoRoot` 和 `-PythonExe` 指定；主机 Python 需 NumPy、OpenCV。
**不要把主机 requirements 文件安装到 PYNQ 2.4 板卡上。**

单项命令：

| 命令 | 验证内容 |
| --- | --- |
| `.\build.ps1 -Step sim` | 小尺寸多模式/堵塞/异常帧/寄存器 XSim |
| `.\build.ps1 -Step full` | 1280×720 全帧增强与 DVP-to-DDR XSim |
| `.\build.ps1 -Step test` | Python 软件与协议边界测试 |
| `.\build.ps1 -Step preview` | 生成 PC 参考效果图，不算实板证据 |
| `.\build.ps1 -Step gui` | 创建并实际运行 Vivado 图形仿真工程 |
| `.\build.ps1 -Step synth` | 自定义 RTL 综合，非完整系统实现 |
| `.\build.ps1 -Step system` | 创建/复核独立 PS/DDR/HDMI 系统框图 |
| `.\build.ps1 -Step bit` | 独立整机综合、布局布线、时序/DRC/CDC检查，发布配套 bit/HWH 与板端ZIP |
| `.\build.ps1 -Step package` | 对已有构建结果重新核对并打包，不重跑布局布线 |

`verify` 要求日志含明确 PASS 标记，并检查退出状态；完整分辨率结果带 RTL 哈希。
该命令还会创建/刷新独立系统框图，复核旧工程文件，并更新 `reports/STATUS_zh.md`。
`bit` 在 RTL 与最后一次完整仿真哈希不匹配时拒绝继续。
修改 RTL 后先重新运行 `verify`；更改接口后重建新工程，不能借用旧 OOC 网表。

## 在 Vivado 界面中打开仿真

1. Open Project：`build\gui_sim\visual_aid_v3_sim.xpr`。
2. Sources → Simulation Sources，默认顶层 `tb_reading`。
3. Run Simulation → Run Behavioral Simulation。默认运行到 `$finish`。
4. Tcl Console / simulation log 中应出现 `PASS reading pixels=7680 frames=10`。
5. 波形观察 `vin/rin/uin/lin`、`vout/ready/uout/lout`、`din/dout`、`cfg`、`pending/bank`、`got`。
6. 测试其他链路：把 `tb_capture`、`tb_registers`、`tb_gamma`、`tb_fifo` 或 `tb_abort` 设置为 Simulation Top，再运行。

测试完成后如要重跑，先 **Restart**，再 Run All；不要在 `$finish` 之后直接 Run All，否则会继续到测试台看门狗。
完整 720p 仿真用 `-Step full` 最直接，避免 GUI 测试台参数与向量尺寸不一致。
测试台自带超时、逐像素断言、AXI 堵塞稳定性断言，不需要连接实体摄像头。
`tb_abort` 专门覆盖写地址、写数据或写响应堵塞期间停止采集，保证在途事务完成后才允许释放缓冲。

## 板上运行顺序（本轮不执行实板验证）

完整上传、接线、启动、通过条件与故障分支见 `docs/board_bringup_zh.md`。
推荐顺序：只读 preflight → static HDMI → keys → sensors → colorbars → live 无AF → live 加AF。
静态图不依赖摄像头；按键与传感器测试不启动 HDMI。

```bash
cd /home/xilinx/jupyter_notebooks/visual_aid_v3_enhanced
/usr/bin/python3 preflight.py
sudo /usr/bin/python3 run_board.py --stage static --io-confirmed --seconds 30
```

图像链路通过后再启动增强主程序；未接距离模块时保留 `--no-distance`：

```bash
sudo /usr/bin/python3 run_board.py --stage live --no-distance --io-confirmed
```

默认持续到 Ctrl+C，报告保存在 `logs`。程序结束会关闭 HDMI。
`--no-af`、`--no-light`、`--no-distance`、`--no-sensors` 可分阶段定位。
AF固件上传后进行全部4077字节回读；对焦异常记录警告，显示可继续。
传感器缺失记录 null 与具体错误，图像统计仍可参与自适应控制。
只有运行报告的 `measured_unique_capture_fps` 才是不同采集帧的测量值，HDMI60Hz不能替代它。

## 操作

| 输入 | 功能 |
| --- | --- |
| 五向上/下/左/右 | 移动 ROI，长按重复 |
| 五向中间 | 1× → 2× → 4× → 1× |
| BTN0 | 原图/增强灰度/反色/二值化/彩色增强循环 |
| BTN1 | 冻结/恢复；冻结保存完整源帧 |
| BTN2 | 同 ROI 左右分屏/全屏 |
| BTN3 | 自动 Gamma/固定手动预设 |

手动预设保留局部增强，Gamma 使用恒等表；没有编码器，因此不提供连续旋钮调参。
算法为简化局部对比度与均值阈值，并非完整 CLAHE、Sauvola、OCR、曲面展平或医学矫正系统。
空间窗口采用因果/尾随窗口；顶部/左侧不足窗口的区域回退到当前像素，不伪称中心对称滤波。

## 目录

`rtl`：硬件逻辑；`sim`：自检测试台；`software`：板端程序和 PC 参考模型；
`tests`：软件测试；`vivado`：独立项目脚本与 XDC；`vendor`：带来源与许可证的参考资料/IP；
`reports`：日志、测试记录和效果预览；`docs`：接线、寄存器与架构说明；`build`：仅新工程生成物。

第三方代码与固件来源见 `THIRD_PARTY.md`。构建脚本不调用旧工程写入入口。
