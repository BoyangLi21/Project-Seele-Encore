# R44 地表、建筑与生态记录

施工世界固定为 `SEELE_FIELD_R44_REVIEW`。本分支只读存档并产正逆计划；实际写入、Java 编译、启动与交付由 root 队列执行。这里没有新的用户认可记录。

## 有效配置根因

首次原生生态预演 `artifacts/rebuild_r44/native_authors/ecology/20260930_135415` 失败于 `NativeEcologyBiomesR44` 的真实 biome source 守卫。虽然源码和 `level.dat` 已配置 `regional_ecology`，启用的 `file/tv_world_preview` 数据包仍将同名 `data/projectseele/dimension/geofront.json` 定义为 fixed source。该定义优先于模组定义，启动/保存还把 `level.dat` 序列化回 fixed。这不是花草计数不足，不能构造一个假 source 绕过守卫。

root 随后只替换生效数据包内的 `generator.biome_source`，保留 `tv_preview=true`、`surface_datum=80`、噪声设置和其余维度字段，保存完整前后文件。相同冻结 class/resource epoch 的第二次原生预演 `20260930_135946` 已通过真实 source 守卫。`effective_dimension_audit.json` 列出源码、冻结原生资源和世界数据包三处定义与哈希；当前生效世界覆盖只有 `tv_world_preview`。原失败 marker 的时间早于成功运行，不是新失败。

以后安装器、世界合成和复验必须同时迁移/回读生效数据包的精确差量、`level.dat` 及有效 pack 顺序。只看源码、生成 JSON 或改 `level.dat` 不足以证明运行时采用了配置。新的默认模组定义不写本档种子；其气候噪声由世界 RandomState 初始化，植被 feature 使用实际 `world.getSeed()`。已测存档的配置保留真实世界种子，原生执行器强制核对 job seed。

## 已实施的源码

- 普通建筑模板修复了“后做楼面盖回前一楼梯头部净空”的顺序，采用已经验证的交替三列梯段与共同平台；多类街面有浅雨棚、连续基座和中文入口牌。R03 已退休的 `13-05/13-06` 东翼在新模板中保持退役。
- 升降塔使用完整楼面、连续楼梯、围护、双开人员门、接待、办公、储物、服务和少量住宿。全 93 塔而非 45 塔为分母；新模板与旧实例分别复验。
- `Tokyo3BuildingArchiveR44` 为每个世界/维度/塔保存独立货物和完整 state/NBT 写前日志，先保存逆向数据再移动，恢复时重写 BE 坐标并保留其余 NBT。不再每层压缩整座城市的快照。生成器运动接持久 voxel cursor、变更写量及时间预算；不可见且未改变的深度跳过。货物、测试快照及运行缓存共用持久 WorldUUID；旧 archive 必须完整备份后显式绑定迁移，不能静默认领其他世界日志。屋顶构件若投影触及固定穹顶角柱则明确 fail，不能在 negative mask 中吞掉。
- 玩家、EVA 和所有存活实体的占用检查使用实际 TV 高度并覆盖地下楼体。屋顶 cap 上两层列入货物；四个固定穹顶钢柱角点形成精确 negative mask。1488 格当前全部为预期铁块且无 BE，若模板状态变化则明确停止，不能算通过。高出两层的任意新增工程不从空气推断归属。
- 地表、地下的未来普通植被使用已注册的原生 placed features。废止 TV 的十四格网格树和 canonical 手工树调用，地形、湖岸及穹顶形状保持。地下使用已雕刻土层投影；地表/地下作者预留和虚轨 footprint 都保护整 feature，原有用户木、叶、其他植物及 BE 不被直接覆盖。普通叶片保留原生距离与凋落行为。

## 当前覆盖和可逆计划

