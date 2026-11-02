# 通用 PYNQ 框架技能包

面向使用 PYNQ 进行 PS/PL 协作的队伍，把“可运行一次”整理为“版本明确、可诊断、可复核”的工程交付。经验来自一个 PYNQ 视觉工程，但使用入口没有相机、图像算法、固定板卡、固定 IP 名称或固定寄存器地址。信号处理、采集、控制、加速计算等题目均可按自己的接口配置复用。

这是按竞赛 3.3.5.2 组织的独立 `skill/` 目录；也提供带标准 frontmatter 的 `skill.md`，可由支持该格式的智能体加载。不依赖 Codex、云端服务、账号或联网运行。

**通用性的准确含义：换题目、换板卡时复用流程、校验器和模板，重新生成匹配目标的 bit/HWH、PS 配置和约束。没有一份 bit 可以直接跨 FPGA 型号复用。** 本次只在电脑端运行新增脚本与故障注入，未重新连接板卡，也未做第二种板卡实测。

## 1. 陌生队伍快速开始

将整个目录复制到新工程根目录。离线校验器只需 Python 3.6+ 标准库；此次实际执行环境为 Windows/Python 3.12.7。没有在 Python 3.6 解释器上执行本包，兼容性声明是语法/API 设计目标。`metadata` 必须在有对应 PYNQ 运行时的环境执行，不建议在电脑上随意 pip 安装 PYNQ 来冒充目标环境。

从工程根目录执行（PowerShell 与 Linux shell 通用）：

```text
python -m unittest discover -s skill/tests -v
python skill/scripts/pynq_check.py env
```

然后复制并填写 `templates/board_profile.json` 为工程根目录的 `board_profile.json`。所有 `REPLACE_...` 项必须替换；示例地址不是板卡默认值，要从自己的 HWH/地址表填写。准备同名同目录的 `overlay/design.bit` 与 `overlay/design.hwh`，以及自己的入口脚本，例如 `app.py`：

```text
python skill/scripts/pynq_check.py seal . release_manifest.json overlay/design.bit overlay/design.hwh app.py board_profile.json
python skill/scripts/pynq_check.py verify . release_manifest.json
```

`seal` 只创建新文件，已存在的清单拒绝覆盖。首次封存前应确认构建来源；哈希只能判断与这份清单是否一致。修改载荷后，应审阅修改、新建版本和清单，再重新验收，不要用重算哈希掩盖意外篡改。

将工程复制到目标板，在镜像提供的 Python 中运行：

```text
python3 skill/scripts/pynq_check.py verify . release_manifest.json
python3 skill/scripts/pynq_check.py env --modules pynq numpy
python3 skill/scripts/pynq_check.py metadata . board_profile.json
```

`metadata` 显式使用 `Overlay(..., download=False)`，不会下载 bitstream，也不会读取活体 ABI 寄存器；构造对象仍可能初始化 PYNQ 驱动状态和访问设备元数据，不是完全脱离硬件的纯解析器。检查通过后，按 [上板流程](references/bringup.md) 使用自己的驱动进行限时验收。

## 2. 每项技能的适用范围、用法、效果与失效条件

以下“已验证”分为本次脚本测试和来源项目观察，均可在 [证据表](references/evidence.md) 找到对应记录；不将提示词写出等同于已完成跨队验证。

| 技能项 | 适用场景 | 使用方法 | 已验证效果 | 失败/观察来源与失效条件 |
|---|---|---|---|---|
| A. 载荷封存与完整性检查 | PYNQ bit/HWH、PS 软件、配置/依赖文件的交付 | `seal` 创建清单，`verify` 校验 | 本次注入篡改、缺失、目录越界、坏哈希，均能拒绝 | E1/E2：仅有“最新版”文件名不证明版本；清单不可信、遗漏成员、清单外新增文件均不被解决 |
| B. 环境能力预检 | 主机与板端 Python/依赖差异排查 | `env --modules pynq numpy`；按需求追加模块名 | 本次检查运行环境、必需模块缺失会失败；来源工程独立区分主机/板端预检 | E3：电脑测试通过不等于板端兼容；不安装依赖，不检查包 ABI/板卡电气条件；unknown 版本需人工补证 |
| C. Overlay/IP 元数据契约 | `.bit/.hwh` 型 PYNQ Overlay 接手与迁移 | 填板卡配置后运行 `metadata` | 本次用替身 Overlay 确认 `download=False`；IP 缺失、VLNV/地址变化均失败；两个不同 IP 契约可复用同一校验器 | E1/E4：旧引脚/软件与硬件版本混用风险；元数据可被错误配对，不能据此确认 FPGA 当前配置；不覆盖 xclbin/部分重配置 |
| D. 实现质量摘要门槛 | 完成布局布线后的建立/保持/DRC 与约束覆盖初筛 | 从原报告填写时序 JSON，运行 `timing` | 本次负裕量、缺失字段、NaN、DRC 错误、未约束内部端点均被拒绝 | E5：工具返回零与完整验收不同；摘要是人工输入，不解析 Vivado 报告，不签核 CDC、脉宽、总线偏斜及外部时序 |
| E. 黄金参考逐字比较 | 整数/定点加速器、数据采集、协议回环 | `compare golden.mem dut.mem --bits 32` | 本次覆盖一致、首个差异、截断、空数据、非法值及超字宽 | E6：软件/RTL/实物证据需区分；未统一字节序、符号、定点、帧顺序或含 X/Z 时不适用；不是浮点容差比较 |
| F. PYNQ 分层启动与 DMA 排错 | Overlay、寄存器、缓冲区、AXI/DMA 组合问题 | 按 `references/bringup.md` 逐层验收 | 来源项目有版本核对、限时运行及清理证据；新包流程未跨板实测 | E3/E7：无限等待与过早释放的风险；厂商/自定义 DMA、缓存 API、复位顺序需按实际版本适配 |
| G. 大模型协作提示词工作流 | 新题目的软硬件划分、瓶颈定位、重建与报告 | 复制 `references/prompts.md` 中任务段并补输入 | 来源工程形成可追溯纠错；新增软硬件划分/瓶颈提示词尚未做独立任务效果评测 | E2/E5/E8：缺输入时只能产出假设与待验证项；提示词不保证模型正确或自动提速 |
| H. 踩坑清单与验收模板 | 项目移交、失败定位、竞赛报告复现 | 按触发表查询 `pitfalls.md`，复制验收模板记录 | 来源项目保留旧失败，区分程序数据与人工观察；本次提供独立模板 | E2/E4/E7/E8：误填内容仍需人工核对；不能用文档齐全替代实板测试 |

