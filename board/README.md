# 上板运行

板端运行文件位于 `../src/ps/runtime/`，包含匹配的 bit、HWH 和运行软件。复制整个目录到 PYNQ 开发板的英文路径后，先运行 `python3 preflight.py` 检查文件及依赖。接线核对后，在该目录执行 `sudo /usr/bin/python3 control_server.py --host 0.0.0.0 --port 8088`，按终端显示的地址访问控制界面。实际显示通过 HDMI 输出。

新构建的硬件文件位于 `../build/rebuilt/`；更换 bit/HWH 时需同时更新发布清单并重新核验，勿混用不同版本。