193 栋普通建筑当前读到 948 对门，187 个已有门型入口和 6 个原清单定义的北侧开放团地落厅。193 个入口阈值均完成连续承重/净空的静态原生碰撞形状检查，未知形状为零。root 已施工街面 5753 records / 5751 实际变更格（另 2 项 NBT），187 个中文入口牌含完整 NBT。`city_buildings/native_entrances_r44.json.complete.json` 随后实际检查全部 193 对象、948 对门的 native use 和 756 门槛运动，并逐项恢复完整门状态/NBT。原生 server 通过尚不等同全建筑楼面、客户端或美术通过。

R43 剩余的两个“175 格孤立楼面”来自错误的设施包络。R03 收据已将两楼东墙完整收至 X152，旧 X153..157 已退休；现测 `13-05` 为 175 格墙外草地，`13-06` 为 100 草地与 75 旧外地铺。当前完整墙面和收据交叉验证后，`actual_authored_ownership.json` 保留旧地块信息并记实际包络。按实际包络重算两楼 13 层：连通 13，临空缺护/隔离岛/未知形状均为零，不需拆墙或填造假室内。

首次完整扫描为 101139 个区块记录，60261 FULL、40878 未完成，选择 37251 origin / 292 batches。后来原生生产案例和图审生成了新区块，当前扫描为 101488 记录、60467 FULL、41021 未完成。修正地下错误共用地表预留后，`layer_resolved_jobs` 选择 46207 origin（地表 24149、地下 22058），原 37251 全部仍在，新增 84 地表及 8872 地下。这些是待作者分母，不能计为已植被化。

`layer_resolved_single_jvm_v1/manifest.json` 冻结了 361 个 batch 的输入/来源 SHA；一次 `run_headless_r44.py ecology <manifest> --timeout 21600` 串行执行全部批次。每批最多 128 origin，实际最大 available chunk ID 为 376；每 feature pending 上限 65536 格，overlay＋pending 每批最多 1048576 格，单 feature detached scratch 最多 16 chunks，磁盘 ledger 缓存最多 96 节 / 393216 sparse cells，biome 每 shard 512 节。越界直接生成 failed，不记成保护回滚成功。每批清空 overlay、baseline、NBT、trial、origin 和 scratch，不保 forced tickets；原生短票正常过期，loaded chunk 和 sampled heap 仍由实际观测记录，不能从 cell 上限推算字节或承诺已卸载。

18:51:57 源新增逐 origin 的 runtime centre biome、实际注册 feature 顺序、实际 accepted mutations、耗时和 batch 堆/loaded chunk 采样。`audit_ecology_sequence_r44.py` 流式审查全部预期 origin 与 feature 分母、实际产出和保护回滚，导出逐 tile CSV；另用 `validate_ecology_manifest_r44.py` 校验共享 reader 的 exact state/full NBT/唯一 biome 节。来源 feature 数、作者完成、施工收据、增长/重登与图审分别记账。新观测 epoch 尚待 root 编译运行。

旧 TV 树模型共 4851 棵、4704 个连接组件。2697 组完整原模板通过全部树干、树冠、连接边界和 NBT 检查，可自然化 620101 叶格：整组从树干 BFS 计算原生支持距离，改非 persistent，保留完整树形和树干。1878 组触及城市/设施/虚轨预留，129 组原状态改变、未完整加载或边界不明，全部整组保留，逐对象坐标和原因在 `legacy_tree_components/audit.json`。这不是用新的手工网格树替代自然生成。

第一组原生样板包含地表/地下 meadow/woodland 四类共 18 origin、82 次 feature 调用：有效 placed 36，原生无产出 44，保护整 feature 回滚 2。真实正逆计划包含 4715 格、43 个完整 biome 节和 1553 个 quart；全部旧状态、完整 NBT、完整 biome NBT 回读零失败，逆向逐项一致。新植被在地表 2933 格、地下 1782 格，含草、长草、四类原生花、橡树与桦树。叶片全部非 persistent；39 格 distance=7 将按原生规则凋落。root 已施工原 18 origin 及另 28 halo 的 biome-only 迁移（后者原生 marker exported_cells=0，未重复种植物）。这只关闭样板跨界范围，不能计全域关闭。

