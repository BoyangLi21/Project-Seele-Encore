# R45 小梯真实损坏与世界政策主线程热点

本子代理未启动Java/Gradle/Minecraft，未写世界或模型。原生运行、编译、性能与完整90趟由root执行；以下为实际既有日志、冷sourcecandidate回读和源码修复。

City v6 `qa_checkpoint_revision_v1/native_city_checkpoint_run_v6/native.log` 第684行，12:17:14实际报 `s20-compact-cage-x93-z204-v4` ambiguous/unsafe damaged cabin并拒绝清井、填地或重建。进程正常exit0，430.10秒超时后正常退出；没有完整96通过，也没有小梯90趟通过。

`small_lift_complete_v3`对完整1736文件前后inventory/SHA一致；7组/24停层的完整楼面、顶板、控制器、全部实际input/display NBT、全层门孔、完整外呼路径及承重handoff已回读。大型gateway使用原固定native controller菜单(showButtons=1)，没有虚构轿内selector；其余6组用原linked selector与完整顶板独立识别，7组各有唯一原轿厢。

唯一真实错误是compact当前−394层东北角 `(95,-395,-54)`：24格polished_deepslate地板＋1格nerv_machine_panel，25格smooth_quartz顶板、原选择器/完整NBT与门喉完整。原已applied的 `tv_hangar_envelope_v3/whole_three_line_tv_skin` 精确ops及 `applied_20260930_175054_732221/receipt.json` 证明它由 `r44/tv_hangar/shared_transfer_green_fabricated_pressure_skin` 从polished_deepslate涂成machine_panel；R45 TVshell forward没有这格。当前skin生成器whole_native_lift保护域会排除此格，旧实际施工差量却不满足现guard，不能把后补guard当成已恢复。

这是1格外围角的已知错误饰面，不是运行时允许自动修的“1格内部空气孔”。`isCabinFloor`拒绝它、`repairIdentifiedCabinFloor` HOLD均正确；没有扩大材料白名单。正逆1格候选只还原收据记载的原地板，全部井、轿厢、原硬件/身份/进度保留，尚未安装。root应在明确目标停服后重新核旧完整state/NBT，合入1格后建新checkpoint/lease，再实际原菜单、层门、到层退出、90组合和重载。

独立主线程证据为 `qa_inflight_ready_revision_v1/native_ready_diagnostic_run_v1/threads_live_1.txt` 第839..877行：Server thread CPU108687.50ms/elapsed167.39s，栈为NoSuchFileException/Throwable.fillInStackTrace→Files.isRegularFile→FacilityWorldPolicy.isS22Coastal→s20Lifts→setLandingDoor→synchronizeMovingElevatorDoors→adapter reconcile→server tick。

性能源码只改FacilityWorldPolicy、S20PhysicalElevatorDirector的设施清单获取、FacilityLiftsR25。marker正/负stat按实际server对象、绝对world root、level name和当前tick复用；下一tick或root/name变化重新读取，明确 `invalidate(server)` 可同tick清理marker及设施清单，ServerStopped事件清理。不同ServerLevel/world/tick的完整immutable lift list分别缓存；R25/26marker也使用同cache，不再保留旧forever ACTIVE。当前方案没有长期隐藏外部marker更新，也没有删除任何门同步。

源码before/current静态比较证明原完整lift spec builder与setLandingDoor/synchronizeMovingElevatorDoors函数体相等；真实磁盘stat调用点由多处收敛到唯一cache loader。证据为 `performance_policy_v1/source_fix_receipt.json`。本代理未编译，root须附新source/class/actual-loaded epoch，分别验证多存档、marker刷新、退出再进、实时门同步及JFR。Create工作线程shape union/City I/O由City独立负责，当前不宣称整体性能或任何设备生命周期已通过。
