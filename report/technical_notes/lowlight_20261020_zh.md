> 历史阶段文档：当前版本的接线、目录与启动请以 [2026-10-28发布说明](github_release_20261028_zh.md) 为准。

# 暗光提亮更新与上板检查（2026-10-20）

本次加强 ARM 生成的暗部 Gamma LUT，沿用现有 FPGA 双缓冲查表硬件。
无需重新生成 bitstream，无需新增传感器。本次尚未上板，不能以软件亮度代替实板观感、噪点或帧率测量。

## 更新内容

- 默认 `lowlight` 策略综合有效源 ROI 的平均灰度与第60百分位亮度，避免少量亮点掩盖整体暗光。
- 环境 lux 只在画面本身偏暗时加强提亮，正确曝光的亮画面不会因遮住 BH1750 而强行变亮。
- Gamma 指数最低0.35；在灰度224处衔接原曲线，224及以上的 LUT 值保持原值；近黑 LUT 放大不超过5倍。
- LUT 与场景统计按时间平滑，最快每0.25秒更新。光照切换后等待约3～5秒观察。
- 增加 `--mode color` 与 `--tone-profile lowlight/legacy`，旧策略可以直接比较。
- `LUT Y ... (EST)` 是源 ROI 经过 CPU LUT 的亮度估计，不是实际 HDMI 测量；PL 的局部对比度、锐化和颜色限幅仍可能改变最终像素。
- 亮部保护只针对 Gamma LUT；PL 原有锐化与局部对比度仍可能改变亮暗边缘。本次没有增加去噪算法或曝光控制。

## 电脑端证据

50项基础、暗光及运行日志集成检查通过，记录见 `host_validation/software_tests.json`。
恒定灰度图、lux=0、适应4秒，经过完整软件参考增强器的结果：

| 输入灰度 | 旧策略输出 | 新策略输出 |
| --- | --- | --- |
| 20 | 62 | 96 |
| 40 | 82 | 123 |
| 80 | 104 | 133 |
| 120 | 126 | 135 |
| 180 | 172 | 180 |
| 240 | 238 | 240 |

合成暗光阅读图平均灰度：原图53.2，旧策略88.3，新策略133.1。
对比图和原始数值见包内 `host_validation/lowlight`。这些是合成图结果，不能证明真实暗光细节恢复。

## 上传并安装到独立目录

结束旧的摄像头/HDMI程序和相关 Notebook 内核。保留旧版目录，不要同时运行两个显示程序。
把 `visual_aid_v3_lowlight_20261020.zip` 上传至板卡 `/home/xilinx/jupyter_notebooks`，在 Jupyter Terminal 执行：

```bash
cd /home/xilinx/jupyter_notebooks
/usr/bin/python3 -m zipfile -e visual_aid_v3_lowlight_20261020.zip .
cd /home/xilinx/jupyter_notebooks/visual_aid_v3_lowlight_20261020
/usr/bin/python3 preflight.py
```

预期 `outcome: passed`。如有 hash mismatch，重新上传整包，不要把两版脚本和清单混在一起。
沿用 PYNQ 2.4 自带 Python/NumPy/OpenCV；本次没有新增板卡依赖。

## 第一次只验证提亮

摄像头、HDMI和传感器保持之前已核对的接线。尚未确认硬件兼容时，先按 `board_bringup_zh.md` 完成检查。
使用已验证的同一接线时运行：

```bash
sudo /usr/bin/python3 run_board.py --stage live --mode color --tone-profile lowlight --no-distance --no-af --io-confirmed --seconds 60 --report logs/lowlight_60s.json
```

此命令先关闭自动对焦以减少变量；镜头已对焦时观察提亮即可。需要重新对焦时去掉 `--no-af`。
未接BH1750时额外加 `--no-sensors`，图像统计仍会提亮，LUX应显示“-”。
程序默认分屏，左原图、右增强；默认AUTO。首次对焦固件不在这条无AF命令内上传。

验收步骤：

1. 固定相机和纸张，确认屏幕为 `COLOR`、`AUTO`、`LOWLIGHT`。
2. 降低被摄物实际照明，避免仅遮住光照传感器。等待3～5秒，看右侧纸面是否比左侧明显变亮。
3. 检查小字、噪点和彩色物体；亮度变高不等于细节一定更清晰。
4. 恢复照明，观察提亮逐渐减弱，不应持续把正常画面抬白。
5. 保存屏幕照片和日志；核对 `tone`、`sensors`、错误计数增量、`measured_unique_capture_fps`。

`RAW`、`BINARY` 模式绕过此提亮结果，屏幕会提示 `TONE BYPASS`；BTN0切换至COLOR或GRAY。
BTN3关闭AUTO时显示 `TONE OFF (MANUAL)`。`INVERSE`使用Gamma后反色，不能用作普通提亮对比。

## 对照旧策略与回退

等上一条命令完全退出并关闭HDMI后，在同一目录、同样场景运行：

```bash
sudo /usr/bin/python3 run_board.py --stage live --mode color --tone-profile legacy --no-distance --no-af --io-confirmed --seconds 60 --report logs/legacy_60s.json
```

这会使用此前的Gamma策略。若要回到原发布程序，结束本程序，再从保留的旧版目录启动原命令。
电脑端修改前备份位于工程 `backups/lowlight_before_20261020_165013.zip`，包含旧程序、清单和旧上板包。

如果新策略下LUT估计已上升但屏幕差异仍小，先保留屏幕照片和日志，核对模式、AUTO及实际加载目录。
若原图接近全黑且噪点明显，下一阶段再检查摄像头曝光/增益或实际补光；本更新不能凭空恢复未采集到的细节。