真实未完成源案例包含 `(88,57..60)` 四个原 carvers chunk，经过生产生成器变为 FULL，完整结果在 `future_generation_cases.json.complete.json`。这捕获并修复了 WorldGenLevel 零参数 getHeight 被误作 heightmap overload 的 NPE；既有 FULL 的 overlay 预演曾未检出。root 已看开启光影的地上/地下 meadow/woodland 四图，指出样板外裸地及背景规则旧树仍存在；该评价没有被改写为全域视觉通过。

全量多批 native 作者新增 `NativeEcologyPlanLedgerR44`，前批植被状态在磁盘保存，缓存最多 96 节；后批读取计划中的实际状态，写触已有完整 feature 就整次回滚，所有 block 输出坐标互不重叠。biome 在磁盘按同一节的 64 holder quart 合并，保持唯一完整 before/after，原生 codec 重编码后按 512 节导出 shard。只允许最终 complete manifest 的 `merged_biome_plans` 施工，原始 batch biome 计划被 validator 拒绝。两个相邻 origin 分属两个 batch 的独立校准输入在 `ledger_calibration/two_adjacent_batches.json`；全量运行前必须以共享 query 管线和磁盘唯一性审查该输出。

root 已完成两个相邻 batch 的真实预演，最终 manifest 为 518 个互不重叠植物格、20 个唯一 biome 节。该证明属于跨批作者预演，未改存档，不能计作全域种植或生长完成。

布局整改与叶片凋落分开。root 先退休 9 个完整样板组件 / 2086 格，并实际原生 reseed 1126 格 / 25 biome 节。对旧预留的完整成员/NBT 和实际三维铁路关系再查，发现 1338 地下原树只是与地表城市同 XY、并未碰地下设施或 rail。`reservedBelow`、地下 feature、quart 与 selector 均已按 layer 修正。

`layer_resolved_retirement` 当前 exact 计划为 4029 个完整原网格组件 / 960889 格，root 已做完整前置、逆向与施工回读，收据为 `ecology/replay_full_grid_retirement_20260930/.../applied_20260930_190000_644168`。额外 3 个完整原树实际侵入原生 7×7 rail envelope，共 694 格，另由 `rail_grid_retirement_20260930` 的 19:01:40 收据退休。原 HOLD 目录仍保留 135 改动组和 540 地下预留组；其中独立轨道退役的 3 项须以其收据覆盖，不能重复计为仍保留或已 reseed。其他用户植被、状态/NBT 改动或真实设施预留均保整组件。以上布局退役不能与旧 620101 叶片自然化备选混用，也不能计为全量新生态已完成。

93 塔完整原生作者 `central_towers/author_20260930_1540/audit.json` 提供 306898 格正逆计划和全部三宽楼梯 cases，初始深度 312。`Tokyo3BuildingQualityR44` 的 13 个独立 job 负责每塔 9 格入口、真实 use 后恢复门状态、全幅楼面/连通/落厅临空边及每梯三列双向 MoverType.SELF 实测；货物按塔流式完整 NBT 保存，升降后逐格比较全体含空气与 roof+1/+2 的 prism；占用、部分层保存/重启、排队反转另出 marker。Native server use/physics 不等同客户端输入、画面或用户认可。

原生 rooms 首跑覆盖全 93 对象后失败，原始 failed 与 SHA 在 `landing_guard_repair` 冻结。713 个楼层的 centre seed 实际是源码声明的楼梯井侧栏；2181 个上行梯段全通过，下行却在横移终止后悬 0.4 格，检测增加 Vanilla travel 零输入沉稳，维持原 .32 落点容差。4920 个临空 flags 中 2181 是已声明的真实下降轴；剩余 2739 是各层入梯对端深井 lip 和最高层 unused bay 的真实缺护。模板和实例同步补 16941 格承重、横护及 unused bay 楼面，root 已施工。

