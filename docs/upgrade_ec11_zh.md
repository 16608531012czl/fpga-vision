# EC11与边缘引导锐化升级 2026年10月22日

本次是比赛升级的第一阶段：硬件EC11解码、可调锐化、算法对照和状态显示。
2026-10-23追加时序流水线、画面合成加速和连续自动对焦，入口见[性能与对焦说明](performance_af_zh.md)。
PL 缩放分屏、局部映射、保色和阅读窗口升级见 [PL 图像链路说明](pl_upgrade_zh.md)。
保留上一阶段暗光 Gamma 策略；曝光闭环和几何矫正属于后续阶段。
本版独立目录为 `visual_aid_v4_ec11`，ABI为 `0x56410400`；不能与V3的bit/HWH混用。
内部比特流文件仍名为 `board/visual_aid_v3.bit`，以ABI和发布清单为准。

## 已确认接线

| EC11丝印 | 板卡插座 | 信号 |
| --- | --- | --- |
| 5V | J7第7脚 3V3 | 本模块按纯无源原理图使用3.3V供电 |
| GND | 公共地，分线至J7第2脚 | 共地 |
| S1 | J3第1脚，Arduino D8，V17 | enc_a |
| S2 | J3第2脚，Arduino D9，V18 | enc_b |
| KEY | J3第3脚，Arduino D10，T16 | enc_key_n |

供电端丝印虽然为5V，但不能在直接连接PYNQ信号时接5V。原模块上拉随供电变化。
这套接线已由用户确认连接；更换模块或改线后需要重新核对电平。
本模块S1/S2各有10k串联电阻和外部上拉，因此最终版本关闭这两路FPGA内部上拉；KEY仍启用内部上拉。
调试期间发现内部上拉版本AR9始终偏高。关闭后的实测结果以本次实板记录为准，不能只凭该修改推定故障已排除。

本次按用户要求将光照通信改为PMOD B：SCL→物理第3脚（T11），SDA→物理第4脚（T10）。
仅在加载本次PMOD B版本后使用该接法；不要把软件索引2/3误当成物理第2/3脚。
GY-302供电暂保持原3.3V与GND接法，信号上拉电平为3.3V，EC11仍为AR8/AR9/AR10。
原Arduino SCL/SDA接口不再用于本版本。原版发布包及约束保存在reports/attempts/before_pmod_b。
AR11/AR12只作过未通过的诊断，不作为本次接线。通信验收须同时具备地址应答和有效照度变化记录。

刚上电时，PYNQ的开机灯效服务会加载base.bit。本版在加载项目之前等待该服务的排队/运行任务结束，
避免已启动的测试被基础工程覆盖；不要在运行过程中从其他Notebook加载不同Overlay。

## 安装与第一阶段检查

先停止旧的摄像头/HDMI程序及相关Notebook内核，保留旧目录。
把 `visual_aid_v4_ec11_board.zip` 上传至 `/home/xilinx/jupyter_notebooks`，执行：

```bash
cd /home/xilinx/jupyter_notebooks
/usr/bin/python3 -m zipfile -e visual_aid_v4_ec11_board.zip .
cd visual_aid_v4_ec11
sudo /usr/bin/python3 preflight.py
sudo /usr/bin/python3 run_board.py --stage encoder --io-confirmed --seconds 60 --report logs/encoder_check.json
```

旋钮测试不启用摄像头/HDMI。正反旋转、短按、长按各做几次，应打印 rotate/short/long。
`position` 是每完整正交周期的计数；机械每一格对应多少周期以实物检查为准。
若顺时针方向与预期相反，加 `--encoder-reverse`，无需重新接线。
无操作时自动退出并不代表旋钮通过；必须有真实事件和双向计数记录。

随后检查画面：

```bash
sudo /usr/bin/python3 run_board.py --stage live --camera-fps 20 --mode color --sharp-mode guided --no-sensors --af continuous --io-confirmed --seconds 120 --report logs/ec11_live_120s.json
```

