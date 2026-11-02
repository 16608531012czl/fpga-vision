# 基于 FPGA 的实时视觉增强器

队伍：别急还在学二进制。提交整理日期：2026-11-02。运行代码版本：2026-10-30 dynamic AUTO v3。

基于 PYNQ-Z2（Zynq-7020 / xc7z020clg400-1）与 OV5640 的纸面阅读和近距离观察原型。PL 完成视频采集、缩放、分屏和像素增强，PS 管理相机、外设与动态 AUTO，HDMI 输出实际画面，网页负责控制和状态查询。支持五种显示模式、1×/2×/4×放大、平移、冻结和人工接管。

本仓库按竞赛要求组织工程包、最新版通用 PYNQ 技能包和设计报告。

## 已有工程指标

| 项目 | 已记录结果 | 原始证据与限制 |
|---|---|---|
| 器件与工具 | Zynq-7020，Vivado 2018.3 | `build/rebuilt_reports/` |
| 实现资源 | LUT 9957，FF 12443，BRAM 40，DSP 38 | `build/rebuilt_reports/system_utilization.rpt` |
| 构建时钟 | PS/AXI 100 MHz；相机输入约束 84.005 MHz | `build/rebuilt_reports/system_clocks.rpt`；约束值不是吞吐实测或 Fmax |
| 时序与 DRC | setup +0.189 ns，hold +0.014 ns，DRC 错误 0 | `build/rebuilt_reports/system_timing.rpt`、`system_drc.rpt`；同时审阅 CDC 与约束告警 |
| 历史实板 60 秒 | 采集 19.980 FPS，渲染 19.622 FPS；DMA/溢出/坏帧增量 0 | `board/results/`；含冻结操作，不是 AUTO A/B |
| 新增 AUTO 对照 | OFF/ON 19.897/19.889 FPS；CPU 43.92%/48.50% | 3 对约 20 秒现场短测；详见下方专项实测补充 |
| 新增连续运行 | 606.950 秒；19.876/19.878 FPS；46.63–49.34°C；错误及清理均 0 | 含光照变化与实体接管，不外推长期稳定性 |
| 功能验证 | 129 项主机测试、九组 XSim | `build/results/`、`sim/results/`；日期和版本见原日志 |

优化比较见 [优化说明](report/optimization.md) 和 [对比数据](data/optimization.csv)。不同条件的历史数据仅表示趋势。

| 目录 | 内容与入口 |
|---|---|
| `src/` | `pl/` 含 RTL、约束、BD Tcl、参考模型和厂商 IP；`ps/` 含当前板端软件、测试、引脚定义、bit/HWH 和 ARM 库源码。没有额外未使用的 HLS 工程。 |
| `sim/` | 九组 XSim 验证结果及 PASS 证据；testbench 位于 `src/pl/sim/`，验证入口为 `build/reproduce.py`。 |
| `build/` | 可复现构建脚本、已验收与重建的资源/时序/DRC 报告、重建 bit/HWH、来源和本次提交检查记录。 |
| `board/` | 原验收硬件与重建硬件各自的完整运行包；`results/` 保存 2026-10-30 原始实测输出。 |
| `data/` | 仿真输入与黄金参考、历史数据、优化比较表及报告指标表。 |
| `skill/` | 可复用 PYNQ 验证工作流、提示词、证据模板、踩坑清单、哈希/时序/黄金数据校验脚本与自测。 |
| `report/` | 用户提供的最新版 41 页 final 设计报告、协作记录、复现步骤、优化过程和证据索引。 |

## 从解压开始复现

1. 使用自己的 GitHub 权限克隆，或下载仓库 ZIP 后解压到英文路径。进入含本 README 的根目录：

```powershell
git clone https://github.com/16608531012czl/fpga-vision.git fpga_vision_enhancer
cd fpga_vision_enhancer
```

下载 ZIP 的用户直接进入解压目录，无需执行 clone。
2. 主机准备 Python、NumPy、OpenCV；硬件构建需要安装带 Zynq-7000 器件支持的 Vivado 2018.3。板端基线为 PYNQ 2.4、Python 3.6 和 NumPy 1.13.3；不要用主机依赖升级命令修改原板端环境。
3. 先在主机检查交付完整性和软件，再按需仿真与硬件构建：

