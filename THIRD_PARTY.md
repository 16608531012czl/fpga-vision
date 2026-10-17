# 来源、修改与许可

- `vendor/pynq_video_procs.tcl`：从本机 `C:\fpga\vision\PYNQ\boards\Pynq-Z2\base\base.tcl` 提取的层级过程，仅使用 HDMI OUT 部分。
- `vendor/pynq_ps7.tcl`：同一官方 PYNQ v2.4 脚本的 PS7 配置；新工程另行禁用未使用端口。
- `vendor/ip`：从同一 PYNQ 本机副本复制的 axi_dynclk、rgb2dvi、color_swap、接口定义，以及 color_convert/pixel_unpack 已导出 HLS IP。
  原始版权/许可保留在各文件及 `vendor/PYNQ_LICENSE`、`vendor/PYNQ_THIRD_PARTY_LIC`。本次没有声称重新导出了 HLS。
- `vendor/esp_ov5640*`：Espressif esp32-camera，固定提交记录于 `esp32_camera_revision.txt`；Apache-2.0，许可见 `ESP32_CAMERA_LICENSE`。
  从默认寄存器表解析数字配置到 `software/assets/ov5640_720p.json`，未执行下载的 C 代码。
- OV5640 720p 时序：用户提供的 `ZL0008/资料文档/OV5640_自动对焦照相模组应用指南(DVP_接口)__R2.13C.pdf` 第23～24页。
  采用 24MHz 输入时钟的 15/30fps 寄存器候选配置，再设置 RGB565；实际硬件/时序/FPS 未验证。
- `software/assets/ov5640_af.bin`：由用户提供的 `ZL0008/ESP32S3_OV5640_WiFi/ov5640_af_firmware.h` 提取，4077 bytes。
  来源路径、SHA256 记录于 `vendor/af_firmware_source.txt`；这是传感器固件数据，不是新编译出的 FPGA bitstream。
- `software/visual_aid/vl53l0x_vendor.py`：Adafruit CircuitPython VL53L0X（MIT），固定提交见 `vendor/vl53l0x_revision.txt`。
  原文件保留在 vendor；修改为本地 I2C 适配器、移除类型注解以兼容 Python 3.6、用普通函数替代 micropython.const。
  版权头保留，许可为 `vendor/ADAFRUIT_VL53L0X_LICENSE`；其源代码亦注明参考 Pololu 驱动。
- `vendor/original_*`：旧项目的许可/来源说明副本；旧项目本体没有修改。

公开参考：

- https://github.com/Xilinx/PYNQ/tree/v2.4/boards/Pynq-Z2
- https://github.com/espressif/esp32-camera
- https://github.com/adafruit/Adafruit_CircuitPython_VL53L0X
- https://dpoauwgwqsy2x.cloudfront.net/Download/PYNQ_Z2_User_Manual_v1.1.pdf

新写的 RTL、控制/模型代码、测试与构建脚本按本目录 MIT 许可提供；不改变上述第三方部分的许可。

增强版上板完善阶段只读参考了独立 `camera_hdmi_raw` 子工程中的 IOB 采样、DMA 行计数、PYNQ 2.4 接口绑定、
缓存/BGRX 交接、SCCB 极性和 AF 固件回读流程，并在本工程重新仿真及实现。该原图子工程未被修改，
其旧 bit/HWH 未被重命名或作为增强版发布。增强流水线仍为本工程单独构建的实现。