第二原生 `rooms_underground_landing_v2.json.complete.json` 已回读：93 对象、837 入口格、186 门真实 use、820 全楼层、198770 可行走格全连通，未知障碍/临空缺护均零；2181 三宽梯段双向全成功。塔 0 下楼从 -35.72 经四次真实 Vanilla travel 沉到 -36、onGround=true，原容差未放宽。现为 13 个 job，额外单列地上/地下 roof 占用；capture 不再隐式补杆，固定中心负 mask 单独校验，29 个非 core 塔中心计完整 cargo；层内新增占用保留日志 cursor 暂停，方向反转仍等当前层安全完成。全 cargo movement/restart/客户端与图审还未计通过。

原 capture 曾对地下初始副本缺失的屋顶杆执行 `putIfAbsent`，这会在观测时创造新货物。现已取消。285 个实际杆位在该反例冻结时全部 AIR、NBT 为零，源码首错与旧编译 epoch 哈希保存在 `central_towers/implicit_roof_creation_counterexample.json`；当时尚未启动 tower movement，不能编造一条原生运行失败。屋顶装备若需要恢复，必须另产完整模板迁移和精确逆向，再做 cargo capture。新的捕获只保存当前完整实际状态。

root 随后完成全 93 cargo capture / 1994771 prism 格 / 1471 BE，WorldUUID 为 `4dee5b9d-ef54-4d89-9b16-f2556ca54867`；地下室内占用和 roof 占用分别 93 对象实际通过。首次 `restore_surface` age41 却误以 depth312==target312 作为恢复终点，age42 比对 tower0 地下 cargo 零差异，随后生产街面恢复回调真正请求 312→0，age43 的 settled 守卫正确报错。原 input/failed/log、全部 93 NBT cargo、UUID/controller 共 100 文件已冻结于 `restore_surface_first_failure`。

19:02:53 新 fixture 等待明确请求的 endpoint0/312，游标及 queued target 全清后才全 cargo verify；已有同向请求按原 journal 继续，不 reset。反转必须实际观察原活动层完成且消费 queued target，正常 312→311→312 或 0→1→0不再误判为未越层；重启 checkpoint 持久保存原方向与原子边界证据。独立 13 输入在 `native_quality/attempt_movement_goal_v2`，反转对由已恢复的 surface0 发 descent，再排队 ascent；原 93 snapshot 路径复用但不允许隐式覆盖。负 mask 在 fixture 内新增实际铁块/no-BE 校验。新源码仍需 root 编译和实际新 attempt，旧失败没有抹除，也未计全 cargo movement/restart 通过。

道路输入为 R20 主道路 714027 列及 R20 最终扩张道路 68892 列（与 R02 扩张 height2/mask 相同），并集 782581。当前 BEFORE 全宽扫描用实际原生碰撞形状检查脚面、玩家净空、554776 车行列的 6 格净空、承重与四向岸边、八邻坡度及虚轨 7×7 footprint。原始结果不覆盖，SHA 已冻结。对象清单把全部异常组成 737 个组件；机场/站房迁移和未知用途显式保留为待审，不以屏蔽图层算通过。

机场联络路第一处完整修复在 `surface_network/bay_airport_crossing`：819 列同一既定 Y81 断面、3246 exact 变更格，严格旧状态/NBT preflight 零失败，HOLD/static collision failure 都为零。R22 在 `build_transit_civil_r22.py` 中只用主路 mask 避让桥柱，遗漏扩张道路，于是将 `(219,94,997)` 完整支柱放入街面；当前计划将其改为 Z980/1004 两侧 portal、连续 headstock，退役 R02 旧路桥隆起组件、填实路基并以 1:2 草坡接自然地形。铁路 curve/ID 不变，静态虚轨下净空 10、头梁下 8；全 13 列双向原生 cases 与实际画面仍待施工后验证。

