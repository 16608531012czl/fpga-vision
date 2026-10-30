# 应用背景 相关工作与软硬件划分

电子助视器已有“相机采集—屏幕放大显示”的应用基础。RNIB 对家庭辅助技术的介绍说明视频放大器通过摄像头与屏幕帮助查看文字和物体[1]。本项目定位于该场景的可复现 FPGA 原型，重点是连续视频下的图像增强、缩放分屏、实体控制与自动/手动协同；尚未进行用户群体阅读效率或临床评估。

图像增强相关研究中，He、Sun、Tang 的 Guided Image Filtering 根据引导图像与局部线性模型进行边缘相关滤波[2]，为边缘保持处理提供基础。本文引用其作为相关工作；项目代码的 guided 档位是工程内的边缘引导锐化实现，不据名称宣称逐式复现该论文或达到其指标。亮度映射、局部阈值与色彩降噪等模块以本项目 RTL 和 Python 参考模型为准。

PYNQ 将可编程逻辑封装为 overlay，由 Python 控制内存映射 IP；HWH 描述 IP、地址、时钟和中断等系统信息[3]。因此本系统采用 PS 管理状态和决策、PL 连续处理像素的划分：

| 功能 | 实现侧 | 划分依据 | 接口 |
|---|---|---|---|
| DVP 接收、格式/行帧检查、帧存储 | PL | 像素节拍与数据流连续性 | 摄像头并行接口、AXI/DDR |
| 增强、LUT、实时缩放/分屏/文字组合 | PL | 重复逐像素计算和确定时序 | 流数据、寄存器/LUT 双缓冲 |
| HDMI 输出 | PL + 官方视频 IP | 固定显示时序和串行化 | 显示 VDMA、TMDS |
| AUTO 图像统计与策略 | PS | 低频策略调整、便于修改与记录 | 只采样 ROI，状态映射到寄存器 |
| 网页/按键/编码器事件与模式切换 | PS 为状态拥有者 | 统一命令顺序与手动优先规则 | 网页邮箱、采样事件、控制寄存器 |

控制基址 0x43C00000，显示 VDMA 基址 0x43000000，ABI 0x56410400；寄存器位域以 `src/ps/runtime/visual_aid/device.py`、`pl_runtime.py`及 RTL 为准。HWH 与 bit 必须同包。网页控制线程传递命令，主循环执行状态与寄存器更新，减少竞争；双缓冲的提交边界与异常释放规则由测试验证。

本项目的可验证工程特点包括：独立采集与显示计数、PL 增强/缩放/分屏链路、ROI 驱动的有限速 AUTO、手动接管保持、可复现脚本及与版本绑定的板端证据。它们是本原型的实现特点，不宣称全球首次或未经比较的性能领先。

参考资料（检索日期 2026-10-30）：

1. RNIB. Assistive technology for blind and partially sighted people in the home. https://www.rnib.org.uk/living-with-sight-loss/assistive-aids-and-technology/everyday-tech/using-technology-at-home/
2. Kaiming He, Jian Sun, Xiaoou Tang. Guided Image Filtering. ECCV 2010. 作者项目页：https://people.csail.mit.edu/kaiming/eccv10/index.html
3. Xilinx PYNQ 官方文档源文件. Overlay Design Methodology. https://github.com/Xilinx/PYNQ/blob/master/docs/source/overlay_design_methodology/overlay_design.rst 。该在线说明用于概念介绍，实际环境锁定 PYNQ 2.4；工程携带该版本第三方 IP 与许可。
