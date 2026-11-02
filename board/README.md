# 上板交付

`runtime_bundle.zip` 解压得到 `fpga_vision_runtime`，包含当前已验收 PS 程序、bit/HWH、资源与 manifest。与 `src/ps/runtime` 的文件逐字节一致。

先运行 `python3 preflight.py`，再按 `../report/reproduction.md` 启动服务或限定时长验证。不得混用历史 bit/HWH。`results/` 是已有 2026-10-30 实板证据，新运行产生的记录另存。

`rebuilt_runtime.zip` 是本次从零构建生成的可部署副本，配对 manifest 已重新计算。配置数据与原实测 bit 相同，PYNQ 解析的硬件字典相同；本轮未重新上板。已有验收数据仍属于 `runtime_bundle.zip`，不可将其标为新运行记录。
