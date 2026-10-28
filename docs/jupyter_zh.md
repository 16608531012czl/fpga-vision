# Jupyter 一键运行（当前版本）

板端目录为 `/home/xilinx/jupyter_notebooks/visual_aid_v4_camera_detail_20261028`。
配套上板包解压到 `/home/xilinx/jupyter_notebooks` 后，应同时出现此目录和 `FPGAvision_OneClick.ipynb`。
目录内必须有 `jupyter_gui_guard.py`、`run_board.py`、`board/`、`visual_aid/` 和其他配套文件，不能只上传 Notebook。

## 已安装的板子：不用终端

1. 在 Jupyter 文件页打开 `FPGAvision_OneClick.ipynb`，选择 **Cell → Run All**。
2. 选择清晰模式或标准模式。标准模式切回相机基线 ISP 参数，PL 仍使用 detail 画质预设。
3. 定时运行：在“运行秒数”填正整数，例如 300、600、3600，再点击“按设定时长运行”。
4. 持续运行：点击“启动画面（持续）”。
5. 点击“停止”结束。等待状态变为“已停止”，再开始下一次运行。

计时从实时画面开始后计算，自动对焦固件初始化约一分钟另计。改秒数只影响下一次启动。
关闭网页不会自动停止程序。重新打开并运行 Notebook 后，可读取状态并请求停止已有进程。
画面输出到 HDMI 显示器，Notebook 显示控制按钮、状态、板温和报告结果。

## 首次安装

下载 `delivery/visual_aid_v4_camera_detail_20261028_board.zip`，在电脑解压。
通过 Jupyter 文件页上传解压出的项目目录及 Notebook，并保持上述目录层级；如果 Jupyter 5 的上传按钮不支持目录，可逐目录创建并上传，或使用 SFTP 上传整目录。
保留 PYNQ 2.4 原系统 Python 3.6、NumPy、OpenCV；不要把电脑端 Python 包装入板端环境。
面板使用 ipywidgets；本机实测版本为 7.4.2，widgets 扩展已启用，Jupyter 内核以 root 运行。
其他安装若缺少 widgets、扩展未启用或内核权限不足，需要先配置相应环境，Notebook 文件本身不能替代环境安装。
有同名旧项目时，先停止旧程序并备份目录，再整体替换；不要混用旧 bit、HWH 和脚本。

## 已验证

- 自定义 5 秒：自动完成，99 帧，约 19.818 FPS，DMA/溢出/坏帧均为 0，无清理错误。
- 持续运行（seconds=0）：点击停止后退出，reason=user_stop，无清理错误。
- `interrupted` 是手动停止留下的报告状态；同时检查控制状态和清理结果。
- 控制程序检查配套指纹、阻止并行启动，并在 XADC 达到 75°C 时请求停止。

软件时长参数也可用：`--seconds 300` 为 5 分钟，`--seconds 0` 持续至停止。