root 已施湾岸机场断面，按其 `road_contract_delta.json` 重新测全 782581 列，之前 21 个虚轨冲突归零、承重待审从 1562 降到 1454，原 BEFORE 和 737 对象目录未覆盖。旧 datum 与站房用途迁移、实际楼面仍分别列账，不能把候选机场的新 73 标高当旧 81 道路缺口重填。

第二完整道路组件为 `hakone_valley_bridge`，保持箱根机场联络路 X-2238..-2226、Z-299..-216 共 1092 列原 Y81 标高。四根原柱当前都有实际土层承重，源判断只看中心高差，漏掉 -254/-253 两格路边 16 米落差。554 格候选补连续纵/横联系和栏杆的完整承重 coping，原谷地不被填平，路面及当前虚轨身份保持。整个 frame 连至原基础、全宽 6 米净空、虚轨冲突和 state/NBT 前置均零失败；施工后的原生物理与图审仍待 root。

补查明确作者后来新增的 R07 港口路、R10 拦截大道及 R07 UN 主路，38502 positive pavement 列与旧集合合并为 820895 列。完整当前读取得到 587690 车行列、840 玩家净空异常、9651 车行净空异常、1846 datum、1454 承重待审、944 grade jump、3485 路岸边，虚轨冲突和未知形状均零；全部异常组成 799 对象，不算通过。新 `audit_regional_roads_r44.py` 输出每列实际脚面/原 datum/玩家与6m净空/承重岸边/虚轨 flags 的紧凑 NPZ；`audit_road_connectivity_r44.py` 对整个路权与真实几何候选分别连通，不从旧 782581 二维 mask 宣称整个城市无路，也不以一条中心路径或连通量替代全宽车行、桥基础、坡岸与站入口复验。

首个样板的两个保护回滚完整树候选未施工，其冻结 epoch 只记录计数、没有拒绝坐标，因此没有为这两次 feature 补造成功证明。后续两批共享 ledger 校准已经记录拒绝坐标/原状态，新的源保留同样诊断。物种密度、逐 tile 分母在 `calibration_inspection.json` 与 CSV。施工后仍需实际画面、施骨粉/叶片行为、重登和性能检查，样板认可后再推广。

## 参考与原创边界

root 随后以新 probe lifecycle epoch 完成真实 `attempt_probe_lifecycle_v3/restore_surface.json.complete.json`：全部 93 cargo 与原 capture 严格一致，depth/target0、所有 cursor 及 fault 清空，正常保存退出。此次完整恢复约 17.5 分钟 / 15,385 tick，并出现 10–14 秒级 Can'tKeepUp；货物功能通过不等于升降可玩速度或性能通过，须以真实 archive、光照、region IO 采样查热点，不能仅提高写入预算。旧 probe 假阳性记录仍不重新算通过；surface、下沉、完整 cold/reversal 与客户端仍独立待验。

路桥 v11 已由 root 以完整 state/NBT preflight、inverse 及实际回读施工 37,162 格，收据 `ecology/replay_hakone_tokyo_link_v11/hakone_tokyo_link_v11/applied_20260930_201407_793140`。随后扩大到原东京纵向交通检查，检出沿新链接的护栏/边梁误跨旧有效公共横路。这个是新链接自通检查的真实遗漏，初始路口不能计通过。`surface_network/hakone_tokyo_original_junctions_v1` 准备 104 格 exact 恢复，依据旧 native effective flags 7/31、原 floorY、完整 v11 写前 state/NBT 与真实当前状态，不以黑色方块判断道路身份；原九列南北双向 18 个 native cases 独立待验。

