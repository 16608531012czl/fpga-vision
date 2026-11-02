# 从零复现操作

## 1 解压与环境

将压缩包解压至英文路径，如 `C:/work/fpga_vision`。保留根目录结构。需要 Windows、Vivado 2018.3（含 xc7z020 支持与有效授权）、Python（本次主机 3.13，安装 NumPy/OpenCV），板端原生 PYNQ 2.4（本次 Python 3.6.5、NumPy 1.13.3）。在已有可用环境中操作；不要用电脑 Python 包覆盖板端旧环境。主机新环境可执行 `python -m pip install numpy opencv-python`，本次实用版本记录于 `build/results/environment.json`，复现优先使用其版本。

在根目录依次运行 README 的 SHA-256、技能自测和 `host` 命令。预期哈希全匹配、技能 9 项通过、主机 129 项通过，preflight `outcome=passed`。这些步骤不会加载 overlay。若缺模块先补主机依赖；若哈希失败，重新解压核对版本，不能修改清单掩盖问题。

## 2 独立仿真与硬件构建

```powershell
python build/reproduce.py quick --vivado 'C:/Xilinx/Vivado/2018.3'
python build/reproduce.py full --vivado 'C:/Xilinx/Vivado/2018.3'
python build/reproduce.py project --vivado 'C:/Xilinx/Vivado/2018.3'
python build/reproduce.py implement --vivado 'C:/Xilinx/Vivado/2018.3'
```

首次步骤把 `src/pl` 复制到 `build/work`，在副本生成中间文件。quick/full 分别跑 reading、capture、registers、gamma、fifo、abort、encoder、canvas、kernels 九组；full 启用 1280×720 的相关测试，reading 逐像素对照 Python 黄金模型。查看 `build/work/reports` 中的 PASS、像素/帧数、完整源指纹。生成器与 testbench 存在实现相关性，不能替代独立实物验收。

project 从 Tcl 创建 PS7/DDR、控制核、显示 DMA/HDMI BD，不依赖任何旧 DCP。implement 要求当前 RTL 对应的 full 仿真指纹，通过后执行综合、布局布线、时序/DRC/CDC 检查并生成 bit/HWH。`build/work/build/visual_aid_v3.bit` 和同名 `.hwh` 为重建输出；`build/work/reports/system_timing_values.json` 为数值摘要。不要将新的 bit/HWH 自动覆盖已验收的 `src/ps/runtime/board`。

工程已存在时 project 会拒绝覆盖。需重新从零运行可指定新空路径，例如所有步骤统一加 `--work C:/work/fpga_rebuild_02`。工作目录必须配套使用；源文件变更后应另建副本重新仿真，不能复用旧指纹。失败查看 `build/results/*stdout.txt` 和工作目录原始日志，修正依赖/约束后重跑对应步骤。Vivado 返回零但没有指定 PASS 仍判为失败。保持裕量较小，应同时阅读 CDC、bus-skew 和时序告警，DRC 零错误不代表零告警。

本机兼容处理已验证：工程创建/实现 Tcl 首行设置 `encoding system utf-8`；reproduce.py 通过随包 invoke_vivado.ps1 调用厂商批处理，保留 Vivado 原有环境，不强制替换 TCL_LIBRARY 或 locale。此前的预加载尝试不属于最终复现步骤。原始失败日志作为纠错记录保留，最终综合、实现及输出均通过。

## 3 接线与版本检查

目标是 Arduino 光照接口版本。传感器 SCL=P15、SDA=P16，对应接线看报告中的 J3 图；不可沿用旧 PMOD T11/T10 版本。摄像头、EC11、按键全部 FPGA 管脚见 `src/ps/docs/pins.json` 与 `src/pl/vivado/pins.xdc`；端口方向、电压和连接器位置对照 `report/technical_notes` 与设计报告的电路图。所有接口使用对应 3.3 V 逻辑。接线核对完成后再运行硬件；项目测试脚本不会替代人工核对接线。

在板端停止正在运行的图像程序，避免两个进程争用 DMA/overlay。把整个 `src/ps/runtime` 目录复制到板上任意英文目录，例如 `~/jupyter_notebooks/fpga_vision_runtime`。电脑通过自己的 SSH 账号完成传输，包内不提供密码、会话令牌。

