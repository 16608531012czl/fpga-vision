# 失败触发与排查

| 触发条件 | 观察/风险 | 排查和修正 | 验证边界 |
|---|---|---|---|
| manifest 旧字段未回填 | 新实测存在但仍显示未测试 | 保留原件，建立日期/版本对应的补充索引 | 新索引不能掩盖真实失败 |
| board 日历未校准 | 原始文件名出现 2019 日期 | 同时记录主机时间、monotonic 区间、运行文件指纹 | 不篡改原始板时钟证据 |
| 移植目录漏 docs/pins.json | 软件测试因 FileNotFoundError 失败 | 从相同版本补齐依赖，完整重跑 | 文件存在还需核对真实管脚 |
| 只看 Vivado 退出码 | 日志有错误仍被当作成功 | 同时检查返回码、ERROR/FATAL 和 PASS | PASS 覆盖范围取决于测试 |
| XSim 顶层含泛型值 | 按固定 /tb_reading 路径取信号失败 | 查看真实层次与 get_objects；按当前对象添加波形再 run all | 波形截图须伴随实际 PASS |
| 同一文件夹复用旧构建 | 仿真指纹与 RTL 不一致 | 新空目录复制源码，重新仿真/构建 | 不把旧 DCP 作为从零重建 |
| Windows 编码混杂 | 中文日志解码错误影响诊断 | 主机 Python 设置 PYTHONUTF8=1，保留原始日志 | 厂商日志可容错解码但不可忽略错误 |
| 传感器接口版本更换 | PMOD 与 Arduino 管脚不兼容 | 核对 bit/HWH/ABI 与板上连接器，查 pins.json/XDC | 文件映射不等于实物接线确认 |
| 开启冻结/模式切换 | render FPS 低于 capture FPS | 记操作和时间；固定场景另做 A/B | 差值不能推成 AUTO 性能损耗 |
| 主机默认 Python 代替板端 | 新 NumPy/API 在 PYNQ 2.4 不兼容 | 板上单独 preflight，再限时执行 | 主机通过不代表板端通过 |

本次 Vivado 2018.3 兼容问题已闭环：Tcl 显式使用 UTF-8，通过原生 PowerShell 调用厂商批处理并保留原环境，完整 BD、综合、实现与 bit/HWH 生成通过。预加载库和强制 TCL_LIBRARY/locale 的局部诊断不等于完整成功，不能作为最终通用修复。