```powershell
python -m pip install numpy opencv-python
python skill/verify_hashes.py . manifest.json
python build/check_submission.py
python -m unittest discover -s skill -p test_validators.py -v
python -m unittest discover -s skill/tests -v
python skill/scripts/pynq_check.py verify skill skill/package_manifest.json
python build/reproduce.py host
python build/reproduce.py full --vivado C:/Xilinx/Vivado/2018.3
python build/reproduce.py project --vivado C:/Xilinx/Vivado/2018.3
python build/reproduce.py implement --vivado C:/Xilinx/Vivado/2018.3
```

仓库用 `.gitattributes` 保留原始字节，避免跨平台换行转换破坏硬件清单。先校验再运行测试；测试或构建生成新输出后，严格全目录校验会提示文件集合发生变化，应使用新的干净副本复核交付。根清单应全部匹配；旧构建兼容校验器 9 项应通过；最新版通用技能测试共 24 项，Windows 可能因符号链接权限跳过 1 项。主机工程测试应为 129 项通过，预检为 `outcome=passed`。仿真应九组 PASS；构建必须同时满足日志 PASS 和时序/DRC 检查，不能只看进程退出码。主机验证不加载 Overlay。

构建生成目录为 `build/work/`，交付源码保持在 `src/pl/`。Windows Tcl 路径、工具路径和工作目录应使用英文路径。详细故障处理及每阶段 PASS 条件见 `report/reproduction.md`。

4. 断电接线：按 `src/ps/docs/pins.json` 连接 OV5640、EC11 和五向按键。BH1750 为 Arduino J3-10/P15=SCL、J3-9/P16=SDA，3.3 V、共地；HDMI OUT 接显示器。板卡与电脑接入同一可信局域网。
5. 将整个 `src/ps/runtime/` 复制到板端英文目录，或解压 `board/runtime_bundle.zip`。在板端运行目录执行：

```bash
/usr/bin/python3 preflight.py
sudo /usr/bin/python3 control_server.py --host 0.0.0.0 --port 8088
```

用板卡 IP 和终端给出的令牌打开网页，开始限定 60 秒运行；在 HDMI 上检查移动画面、模式、放大、AUTO/手动接管和冻结恢复，停止并保存新日志。`board/rebuilt_runtime.zip` 使用独立重建硬件，应单独验收。电脑模拟可执行 `python src/ps/runtime/control_server.py --simulate --host 127.0.0.1 --port 8088`。

## 结果与证据范围

历史实板 60 秒：采集 1199 帧 / 19.980 FPS，渲染 1176 帧 / 19.622 FPS，温度 47.37–48.11°C，DMA/溢出/坏帧均零；HDMI 画面和运动更新由用户确认。该运行含冻结，不能用两种帧率差计算 AUTO 开销。

2026-10-30 从零创建 BD、综合、实现和 bit/HWH 生成已完成，建立裕量 +0.189 ns、保持裕量 +0.014 ns、DRC 错误 0；报告与原始日志在 `build/`。新旧 bit 配置数据一致，HWH 的 PYNQ 2.4 六类运行时字典一致，不宣称 HWH 字节一致。九组完整仿真、129 项软件测试和 9 项技能测试的历史证据均保留。

2026-11-02 早期交付整理检查见 `build/results/submission_20261102/`、`build/results/github_update_20261102/`。之后已有补测：3 对约 20 秒 AUTO 开/关现场对照、约 607 秒连续运行、光照变化、EC11 实体接管和两档 ISP 原始图统计；详见 [专项实测补充](report/measurement_update_20261102.md)。本次仓库更新导入这些已有证据，没有重新上板或综合实现。严格隔离条件的 AUTO 因果开销、至少 30 分钟稳定性、HDMI 画质量化、端到端延迟、辨读正确率、功耗及光学重新合焦时间仍未验证。

项目对外名称统一为“视觉增强器”。`visual_aid` 等 Python 包名、RTL 实体、IP/ABI 和 bit/HWH 文件名保留原工程标识，确保导入、配套校验和重建入口可用。板端显示名称变更后已刷新内部 payload 清单；历史板端记录保留原字节，不能视为改名副本的新上板验收。

## 最新技能包与设计报告

最新版技能包主入口为 [skill/README.md](skill/README.md)，含八类方法的适用范围、使用方法、已验证效果、来源观察与失效条件。通用 PYNQ 流程不绑定本题相机、寄存器和引脚；换板仍需重新构建硬件并验收。旧校验器为构建兼容保留，独立使用优先采用新版。

设计报告入口：`report/design_report.pdf`；通用 PYNQ Skill：`skill/README.md` 和 `skill/references/bringup.md`。许可证和第三方来源见 `license.txt`、`third_party.md`。
