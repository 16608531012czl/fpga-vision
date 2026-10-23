# 增强版上板操作：PYNQ-Z2 / PYNQ 2.4

本独立副本已于2026-10-22升级EC11和边缘引导锐化，请优先阅读 [本版安装与验收](upgrade_ec11_zh.md)。
下文旧版安装目录和历史实测不代表本版验收结果。

2026-10-20 暗光软件更新使用独立包/目录 `visual_aid_v3_lowlight_20261020`，
请优先按 [暗光更新步骤](lowlight_20261020_zh.md) 安装和比较。下文旧包的历史验证不代表本次暗光策略已经上板。

本包包含独立增强版 bit/HWH、板端程序、OV5640 对焦固件和配套校验清单。
电脑端验收见 `host_validation` 与 `board/build_manifest.json`。
2026-10-17 已在本台 PYNQ-Z2 完成基础实板验证，显示、按键、BH1750、实景增强与连续自动对焦均通过；
实际帧率与用户观察见 [首次实板验证报告](../reports/board_validation_20261017/README_zh.md)。
长时间稳定性、端到端延迟、30fps 配置和距离模块仍未验证。更换硬件或改线后应重新按下面步骤验收。

## 1. 保留原图版本，安装到新目录

不要覆盖已验证的 `camera_hdmi_raw`，也不要加载旧 `vision_enhancer` 的 bit/HWH。
本包目标目录为 `/home/xilinx/jupyter_notebooks/visual_aid_v3_enhanced`。
若该目录已有旧版本，先结束相关程序并备份该目录，再解压新包。

在 Jupyter 文件页把 `visual_aid_v3_board.zip` 上传到 `/home/xilinx/jupyter_notebooks`，
然后打开 New → Terminal：

```bash
cd /home/xilinx/jupyter_notebooks
/usr/bin/python3 -m zipfile -e visual_aid_v3_board.zip .
cd /home/xilinx/jupyter_notebooks/visual_aid_v3_enhanced
/usr/bin/python3 preflight.py
```

预期：JSON 中 `outcome` 为 `passed`。此命令只检查文件与运行环境，不下载 bit、不操作引脚。
如果提示 `hash mismatch` 或缺少文件，重新传输整包；不要混用不同版本的脚本、固件或 HWH。
沿用 PYNQ 2.4 镜像自带的 `/usr/bin/python3`、NumPy 和 OpenCV，不要安装电脑端 requirements。

## 2. 接线与供电

断电后按 `docs/wiring_zh.md` 接线。摄像头使用板载 24MHz 晶振，不另外连接 XCLK。
五向模块只接 COM、UP、DWN、LFT、RHT、MID 六根线，SET/RST 不接；COM 接 GND。
保留板载 BTN0..3；本次EC11扩展接线按 `upgrade_ec11_zh.md`，其他旧版操作仍可参考本文。
摄像头、开发板和外设共地；补光灯独立供电、手动调光。

提供两组同版 bit/HWH：

| 配套文件 | 摄像头 SCCB 上拉 | 使用条件 |
| --- | --- | --- |
| `board/visual_aid_v3.bit` + 同名 HWH | FPGA 内部弱上拉 | 对应此前用户已确认、原图版本已出图的同一模块/接线 |
| `board/visual_aid_v3_external_pullup.bit` + 同名 HWH | 关闭 FPGA 内部上拉 | 外部已有合适电压的上拉/电平接口 |

`--io-confirmed` 是操作者已核对电压与接线的声明，不是软件自动检测。
3.3V 电源输入不等于所有摄像头 IO 都允许 3.3V；更换模块时应重新核对。
当前资料有多份模块原理图，不能把其中一份的电气设计套用于所有同名 OV5640 模块。
内部弱上拉也不等同于已经测量通过的总线波形；另一组 bit 仅改变上拉，不代替电平转换电路。

## 3. 先检查静态 HDMI

关闭所有占用 HDMI 的旧 Notebook 内核和旧程序。显示器连接 **HDMI OUT**，选择相应输入。

```bash
sudo /usr/bin/python3 run_board.py --stage static --io-confirmed --seconds 30
```

通过条件：显示器出现从左到右的蓝、绿、红色块和文字，保持稳定。
该阶段不初始化摄像头，不启用图像增强，不依赖摄像头数据。
程序结束会关闭 HDMI，因此结束后黑屏属于正常行为；省略 `--seconds` 可保持到 Ctrl+C。
屏幕不出图时先查 HDMI OUT、显示器输入与其他进程占用，不要同时修改摄像头寄存器。

## 4. 单独检查五向键和板载按键

```bash
sudo /usr/bin/python3 run_board.py --stage keys --io-confirmed --seconds 30
```

该阶段不启动 HDMI 或摄像头。依次操作后，应打印：
`up / down / left / right / zoom`、`mode / freeze / split / auto`。
方向键长按应重复，中心键与板载功能键每次按下只触发一次。
若无事件，先查 COM 是否接地、是否误用了 40 针脚号和 Arduino D 编号。

