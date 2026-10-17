# 当前 GitHub 发布快照

发布日期：2026-10-17（北京时间）。目标：加入逆光增强之前的电子视觉辅助器增强版。

## 包含与范围

- 五种显示模式：RAW、GRAY、INVERSE、BINARY、COLOR；增强流水线为原有8级。
- 已恢复原版 RTL、控制软件、测试、Vivado脚本、寄存器定义、接线图及19个配套发布文件。
- 两套 bit/HWH：默认弱上拉版本及 external_pullup 变体；硬件变体选择沿用原接线说明，外部上拉变体未在此次恢复后单独验证。
- 包含用到的第三方 IP/驱动和许可；不包含已撤销试验、个人认证文件、原始运行控制台、Vivado缓存或旧工程整棵目录。
- 本次发布按字节保留恢复的源代码及板端包，未修改算法或重新生成 FPGA 下载文件。

## 可复核文件

`source_manifest.json` 给出本次上传的文件 SHA256、Git blob SHA1、恢复点与板端配套信息。它不包含其自身指纹。
`software/board/build_manifest.json` 是原始发布清单，覆盖19个板端文件。`delivery/visual_aid_v3_board.zip.sha256` 校验可独立上板的压缩包。
原版发布清单中早期实板状态字段保留原样；之后的现场观察以 `reports/board_validation_20261017/README_zh.md` 为准。本次恢复运行只确认到采集/显示计数正常推进，未将它写成新的完整画质验收。

## 已执行与历史证据

本次恢复：73个备份文件指纹一致；42项主机软件测试通过；6项RTL快速仿真通过；10帧/7680像素逐点比对；Vivado GUI与独立框图校验通过。
原版布局布线：WNS +0.372ns、WHS +0.004ns、DRC 0 Error。资源为 LUT5588、FF9379、BRAM36等效22.5、DSP11。本次上传未重新综合/布线；报告来自与恢复 bit 配套的原版实现。
CDC报告仍保留既有异步复位结构提示，0 Error 不等于无警告；详见 `docs/validation_notes_zh.md`。
原版全720p仿真通过记录属于先前构建。本次恢复重新跑的是快速回归和GUI，没有重新跑完整分辨率仿真。
此前实板彩条约14.9997个独立采集帧/秒；实景含软件缩放/控制开销约11～13fps，场景及操作不同。HDMI60Hz不是摄像头FPS。具体采样窗口见实板记录，不能将历史值当作任意工况保证。
距离模块、30fps配置、光学端到端延迟、实物波形及多场景定量阅读准确率仍未完成验证。

## 在其他电脑使用

只运行：直接使用 `delivery/visual_aid_v3_board.zip`，解压到 PYNQ 新父目录，先 preflight，再 static/keys/sensors/colorbars/live。未连接测距模块时传 `--no-distance`。接线或模块电压信息发生变化时按原上板说明核对。

软件/RTL测试：在仓库根目录运行 README 中的 `tools/test_software.py`、`tools/verify.py`；Vivado路径用 `--vivado` 指定。`build.ps1` 的主机 Python/Vivado安装目录可用 `-PythonExe`、`-VivadoRoot` 覆盖。

框图和硬件：先 `.\build.ps1 -Step system ...` 生成 `build/system/visual_aid_v3.xpr`；Vivado Tcl Console 可按 `vivado/implement_system.tcl` 执行完整实现。更改RTL后先运行完整仿真，不能用本次附带的下载文件代替新源码实现。

原始 `build.ps1 -Step verify/bit/package` 会保护本机旧 `vision_enhancer` 与 `camera_hdmi_raw` 参考工程：检查表位于 `reports/original_project_before.json`、`reports/raw_baseline_before.json`，其中的根路径是原开发机绝对路径。这两棵旧参考工程不属于当前独立实现，也没有重复上传。克隆到其他电脑后，独立软件/RTL测试和现成板端包可直接按上文使用；要使用含旧工程保护的完整自动打包步骤，需自行提供对应旧参考目录并校准检查表路径，或先单独整理适合新环境的保护策略。不要伪造“原工程未变化”的检查结果来绕过此步骤。

本仓库的 `vendor/` 已包含当前硬件实际引用的IP和来源文件；不要把任意官方base.bit重命名为本项目下载文件。改变约束或生成新bit后，应重新核对bit/HWH与程序SHA256并形成新的验证记录。
