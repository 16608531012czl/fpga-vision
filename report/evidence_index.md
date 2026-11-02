# 当前证据索引

| 证据 | 当前含义 | 不覆盖 |
|---|---|---|
| `board/results/version_check.json` | 板上与本地关键文件 SHA-256 核对 | 非清单成员文件全部一致 |
| `board/results/summary.json` | 60 秒运行、版本、1199/1176 帧、错误增量、AUTO 参数和人工观察汇总 | 长测、严谨画质/性能 A/B |
| `board/results/board_run_raw.json` | 运行原始计数、状态、参数样本 | 静态旧验证标记可能未回填 |
| `board/results/report_board_test.json` | AUTO、MANUAL 接管、恢复、冻结恢复检查 | 未发生的全部场景 |
| `board/results/hdmi_observation.json` | 用户确认画面正常且运动更新 | 光学对焦和定量画质 |
| `sim/results/host_tests_20261030.txt` | 原运行 129 项主机测试 | 不能代替板端执行 |
| `build/results/host_tests.txt` | 提交副本重新运行的软件测试 | 新硬件功能 |
| `sim/results/reading_quick.log` | 32×24、20 帧、15360 像素 XSim 通过 | 全分辨率与全部协议情况 |
| `build/results/reproduction_status.json` | 本次从零仿真/构建结果与局限 | 不能默认新 bit 已上板 |
| `build/reference_reports/` | 原已验收 bit 的布线结果 | 与其他新 bit 的物理实现相同 |
| `data/history/` | 历史演进记录 | 最新 AUTO 的直接验收 |

原始文件中存在源电脑绝对路径和早期板日期，仅作为来源记录；运行入口均使用提交包相对路径和用户提供的工具目录。新证据不能反向修改原始记录。当前主机日期与用户观察用于解释板时钟未校准。原 manifest 的 false/null 未自动变更；本索引及具体实测组成补充证据。


## 本次从零构建状态

本次独立副本的 129 项软件测试、9 项技能校验和九组完整分辨率 XSim 已通过。从空目录创建 BD、综合、布局布线及 bit/HWH 生成全部完成；建立裕量 +0.189 ns、保持裕量 +0.014 ns，DRC 错误 0。新旧 bit 配置数据逐字节一致；HWH 文件存在导出元数据差异，但 PYNQ 2.4 解析得到的六类运行时字典一致。按团队要求保留已有实板证据，本轮未重新连接或操作开发板。
