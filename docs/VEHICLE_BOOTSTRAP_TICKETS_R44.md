# 远处车辆启动区块的生命周期

实际服务器测量：`artifacts/rebuild_r44/native_authors/ecology/20261001_020557/chunk_tickets.json`。生态作者开始前已有60张 `start/level=30`，到第300tick仍全部存在；`post_teleport/level=30`同期由61降至24。这不是只看存档列表得出的推测。

对实际安装的 SBW `0.8.9.1-hotfix-mc1.20.1-993063bed` 字节码核对，`ChunkPosSavedData$Companion.posSavedDataOnServerStarted` 在读取每个保存的车辆区块时调用 `addRegionTicket(START, position, 3, Unit.INSTANCE)`，然后清空这份启动列表。START没有到期时间。每辆车平时刷新的是另一种短期票，所以只停止停放车辆的短期刷新不能释放这些启动票。原始字节码在 `ecology/sbw_start_tickets_bytecode.txt`。

候选只针对本项目维度的这一个已确认调用，把启动恢复票换为同等级、同半径的600tick临时票，保留完整初始加载。行驶、被驾驶、交战、非本项目车辆等仍由原 SBW 实时刷新；原有停放资格判断不变。它不删除实体、NBT、玩家、其他票或其他维度的数据。默认关闭，须显式 `projectseele.r44ExpiringVehicleBootstrap=true` 才生效。

实际原行为与候选均完成一次无人在线的冷启动，运行到1100tick：`native_authors/ecology/20261001_032843` 和 `20261001_033333`。原行为在700～1100tick保持60张START票、9472个加载区块；候选的60张同半径启动票在600tick后正常到期，同一时间段加载区块为5196，约少45%。两次均没有生态来源点、没有方块／生物群系补丁；6张实时POST票与51张Forge票继续存在。完整实时记录在 `runtime_profile/vehicle_bootstrap_v1/live_comparison.json`。

这证明了启动票据的生命周期修正，不证明玩家在线时的全部性能或玩法。堆使用值受GC时点影响，不能拿这两次即时堆值宣称节省了多少内存。远近来回登乘、活动车辆持续运行、重启后全部原身份和最终副本仍待验证；候选仍默认关闭。东京楼宇运输票在初始化结束后也正常释放，不能把那部分归因于SBW。全部驻留区块与票源区块也不能等同。
