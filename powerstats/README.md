# astonc PowerStats：燃料计放电能量通道

## 当前实现（待整机验收）

`battery/main.cpp` 提供一个 AIDL PowerStats EnergyMeter Channel，名称明确标为
“Battery discharge (fuel gauge derived)”。内核现有 Oplus 燃料计更新回调累积
`battery_rm` 下降量与电压均值的乘积，通过只读
`/sys/kernel/oplus_battery_energy/battery_discharge_energy_uws` 输出 64 位 µWs。
充电、无线供电、读数无效和不合理的大幅回跳都不累计；切换回断充时重建基线。
此值是电池侧放电估算，不能用作 CPU/GPU 等 rail 的能耗或外部功率计校准值。

原厂二进制同时提供独立的 `IHandleFactory/default`。为了保留它，原始 OTA
blob 保持不变，`tools/patch_handlefactory_startup.py` 仅将该二进制在
`IPowerStats/default` 重复注册失败分支的一条 AArch64 日志指令从 FATAL
改成 ERROR；构建安装带 `.handlefactory` 后缀的可复现副本。新服务先注册
PowerStats，再触发原厂进程注册 HandleFactory。脚本校验原 blob 的 SHA-256
和补丁处机器码，拒绝对其他版本盲目应用。原厂进程是否确实继续启动、
HandleFactory 是否可用，仍须在整机上验证。

本目录下方的原厂移植记录和 2026-09-24 设备实测描述的是**此前未添加
燃料计通道的版本**；新实现的通过条件见
`/data/crdroid/POWERSTATS-astonc-implementation-acceptance-20260924.zh-CN.md`。

本目录中的二进制、init、VINTF 和 XML 来自用户提供的
`/root/powerstats-astonc-static-evidence-2026-09-24.zip`，其来源标注为
PJE110YS_16.0.5.1002(CN01M001) 原厂 OTA。压缩包 `SHA256SUMS.txt` 的
全部项目已校验通过；ZIP SHA-256 为
`c2fd9389a739c6fe87fb1d782958d9d6bf2b3b22d46e28cdd45e167b16546243`。
该 OTA 与故障报告同为 PJE110 / OP5CF9L1，构建指纹不同。

原厂服务声明 `android.hardware.power.stats.IPowerStats/default`，并在同一
进程中注册 `vendor.oplus.hardware.handlefactory.IHandleFactory/default`。
`Android.bp` 将服务、其直接依赖、init、VINTF 和配置放入 ODM；本机用
现有 AIDL V1 接口库构建。内核中已有 `soc_sleep_stats.ko`、
`subsystem_sleep_stats.ko`，不复制原厂内核模块或预编译 SELinux 策略。
当前构建的 `soc_sleep_stats.ko` 与原厂同名模块并不等价：原厂模块的
字符串含 `oplus_rpmh_stats` / `oplus_rpmh_master_stats`，当前模块没有。
原厂 XML 中相应节点能否读取，必须在目标设备上验证。

静态包只支持原厂存在 PowerStats 实现、sleep/RPMh/DDR 状态驻留数据源
候选的结论。它没有设备运行时计数器样本，不能证明 energy consumers、
energy meter 或 rail 累计能量可用。状态驻留时间也不是能耗读数。

## 设备验收

安装包含本移植的完整构建后，在设备侧保存以下结果，至少间隔 60 秒
重复第 2、3 项，并保留命令错误与 UTC 时间：

1. `adb shell getprop ro.build.fingerprint`、
   `adb shell getprop ro.vendor.build.fingerprint`、
   `adb shell getprop ro.odm.build.fingerprint`；确认 ODM 与 ROM 来源。
2. `adb shell service list | grep -E 'power.stats|handlefactory'`、
   `adb shell dumpsys powerstats`；确认服务注册和 entities、channels、
   consumers 的清单。即时能量数值须直接调用 AIDL 的
   `readEnergyMeter()` 或 `getEnergyConsumed()`，本目录 `probe/` 有只读工具。
3. 只读采集 `/sys/module/soc_sleep_stats/`、`/sys/power/rpmh_stats/`、
   `/sys/power/ddr/residency` 和 HAL 实际引用节点中存在的项目。记录
   `ls -lZ`、原文、单位以及两次采样的 UTC 时间。
4. 保存 `adb shell logcat -d -b all` 中该服务的链接器、init、VINTF、
   AVC 和 PowerStats 错误行；不要为通过测试切换 permissive。

通过标准：服务启动，直接读取 AIDL 得到可追溯且递增的真实硬件
**能量**计数（明确单位），并核对对应原始节点。若只得到状态驻留数据，
只能算 PowerStats 状态驻留接入，不能宣称“真实硬件能耗读数”已完成。

## 2026-09-24 设备实测

设备侧取证包为 `/root/powerstats-astonc-evidence.zip`，SHA-256
`b4f2b156b4e0d527d9c369c5d0a51a9b935e8582144ba8c6d07b7b17fcd0d753`。
本目录中的 HAL、HandleFactory 库和配置 XML 与设备运行文件的 SHA-256
逐项相同。服务已注册并运行，但 `dumpsys powerstats` 的 PowerEntities、
Channels、EnergyConsumers 仍全部为空。

配置里的四个 QCOM RPMh 节点，以及 HAL 二进制引用的三个 `/sys/power`
驻留节点，实机都不存在。`/sys/class/powercap` 为空；没有找到
`energy_uj`。CPU idle 计数递增，但不是能量计数。电池
`charge_counter`、`current_now`、`voltage_now` 在约 62 秒的两次采样中
分别保持 4,990,000、0、4,439,000；`energy_now` 不存在。

这套候选 HAL 当前**未通过真实硬件能耗验收**。不应把服务注册、CPU/RPMh
驻留时间或电池 `energy_full` 静态容量值标为能耗接入完成。移植 Oplus
RPMh 可能补充状态驻留数据，但无法单独满足真实能量目标。后续需要找到
设备实际存在且单位、累积语义可验证的硬件能量接口，再决定是否扩展或
更换 HAL。完整判定见
`/data/crdroid/ACCEPTANCE-astonc-20260924-result.zh-CN.md`。后续收到
PJE110YS_16.0.5.1002 原厂 vendor/odm 镜像；其中 PowerStats HAL、配置
与设备实测文件逐字节相同。另有 Oplus RPMh 和 PowerMonitor 服务，但
它们分别提供睡眠状态和任务诊断接口，没有找到独立的累计能量来源。
静态镜像审核见
`/data/crdroid/POWERSTATS-astonc-stock-image-review.zh-CN.md`。