```bash
cd ~/jupyter_notebooks/fpga_vision_runtime
/usr/bin/python3 preflight.py
```

预期 `outcome=passed`、overlay_loaded=false，原生组合库可加载。若失败先修复文件配对和系统依赖。默认 bit SHA-256 为 `c47f82f7ad5bf47483d35763e4a73ce6c638dad67d11aade71085c108c3d343f`；默认 HWH 为 `45fcd9888bc97d4fc96e810593a9e566eecbe4e1475df04fbe49f9dde89911a9`，ABI 0x56410400。

## 4 上板运行与验收

```bash
sudo /usr/bin/python3 control_server.py --host 0.0.0.0 --port 8088
```

电脑访问终端打印地址（将 0.0.0.0 换为本次板 IP，保留临时令牌）。本命令启动实板服务；网页选择清晰模式和运行 60 秒。板端启动器固定使用 COLOR、PL、20 fps 档与 detail，运行前人工核对接线。当前环境曾用 192.168.2.99，仅作为示例，应以本次网络配置为准；直连时检查电脑同网段、路由、ping。网页负责发命令，板端主循环统一改状态与寄存器。

执行 60 秒验收：查看 HDMI 活画面；移动物体确认画面持续更新；观察 AUTO 状态和参数；切换 MANUAL 并调一个参数，等待至少 2 秒确认保持；恢复 AUTO；短暂冻结后恢复；停止。保存网页状态和 runtime/logs 中新生成的 JSON。程序运行时触发 Ctrl+C 或网页停止，等待子进程清理完成，再退出服务。不要直接删除仍在运行的进程的缓冲区。

不使用网页时，可在已确认接线且无另一个图像进程时运行：

```bash
mkdir -p logs
sudo /usr/bin/python3 run_board.py --stage live --pipeline pl --camera-fps 20 --mode color --quality-preset detail --tone-profile stable --af continuous --no-distance --io-confirmed --seconds 60 --report logs/validation.json
```

预期完成状态、错误增量为零、cleanup_errors 为空；确认版本和计数时间区间后计算帧率。没有 lux 不能填为零；不能把 HDMI 60 Hz 当作摄像头 60 FPS。显示黑屏时保留状态/日志，停止当前任务后检查接线、overlay 版本及视频时序。显著异常升温或供电异常时停止并断电，不做反复压力运行。

## 5 对照实验与复现交付

严格 AUTO 开销 A/B：同一板卡/bit/场景/灯光/镜头/分辨率/算法/CPU状态、锁定参数、不冻结不操作；AUTO OFF/ON 交替各运行 60 秒、至少 3 轮，保存温度、unique capture/render、时间戳和错误增量。以相同统计方法给均值及离散程度。在该实验完成前，本包不填写 AUTO 加速百分比、质量得分或功耗数值。现有历史趋势与本次功能验收见 `optimization.md`。

保留原始日志，另写主机日期、板上日期与用户观察；新重建 bit 的板上结果必须另存并标明其指纹，不能沿用旧 bit 的已验收标签。


## 本次从零构建状态

本次独立副本的 129 项软件测试、9 项技能校验和九组完整分辨率 XSim 已通过。从空目录创建 BD、综合、布局布线及 bit/HWH 生成全部完成；建立裕量 +0.189 ns、保持裕量 +0.014 ns，DRC 错误 0。新旧 bit 配置数据逐字节一致；HWH 文件存在导出元数据差异，但 PYNQ 2.4 解析得到的六类运行时字典一致。按团队要求保留已有实板证据，本轮未重新连接或操作开发板。

## 重建一致性复核

在根目录执行：

```powershell
python build/compare_hardware.py src/ps/runtime/board/visual_aid_v3.bit build/rebuilt/visual_aid_v3.bit
```

预期配置数据完全一致，PYNQ 2.4 的 IP、时钟、GPIO、中断控制器、中断引脚、层次六类字典全相同。bit 文件头有编译日期等差异；HWH 有时间戳、顺序、文档路径和 memory_bus 中额外未连接读通道描述差异，因此不宣称两个文件本身字节相等。该比较不是一次新上板测试。