新的 `audit_existing_road_interfaces_r44.py` 通用后置规则按每个旧有效 public column 的真 3D floor/1.8m 步行或6m工程车辆包络、既有相邻双向连接与显式 floor successor 检查新增件。冻结 v11 候选能检出 51 个旧路阻挡/原 floor 变化反例；104 恢复计划结合明确 v11 floor successor 后，221 旧列/824 双向邻接静态无失败。没有替代权属的旧路退役不能靠改名字、换材质或二维 mask 消失。静态后置 gate 仍不代替真实车辆、原方向完整有效宽度和转向扫掠。

东京—港区第二完整接口在 `surface_network/tokyo_harbour_link_ready_v2`，384 格 / 559 全幅列，连接实际 `(250,81,520)` 和 `(280,81,520)`。包含实测浅路基和草岸坡，旧阻路灯 273/78..83/522 的全部六成员逐格对应 R19 `fixture_supports/grounded_lights_and_baffles/ops.json.gz` 原 owner/state，完整搬到 273/81..86/529 的当前承重土层，头方向保留、NBT 不改。旧 425 公共列及 1,582 双向邻接、新 13 米道路全幅六米工程净空静态无失败或未知；44 条新东西和旧南北全宽 native cases 仍未跑，不计图审通过。

799 道路对象中的三大箱根 VEHICLE_CLEARANCE 组当前重读为 4,770 / 918 / 981 列，全部是 R02 实际 light_gray_concrete/sea_lantern 隧道冠层，真实 underside 在 feet+5 或+5.5，并非退役树后留下的植物。这里“6米不足”是工程筛查阈值，不是已证明现行许可车型发生碰撞。已读 pinned SBW 配置中 truck/FH77BW 等 Collision 本体尺寸，但全部旋转/Transform、附属体、乘员、模型和路面姿态还未实测；原道路的车型许可与完整包络、安全余量未确认前，不升顶、不把设计升级误写为碰撞修复，也不把该阈值筛查直接当坏图结论。

完整箱根—东京道路候选冻结在 `surface_network/hakone_tokyo_link_ready_v11/ready_collection.json`，该目录是唯一选择的 ready 集合，各正逆、形状、端口和设备文件都有 SHA；此前 v1..v10 保留为设计与反例，不作为本轮施工选择。候选从实际箱根 `(-1120,105,300)` 到东京西侧在用纵路 `(-760,97,308)`，提前完成缓弯后隧道保持直线。37,162 格正逆逐格匹配，391 个断面；谷桥采用 22 个 3×3 实测岩土基础桥墩、双柱横梁及完整箱梁，不把低至 Y54 的谷地填成大坝。两端浅岸坡与实际道路相接，既有木与叶零改动。完整 native shape 审查、弯处 1,768 个玩家足迹扫掠采样、全构架通当前地层、3D rail envelope 均没有失败或未知；这些仍是候选静态证据，不是原生走车或美术认可。

87 米山体隧道扩大为 19 米内部侧湾：9 米车行，两侧各一米实体分隔、两格原生 MTR 水平带及两格固定旁通。348 个 flat step 保持恒 `blockY=98`、东西向 straight 与成对 left/right，真实脚面 `98.9375`；两侧使用相反 direction，没有水平 handrail。固定通路为 Y99，端部平整平台、转向区和短半格阶梯接回原车道缓坡。确切 MTR state/collision 继承已实测 low_plant 模块；实际流向、上带/乘送/走出、固定旁通与两个城镇交叉口还须由 root 用原生实体和客户端实测。候选动带与车道间的分隔、洞门、整幅顶板和照明属于同一完整正逆组件，不能只施路面。

新增道路后生态作者采用 `ecology/layer_resolved_infrastructure_single_jvm_v2/manifest.json`，361 批、46,207 origin 的原分母保持；旧 v1 输入不修改。`RegionalEcologyRetrofitR44` 新增显式六坐标 `protected_volumes`，391 个真实道路/设备净空体阻止整次 feature 侵入，同时保留高架桥下的自然谷地种植资格；没有用 XY biome 预留把桥下整片地层抹为无生态。新源待 root 冻结编译；15 个地下校准、全批作者、唯一 merged biome shards 的前置/施工、生长与重登、性能及原生实际画面仍分别计账。道路候选的未来新世界模板应用与全部 799 道路对象整改尚未关闭。

