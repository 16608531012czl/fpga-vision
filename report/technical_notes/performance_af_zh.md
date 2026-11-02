> 历史阶段文档：当前版本的接线、目录与启动请以 [2026-10-28发布说明](github_release_20261028_zh.md) 为准。

# 时序、帧率与自动对焦版（2026-10-23）

本文为上一轮 CPU 合成版本的性能基线。当前 PL 链路、默认 detail / stable 参数和本版实测，
见 [PL 升级说明](pl_upgrade_zh.md) 与 `reports/PL_UPGRADE_zh.md`。

默认balanced画质预设及彩噪处理见[画质说明](quality_zh.md)，
后续硬件扩展设计见[PL升级建议](pl_roadmap_zh.md)。

## 本版内容

FPGA处理时钟保持100MHz。Sobel/Laplacian分解到既有流水级，垂直累加与水平窗口求和之间增加一个弹性级，
保持每时钟一个像素的吞吐及算法整数结果。新增一个100MHz周期的延迟。
布线后全工程建立裕量由+0.146ns提高到+1.068ns，保持裕量+0.015ns，DRC错误0。
这些值是当前约束下的静态时序结果；不能直接换算成摄像头实际帧率或证明外部连线质量。

软件直接向已取得所有权的HDMI缓冲区合成画面，减少一次整帧复制；常用2倍缩小分屏使用ARM NEON。
场景亮度统计最多约160×90采样，亮度降噪与锐化在FPGA逐像素处理；
balanced预设另在ARM执行增强侧颜色时域降噪。
Gamma表由本地编译库执行256次有序的索引写入，再提交换表；忙状态时不写，换表边界仍由FPGA保证。

15、18、20、21帧档保持PLL分频0x41/倍频105，HTS分别1892、1577、1419、1351，VTS740。
由此缩短行空白，保持15帧档的PLL配置；没有仪器测得的外部PCLK值。50/60Hz曝光步长随实际SYSCLK/HTS重新计算并回读检查。
默认请求20帧；实际FPS以同一发布清单对应的实板报告为准。21/22/24/30档保留作诊断，未通过稳定性验收。
HDMI继续为720p60；屏幕CAM FPS计算独立接收的相机帧，不把重复刷新算作相机新帧。

连续自动对焦在摄像头初始化时自动启动，4077字节固件全部回读一致后才运行，并检查命令应答。
初始化约需47秒。AF CONTINUOUS表示连续模式已应答；AF ERROR表示失败，不能据模式名称推定已合焦。
软件状态0x10表示固件报告合焦，光学效果仍以实物观察为准。
用户已在15帧档观察到近处与远处移动后重新清晰，且确认旋钮正常。

## 上板运行

本轮按用户要求关闭外接传感器通信，暗光增强继续根据图像统计工作。光照模块保持原接线，不参与本轮验收。
先退出其他摄像头程序/Notebook。若本次后台演示正在运行，先停止它：

```bash
sudo systemctl stop visual-aid-v4-demo.service
```

将板端包解压至`/home/xilinx/jupyter_notebooks`后：

```bash
cd /home/xilinx/jupyter_notebooks/visual_aid_v4_ec11
sudo /usr/bin/python3 preflight.py
sudo /usr/bin/python3 run_board.py --stage live --camera-fps 20 --mode color --sharp-mode guided --no-sensors --af continuous --io-confirmed --seconds 0 --report logs/live_manual.json
```

Ctrl+C安全退出；不要同时启动另一份程序或加载其他Overlay。需要保守对照时改为`--camera-fps 15`。
`--no-af`用于排查对焦初始化，`--seconds 180`用于有限时长验收。
旋转调节EDIT选中参数，短按选择参数，长按约1秒恢复默认值；板载按键和五向键保持原功能。

本次后台演示使用临时服务`visual-aid-v4-demo`，断电重启后不会自动恢复。
查看运行：`systemctl status visual-aid-v4-demo.service --no-pager`。
停止：`sudo systemctl stop visual-aid-v4-demo.service`；停止后才会写出该次完整JSON报告。

## 验收证据

交付目录的`STATUS_zh.md`、`performance_summary.json`与源码包内`reports/board_validation_20261022`给出实测值和发布对应关系。
不要把早期失败测试或旧版用户反馈作为最终版本的长测通过。
报告分别记录独立采集FPS、DMA/溢出/坏帧增量、启动前后boot_id、AF回读结果和清理错误。
程序拒绝发布坏帧；输入错误会停止并保存诊断，不靠忽略错误提高FPS。

新增只读0x64寄存器通过既有异步FIFO传回EOF诊断：bit27 EOF，bit26完整有效，bit25:23原因，
bit22:12行号，bit11:0像素数。正常为行720、像素1280。
原因1行长不对，2奇数字节，3多余像素/行，4帧结束几何不符，5输入FIFO溢出。
它记录最近一次EOF，可能被下一帧覆盖；不是历史错误队列。ABI仍为0x56410400。

当前保持时间虽通过但余量较小；既有CDC/复位和厂商IP告警详见原始报告，不能宣称零告警。
FPGA资源报告、完整720p仿真、连续流随机停顿和软件测试均随包保留。
光学锐度、暗光噪点、合焦时间与端到端响应时间没有仪器测量值。

## 重建与回退

使用Vivado2018.3和本版独立目录的`build.ps1 -Step bit`重建硬件。
ARM库的源码在`software/native/compose.c`；板上编译及内存边界/逐像素检查脚本为`tools/board_native_build.py`。
将该脚本复制到板端运行目录根部执行，重新编译后的库及验证JSON需取回主机，
更新`reports/native_validation.json`、重跑软件测试并重新打包；发布清单会拒绝手工替换未经验证的库。
主机软件检查使用带NumPy/OpenCV的Python执行`tools/test_software.py`；原始环境与硬件操作见升级说明。
原OV5640 V3和上一发布包保留。退出本版后从旧目录加载配套bit/HWH/软件即可回退，不能单独混换bit文件。
