# 提炼来源、验证结果与边界

整理日期：2026-11-02（Asia/Shanghai）。以下来源是工程文件中已有的可见记录，没有将模型推测写成实测。历史材料复制到包内，路径/内容保持原样；其中指向旧工程其他文件的相对链接不一定在本技能包内存在，不代表那些原始大体积日志已全部随包提供。

## 来源索引

| 编号 | 失败或观察 | 可定位依据 | 提炼出的可复用规则 |
|---|---|---|---|
| E1 | 文件名“最新版”不足以确认板端版本；重建 HWH 字节不同但运行时字典可一致 | `evidence/historical_collaboration.md` 第3节；`historical_reproduction_status.json` 的 configuration_equivalence 与 pynq_24_parser_outputs_equal | 文件指纹与元数据语义分开检查；不把元数据等价写成文件字节相等 |
| E2 | 提交副本漏带 docs/pins.json，测试报 FileNotFoundError | `historical_collaboration.md` 第3节 | 封存依赖；新目录重跑，不能只复制主程序 |
| E3 | 原工程区分主机预检与 PYNQ 板端运行环境 | `historical_host_preflight.json`；来源运行时 preflight.py（来源目录见下） | 环境验证与硬件验证分层；unknown 或缺少运行时不能填为兼容 |
| E4 | 外设曾有不同接口/约束版本；版本切换不能沿用旧接线 | 来源 `skill/pitfalls.md` 的“传感器接口版本更换”；相关条目摘录于本页 | bit/HWH、约束、连接器与实物四方核对；不通用化具体管脚 |
| E5 | 旧检查点/绝对路径、完整 BD 构建的编码/入口错误 | `historical_collaboration.md` 第3节及“从零构建问题闭环”；`historical_reproduction_status.json` | 在新空目录独立重建；联合检查阶段结果、日志与源码指纹 |
| E6 | 固定 XSim 层次取不到带泛型的真实对象 | `historical_collaboration.md` 第3节 | 以实际层级查询为准；黄金数据、DUT 断言与波形是不同证据 |
| E7 | 原程序 display_observed 为空，用户另行确认画面和动态更新 | `historical_board_120s.md`；`historical_collaboration.md` 第2节 | 原始 JSON 保留，机器数据与人工观察单列；运行时长不外推 |
| E8 | 冻结/模式操作影响计数口径；没有严格同条件 AUTO A/B | 来源 `skill/pitfalls.md` 和 `report/reproduction.md`；协作记录说明不虚构量化结论 | 用独立任务计数和单调时间；做交替重复 A/B 后再宣称收益 |

来源目录（由本机读取，接手队伍运行脚本不依赖它）：

- `submission_work/fpga_vision/report/ai_collaboration.md`
- `submission_work/fpga_vision/build/results/reproduction_status.json`
- `submission_work/fpga_vision/build/results/preflight_host.json`
- `submission_work/fpga_vision/build/results/skill_tests.txt`
- `submission_work/fpga_vision/src/ps/runtime/preflight.py`
- `tmp/board_validation_20261028/validation_report.md`

E4/E8 的原始条目在整理时还从提交副本 `skill/pitfalls.md`、`report/reproduction.md` 读取：

> 传感器接口版本更换：PMOD 与 Arduino 管脚不兼容；核对 bit/HWH/ABI 与板上连接器，查 pins.json/XDC。文件映射不等于实物接线确认。

> 开启冻结/模式切换：render FPS 低于 capture FPS；记操作和时间，固定场景另做 A/B。差值不能推成 AUTO 性能损耗。

这些是本队工程的观察与风险总结，不表示所有 PYNQ 项目都发生过相同故障。DMA TLAST/缓存方向条目来自 bringup.md 的官方链接，是补充预防项。

## 历史项目结果能证明什么

- 旧技能校验器日志记录 9 项通过；这是旧校验器的结果，不是本包新增 24 项测试的结果。
- 旧构建记录列出 129 项主机检查、九组全分辨率 XSim、Vivado 2018.3 重建和时序值；本次未重跑 Vivado，不将记录日期改成今天。
- 2026-10-28 的板端摘要记录 120 秒、2392 独立采集帧、19.930 FPS、DMA/FIFO/坏帧错误为零、退出清理正常。它只覆盖那一版本和条件；这是摘要副本，并非所有原始采样文件都在本包。
- 旧报告中 60 秒功能验收与上述 120 秒验证为不同运行，不能合并时长或混用版本。新包没有宣称本次上板、跨板验证、长期稳定、功耗、光学效果或端到端延迟已测。

## 本包本次实际验证

执行：`python -m unittest discover -s skill/tests -v`。
环境：Windows AMD64，Python 3.12.7。日志：`evidence/selftest_20261102.txt`。

**共 24 项：23 项通过，1 项跳过，0 失败。** 跳过的是实际创建越界符号链接的测试，当前 Windows 不允许创建该链接；因此没有宣称该实物路径场景已执行成功。普通相对越界、绝对路径及盘符路径拒绝检查已通过。

| 验证类别 | 实际刺激与检查 | 覆盖结论 |
|---|---|---|
| 清单 | 真实临时文件的篡改/丢失、坏哈希、越界路径、重复封存 | 对应失败被检测；清单外文件故意允许，边界明确 |
| 环境 | 查询当前解释器，导入不存在的模块 | 缺少指定依赖会报错，不隐式装包 |
| 元数据 | 替身 Overlay、缺失 IP、VLNV/地址/范围变化、错名 HWH、拼错字段 | 替身收到 `download=False`；契约变更被拒绝，不证明真实 PYNQ 解析器或驱动兼容 |
| 迁移 | 用 FIR 与 FFT 两个不同名称/类型/地址契约调用同一检查器 | 证明校验逻辑可配置，不证明这些硬件设计已实现或跨板可运行 |
| 时序 | 正常、负裕量、非有限数、缺值、布尔值、DRC/未约束端点异常、无效门槛 | 不完备/不合门槛输入不能通过 |
| 黄金比较 | 一致、首个错字、截断、多余字、空输入、X/Z、负数、超宽 | 对精确无符号十六进制格式有效；合成测试不冒充实际 DUT |
| 命令接口 | 成功/检查失败/输入错误与重复写文件 | 退出码分别为 0/1/2，已有清单不覆盖 |

另执行技能 frontmatter 校验与独立解压后的脚本复跑，记录在 `evidence/package_qa.json`。语法兼容按 Python 3.6 解析规则检查，但 Python 3.6 运行时和不同 Linux/PYNQ 镜像未实测。

## 接手队伍要补的验证

在自己的目标镜像运行 metadata 和最小驱动；从独立参考生成真实 golden/DUT 输出；完成板级接线、时钟、复位、缓存、协议、停止/清理与限时运行验收；换板后从零构建并重做对应验收。按自己的目标提供吞吐、延迟或其他指标证据，不继承上述历史数值。