19:35 的真实 server-thread 只读诊断确认 restore 的 386 个 travel chunk 全为 FULL，`districtLoaded=true`、`travelOccupied=true`。唯一阻挡是 tower3 地下包络 `[-139,-56,171]..[-120,24,190]` 内两只此前测试盔甲架，UUID `b56ee386-294f-422b-aa50-9effe506e7ca` 与 `e2a0fb83-51a0-44c8-998b-0b3f19df98dc`，都带本世界 `r44_city_quality/` 标签，位置分别 `(-129.5,23,180.5)` 和 `(-129.5,-54,180.5)`。没有原项目角色参与阻挡。诊断在正常 `halt(false)` 保存前落盘 `central_towers/live_probe/hold_20260930_1935.json`。两组旧 93 占用结果缺无 probe 阴性对照，当前明确撤销其因果通过资格，仍保留原文件。

原 fixture 探针使用可保存的原生 ArmorStand，清理只丢弃保存于静态字段的对象引用，没有独立 chunk 生命周期票、实际 UUID 回取与不保存约束。实际存档实体 chunk `(-9,11)` 留有上述完整两只探针；尚无逐次卸载追踪，不能断言具体在哪一个 tick 换了实体实例。源码改为 `shouldBeSaved=false`、独立生命周期票、结束/异常/ServerStopping 按本次 active UUID 回取清理并确认已移除；计时前要求整城 FULL。每塔新增放探针前阴性、加入后阳性、移除后阴性 production guard 检查，任何既有角色阻挡直接失败，保留身份。真实无 probe cargo travel 仍另行实测；这些源码尚待 root 编译执行。另修原 held request 取消到当前深度后因 settled tick 跳过而未释放零 TTL travel 票的问题。

`central_towers/exact_probe_cleanup_v1/plan.json` 保存两 UUID 的完整 NBT 与 entity chunk 全量 before/after；after 只移除这两个实测测试对象，其他实体及其他 region records 保留。这是只读计划，由 root 在停止世界、完整旧 NBT 前置、region 备份与精确逆向后执行，并再次回读 probe 不在及其他实体不变。没有按 tag 批量删除、移动角色或放宽占用守卫。

[官方 EVA 箱根路线资料](https://www.eva-info.jp/1051) 只支持第三新东京与箱根的关联，不据此声称逐帧复刻 TV 建筑。本轮没有新观看完整 TV 集数的证据；既有 TV 防御城/穹顶约束来自工程已有研究，精确场景和街景仍需独立画面复核。

[箱根地质公园](https://www.hakone-geopark.jp/hakonegeopark/) 的外轮山、中央火口丘和坡岸，[箱根町森林公园](https://www.hakone.or.jp/morifure/hakoneyasuraginomori.html) 的湖岸森林/公共步行空间用于生态和边界关系。[国土交通省七日町记录](https://www.mlit.go.jp/kankocho/shisaku/kankochi/pdf/ikiiki2009_08.pdf) 记载了 1993 年既有建筑调查、1995–1996 年分段街景协定及 1996 年街道整备，用于“小店与住宅混用、保留成熟街面”的设计依据；[小田原历史照片馆](https://www.city.odawara.kanagawa.jp/darc/item/333/) 是 1968 年资料，不能冒称九十年代照片。

雨棚、配色、店名、房间用途和缩尺均为原创工程推演。原生 oak/birch/spruce 是 Minecraft 物种近似，不是对箱根山毛榉、杉或季节植被的准确复原。没有把官方图片、录像或这些资料的图形导入游戏素材。
