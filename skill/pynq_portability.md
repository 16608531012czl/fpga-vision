# 通用 PYNQ Overlay 交付与分层验证

## 适用范围

适用于采用 bit/HWH 与 PS 程序配套部署的 PYNQ 工程，方法不依赖摄像头、增强算法或本队引脚。Python 标准库校验器可复制到其他工程。换题目后保留方法，换板卡后重新填写器件、PYNQ 版本、ABI、引脚、时钟、IP 与实板验收条件。

## 使用方法

1. 先固定配套清单，记录 bit/HWH、PS 脚本及资源的 SHA-256。使用 `verify_hashes.py ROOT MANIFEST` 检查根相对路径，清单格式参考本项目根目录 manifest.json 的 sha256 字段。
2. 以 `workflow.md` 的四阶段提示词固定版本、运行软件与仿真、核对硬件、生成证据报告；输入自己的工具路径和接口表。
3. 从实现报告导出含 setup_ns、hold_ns、drc_errors 的 JSON，以 `check_timing.py METRICS` 检查。根据自己的目标时钟核对约束覆盖，正裕量本身不能证明约束完整。
4. 对确定字宽和帧序的十六进制数据，用 `compare_words.py EXPECTED ACTUAL` 比较。EXPECTED 必须独立于 DUT 生成，不能复制为 ACTUAL。
5. 用 `evidence_template.md` 区分主机、仿真、构建、板端记录和人工观察。新板加载前核对电平和引脚，实板结果单独记录。

## 已验证效果

`python -m unittest discover -s skill -p test_validators.py -v` 包含 9 项自测，以临时文件主动注入丢失、篡改、越界、负裕量、NaN、DRC 错误、像素差异和截断等输入。主机原始结果在 build/results/skill_tests.txt；本次重验在 build/results/submission_20261102/skill_tests.txt。

该流程在本项目定位了提交副本遗漏 pins.json、旧版本标记混用、bit/HWH 来源不明以及 Tcl 路径/编码失败，形成 129 项软件检查、九组 XSim 与可追溯重建结果。详见 report/ai_collaboration.md。可复用性来自通用输入格式和失败检测；尚未在第二种开发板实物验证。

## 失效条件

清单被一并篡改时哈希无法建立信任；不在清单内的新增文件不由哈希脚本检测。错误时钟或漏约束可能让时序门槛通过。未定义 X/Z、字宽/格式/帧序不一致时黄金文件对比不适用。PYNQ 3.x/XRT、不同 CPU 架构或自定义驱动需要调整环境和加载步骤；本队 ARM 动态库不能直接用于所有板卡。工具自测通过不等于目标工程功能或上板通过。

## 经验来源

配对清单来自历史版本标记与当前程序不一致的观察；分层证据来自冻结期间采集/渲染 FPS 不可直接相减的失败推断；独立目录重跑来自遗漏引脚文件和工具路径编码问题。提示词要求显式提供输入、验收门槛和失败处理，防止仅凭“最新版”文件名或模型回答宣布成功。