AF初始化可能需等待固件进度。需要单独排查时用 `--no-af`，未接光照模块时另加 `--no-sensors`。
默认同帧左右分屏：左原图、右增强。全部参数在下一次被接收的SOF统一生效。

## 操作

- 旋转：修改屏幕EDIT所指参数。
- 短按后松开：依次选择BRIGHTNESS、SHARPNESS、DENOISE、CONTRAST、ALGORITHM、NOISE、EDGE_VIEW。
- 按住约1秒：恢复参数默认值，不额外产生短按。
- BTN0：原图/灰度/反色/二值/彩色；BTN1：冻结；BTN2：分屏；BTN3：自动/手动亮度。
- 五向键继续负责ROI移动和1×/2×/4×缩放。

| 参数 | 范围 | 默认 |
| --- | --- | --- |
| BRIGHTNESS | -10～10 | 0 |
| SHARPNESS | 0～10，对应细节增益0～1.25 | 4 |
| DENOISE | 0～10，0关闭 | 4 |
| CONTRAST | 0～3，局部细节强度 | 1 |
| ALGORITHM | 0 OFF、1 USM、2 LAPLACIAN、3 GUIDED | 3 |
| NOISE | 0～10，边缘/细节抑制阈值档位 | 4 |
| EDGE_VIEW | 0正常、1 Sobel诊断 | 0 |

自动模式保留场景自适应Gamma，BRIGHTNESS作为用户偏好叠加；手动模式以恒等LUT为基准调亮度，自动策略不覆盖用户值。
屏幕CAM FPS为最近约1秒独立采集帧率；BASE LUT Y是用户亮度偏好之前的CPU查表估计，非HDMI测量。
源图统计取有效源ROI，在加入状态文字和HDMI黑边之前完成。

## 算法与边界

USM使用当前像素减尾随3×3均值；Sobel使用3×3窗口的绝对水平/垂直梯度和，再除8。
Laplacian使用同一尾随窗口的中心4邻域响应，再除4；这两个响应的窗口中心位于当前坐标前一行/前一列。
本版保持原工程的因果尾随窗口约定，不宣称与OpenCV居中填边实现直接逐像素等同。
GUIDED利用Sobel响应和细节阈值屏蔽弱变化，过强边缘减半，最终锐化增量限制为正负24级。
强边缘和平坦区仍需用真实印刷文字检查；阈值可能抑制很淡的笔画，可降低NOISE或切换USM对照。
局部对比度是另一项增强，噪声对照时先将CONTRAST设0，避免混淆来源。
RAW原样旁路；二值输出不使用连续灰度锐化结果；EDGE_VIEW诊断仅在非RAW模式下可见。

## 数据接口

既有低16位配置保留；0x30高位为本版可调参数：bit31高级处理使能，30:29算法，28:25锐化档位，
24:21噪声档位，20:17降噪档位，16 Sobel预览。单个32位配置在SOF锁存。
新增只读寄存器：0x50旋转计数、0x54稳定A/B与按下状态、0x58短按计数、0x5c长按计数、0x60非法正交跳变计数。
旋钮A/B采用100微秒稳定滤波、合法Gray状态解码；KEY采用25毫秒消抖。

## 验收

1. 旋钮双向、短按、长按分别可观察，静止时不持续跳值。
2. 调整亮度、锐化时画面变化；检查选择参数和数值同步，未跨模式被自动覆盖。
3. 同一固定场景比较OFF、USM、LAPLACIAN、GUIDED，保留纸面、细字、平坦背景和强边缘。
4. 暗光下记录噪点、笔画保留、光晕；亮度增加不能直接等同于可读性提升。
5. 保存照片与JSON。采集帧率、DMA错误/溢出/坏帧区间增量、清理状态分别记录。
6. 按键到可见变化的200ms是待测目标，当前软件事件日志不等于光学端到端延迟测量。

回退：退出本版程序，从保留的V3目录启动旧程序，旧程序将重新加载旧bit/HWH。
不要在本版目录中替换单个旧bitstream；发布清单和ABI会拒绝混用。