## 5. 单独检查光照与距离

先接已提供资料的 GY-302/BH1750。没有连接 VL53L0X 时使用：

```bash
sudo /usr/bin/python3 run_board.py --stage sensors --no-distance --io-confirmed --seconds 10
```

通过条件：`lux` 为有效数值，遮挡/照明变化时读数相应变化；不得把 null 当作 0 lx。
程序按 BH1750 的 0x23 地址、连续高分辨率模式和至少180ms首次等待处理。
GY-302 所给原理图含板载稳压器，SCL/SDA 上拉接在稳压后电源；应按实物核对上拉电压，不能只看供电标注。
若用 3.3V 接其 VIN，还应确认稳压后芯片电源没有低于数据手册的 2.4V 下限。
缺失/错误信息保留在 `errors` 中；`sensor_readings_observed` 说明本次是否读到有效数据。

VL53L0X 模块型号、电源与接口确认并连接后，再去掉 `--no-distance` 重跑。
其默认地址为0x29，与 BH1750 共用 SDA/SCL；超时或超量程显示 null，不阻塞主显示循环。
仅运行传感器程序成功退出不等于两个模块都验收成功，必须检查各项有效读数。

## 6. 检查摄像头内部彩条

```bash
sudo /usr/bin/python3 run_board.py --stage colorbars --camera-fps 15 --io-confirmed --seconds 30
```

通过条件：摄像头 ID 为0x5640，输出尺寸1280×720，显示器上彩条完整、稳定，无错行或撕裂。
此阶段自动关闭 AF、外设和增强。软件固定使用0x4740=0x20，与当前接收器同步极性一致。
日志中的15fps是请求的摄像头配置，实际帧率只看运行报告中的 `measured_unique_capture_fps`。

若出现 `I2C NACK writing 0x78`：先查摄像头供电、共地、SCL/SDA、RST/PD和上拉，
不能由 NACK 直接判断摄像头损坏。若 ID 正确但整帧超时，查 D0..7、PCLK、VS、HREF与线长。
遇到这一步失败，先保留报告，不要直接跳到完整增强或对焦。

## 7. 运行增强，最后加入对焦

先验证不依赖对焦和距离模块的增强画面：

```bash
sudo /usr/bin/python3 run_board.py --stage live --no-af --no-distance --io-confirmed --seconds 60
```

BH1750尚未接好时另加 `--no-sensors`，图像亮度统计仍可驱动自适应 Gamma。
左右两边显示同一源帧、同一 ROI 和同样的缩放，左侧原图，右侧增强。

| 操作 | 功能 |
| --- | --- |
| 五向上/下/左/右 | 移动 ROI，长按重复 |
| 五向中间 MID | 1×/2×/4× 循环 |
| BTN0 | 原图/灰度增强/反色/二值化/彩色增强 |
| BTN1 | 冻结/恢复；冻结后仍可移动与缩放完整源帧 |
| BTN2 | 左右对比/全屏 |
| BTN3 | 自动 Gamma/固定手动预设 |

随后启用连续自动对焦：

```bash
sudo /usr/bin/python3 run_board.py --stage live --no-distance --af continuous --io-confirmed
```

AF会上传4077字节固件，并回读全部固件校验后启动；初始化需等待终端进度。
`--af single` 为单次对焦，`--no-af` 为诊断回退。
AF固件/命令错误会记录警告并继续显示；命令 ACK 或固件状态不等于人眼已经观察到文字清晰。
对焦效果必须用印刷小字、不同阅读距离和照明条件实际检查。

默认程序持续运行到 Ctrl+C，避免演示时因固定60秒退出而误认为故障。
后续稳定性验收可加 `--seconds 600`，再进行更长时间测试。

## 8. 保存证据与回退

每次运行末尾打印报告路径，默认在 `logs/阶段_时间.json`。
保存屏幕照片及该报告，核对摄像头/显示帧计数、DMA错误、溢出和坏帧的**测试区间增量**。
`display_observed` 默认为空，需要人工看屏确认；程序不会自动冒充物理显示已验收。
独立摄像头帧率与 HDMI 60Hz 刷新分别记录，冻结画面也不能当作相机停止采集。
`timing_ms` 是软件阶段耗时，不是完整光学端到端延迟。

若增强版实物验收失败，结束该程序，再从保留的原图目录运行其已验证脚本和原配 bit/HWH。
不要把原图 bit 改名成增强版：ABI和文件校验会拒绝不匹配的组合。

硬件引脚来源：[PYNQ-Z2 厂家参考手册 v1.1](https://dpoauwgwqsy2x.cloudfront.net/Download/PYNQ_Z2_User_Manual_v1.1.pdf)，
光照时序与电压范围依据用户提供的 BH1750FVI 数据手册，模块接法依据用户提供的 GY-302 原理图与五向按键商品图。