## 3. 校验器命令契约

| 子命令 | 输入与输出 | 边界 |
|---|---|---|
| `seal ROOT MANIFEST FILE...` | FILE 用根相对路径、`/` 分隔；写 schema=1 的 SHA-256 清单 | 输出清单父目录须已存在；不覆盖，不扫描全部文件 |
| `verify ROOT MANIFEST` | 输出 `passed/files_checked/errors` | 仅校验清单成员；不追溯构建来源 |
| `env [--modules MODULE...]` | 输出 Python/OS/架构/解释器、模块版本和错误 | 模块按用户指定导入，可能执行其初始化；默认不导入任何第三方包 |
| `metadata ROOT PROFILE` | 同名相邻 bit/HWH；检查 required IP 的 type/phys_addr/addr_range | 允许额外 IP；配置里的板型/版本字段仅供记录，不自动验证；HWH 必须来自相同实现 |
| `timing METRICS [--min-setup N] [--min-hold N]` | 默认建立/保持 ≥0、DRC 错误与未约束内部端点=0 | 门槛仅接受有限非负数；保留原始报告及约束来源 |
| `compare EXPECTED ACTUAL --bits N` | ASCII 空白分隔十六进制字，可带 0x；索引从 0 开始 | 完全一致才通过；1–4096 位无符号整数；整文件读入，不适于超大捕获 |

退出码：0=所列检查通过；1=有效输入不满足检查；2=输入/环境/执行错误。除 `seal` 创建清单外，脚本不改写输入或配置硬件。JSON 标准输出可以重定向保存日志；PowerShell 保存 JSON 时建议使用 UTF-8。

其他入口：

```text
python skill/scripts/pynq_check.py timing skill/templates/timing_metrics.json
python skill/scripts/pynq_check.py compare golden.mem dut.mem --bits 32
```

时序模板故意填 `null`，第一条应失败，防止未填数据就获得 PASS。`golden.mem` 必须来自独立模型/规范，`dut.mem` 来自实际 DUT；复制 golden 作为 actual 只能验证文件读写，不能证明算法正确。

## 4. 换题目和换板卡

无需修改校验器：替换板卡配置、载荷列表、黄金参考与实际输出、时序摘要、验收条件即可。跨板迁移还需替换板级 PS/DDR、时钟、引脚、电压、目标 part 和镜像支持，再重新构建和上板。没有把来源工程的 20 FPS、寄存器地址、Arduino/PMOD 引脚、电压与温度阈值写成通用默认值。

最小新题目示例：做整数 FIR 时，用自己的 FIR bit/HWH 与 IP VLNV 填 profile；用独立 Python FIR 模型产出 golden，用 RTL/板端导出 dut；明确抽头、位宽、舍入与溢出，再执行比较。改为频谱分析或采集回环时重复同一流程，替换数据定义即可。此处是迁移示范，不是声称已完成这些题目实验。

## 5. 自包含证据与验收状态

- [验证与来源索引](references/evidence.md)：来源观察、适用范围、未验证项。
- `evidence/`：复制的历史协作/构建/技能测试记录及本次新增测试日志；历史文件不改写。
- `tests/test_pynq_check.py`：可在新队伍电脑重跑的真实故障注入。
- `templates/`：板卡/IP 配置、时序数据和验收报告。
- `package_manifest.json`：交付文件自身的 SHA-256；从工程根运行 `python skill/scripts/pynq_check.py verify skill skill/package_manifest.json`。

本包面向通用 PYNQ 的结构和可迁移入口已落实；跨板效果仍需接手队伍按流程实测。是否计入“通用 PYNQ Skill”加分由赛事评审认定。

## 本工程构建兼容入口

最新版通用工作流以上文 `scripts/pynq_check.py` 为主。仓库另外保留 `verify_hashes.py`、`check_timing.py`、`compare_words.py`、`test_validators.py`，供本工程根清单与 `build/reproduce.py` 调用；旧时序校验器不检查未约束端点，其通过不能替代新版时序流程及原报告审阅。旧方法见 [原项目工作流](workflow.md)。

按竞赛文件名约定，智能体入口命名为 `skill.md`；需要标准自动发现的工具可在自己的技能安装目录将它复制为 `SKILL.md`，仓库内保持小写。
