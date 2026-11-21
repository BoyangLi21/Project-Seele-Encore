# R52 非地图作战交接

工作目录：`C:/Users/liboy/.codex/worktrees/r51-nonmap/eva`，从 R51 `6f2d35c` 继续。代理没有写施工世界 `WORLD_R52`。

## 现有生产事实

- 昼天使目标死亡后的尾段 bossbar：R51 的 `TvCampaignDirector.clearCombatBar` 已清空观众并隐藏；R52 前两使徒仍走同一实际目标生命周期。
- 屋岛盾第一炮半血、AT 零，第二炮瘫痪及遮挡身后：原生产规则保留。
- 暴走动力计数为零但仍 powered，普通伤害豁免；演出已进入持续接战时保留至少一 tick；吼叫在引入阶段一次。
- 取刀 26 tick、收刀 40 tick；发射第一帧原四处液压／喷气效果保留。
- 港口已有两原炮真实投射物、双炮窗口、颚部实际接触与原机回收链。R52 读取原港口 manifest 的两炮 UUID／位置，不补造舰船或旧坐标。

## 新生产逻辑

- `SurfaceAngelPlanR52`／`SurfaceAngelAssaultR52`：接受作战即生成远端同一真实使徒，按显式地表路线和原动作迎战；对原装甲井顶层使用实际足／鞭接触。城市未下降也可进入；前两使徒不钻地下。拉米尔继续原逐层完整性账本。
- `BattleNpcEquipmentR52`：常规 NPC 二号机调用原 `StaffOperationsR48.armedSortie` 剑井链。
- 屋岛普通开始默认初／零 NPC，显式玩家编成仍保留。`TvYashimaTransitR52` 只接受本场 bank2 出动凭证，调用原航空池按真实 receiver ID 交付。落点成功须有同原 EVA／pilot／owner／mission 的 `payloadTransferred` 记录及真实脚接触；本 generation 一次记录后，步行离开落点不再返送。
- 固定炮使用新唯一 controller `projectseele:yashima_cannon_r52`，承载原 `58eab304-0fb0-5f44-b500-4fed8824db08` 武器库存。原供架 `749cf141-0e2f-59ef-9e9b-d08346d5ea8d` 原子移交，立即同步空架显示，不能再次领出。同原物品及炮击计数归还。
- EVA 先到实际平台，指挥下令开原盖、真实升炮；驾驶初号机看向原炮实际三角面右键接入，随后完整趴姿与真实双手接触才能开火。Shift＋右键或 `/seele tv leave_cannon` 退出，恢复原徒手／趴姿过渡。NPC 同链。
- 枪体源网格、muzzle、bore、grips、渲染和原生 block shape／EVA 完整选源皮肤 paired BVH 用同一同步 frame。允许实际握持手／腕接触，保留头、胸、臂、腿、肩塔面。旧携炮 late rig 在 fixed actor 场景禁用，未带第二隐形手持炮。
- 瞄准先解析实际眼线目标点，再从固定 muzzle 瞄准该点，避免大炮与眼线平行错位。NPC 使用同原拉米尔核心中心。射程读 manifest，当前候选 2600。
- 拉米尔 `model_scale=4` 为 60m entity / 约 66m 八面体。远山客户端显示同真实 UUID 快照的同源低多边形世界模型，tracked 优先；真实 draw 后才 FRAME ACK；无第二伤害实体。必须随包包含 `RamielDistantProjectionR52Mixin` 及当前 mixins JSON。

## Root 需填写的安装契约

`tv_encounter_sites_r45.json` 的 `sites.ramiel`：

- `landings.0.point`／`landings.1.point` 是 **upright cargo bodyRoot**，分别 Root 已定的 `[-1226.5,175,-1488.5]`／`[-1331.5,175,-1412.5]`。
- `landings.0.receiver_id="yashima_delivery_unit0"`，`landings.1.receiver_id="yashima_delivery_unit1"`。
- `eva_access_routes.0`：从零号机 landing bodyRoot 连续步行至 `equipment_approach.0`；每段不超过 8m，竖差不超过 1.6m。
- `cover_after_supply_route`：从 `equipment_approach.0` 至 `shield_wait_port`；同连续性约束。`route_arrival_radius` 必须显式填写。
- `cover` 为真正挡炮位置；`hero` 不作为 fixed 操作位／落点的替代。

`yashima_cannon_station_r52.json`：用 `calibration_powered/STATION_CANDIDATE.json` 完整 draft。Root 补真实 `cannon_uuid`、`hatch_uuid`、迁后 `source_position`、`closed_position` 及 `eva_access_route`（初号机 landing bodyRoot → `prone_position`），再经实际安装／扫掠验证才设 `installed`／`geometry_validated`。

`source_mesh_sha256` 必须为原 payload `25bb4cb1da80ccd2fb2daaf972eb2179e800038c6dab83565971c3267b6d8fc3`。源完整 bounds、轴、muzzle 及 marker 表面均校验；无旧近城位置 fallback。

本候选 scale **8，64m**。Root 炮井 actor root `[-1242.5,174,-1400.5]` 与鞋锚 `[-1285.5,175,-1458.5]` 保持。`prone_position` 为独立 EVA entity root，不能与鞋锚或 landing 混用。实际完整包络见 `INSTALLATION_ENVELOPE.json`。

## 已取得的证据与边界

`.Codex/r52_operations/calibration_powered/` 有最终 frame／握点 JSON、完整原网格三视图、paired BVH 报告。64m 候选双手误差约 0.0000203m／0.0000081m；没有非握持枪体接触或不相连手臂自交。已按批准的全局 prone 腿修正重算，shin 最低约 0.030m，原鞋矩阵／最低锚保留。

一次有效原生姿势读取使用既有隔离 fixture，没有复制游戏／世界。普通完整电池，server／client powered 均稳定超过 20 tick，shutdown=false、stance=3，并在实际 `EvaPoseGraph.finish` 同帧取得最终骨架。旧动力耗尽取样保留为明确 rejected。

定向编译与 22 项 synthetic 参数拒绝检查是源码／契约证据，**不代表固定台升炮、绑定过渡、炮击、两机地下航空运输、2km 实际远景或完整战役已经原生通过**。这些须由 Root 在唯一最终安装场地上检验。新增 `EvaProneLegSupportR52` 与 `assets/projectseele/eva/prone_leg_support_hulls_r52.json` 必须一同打包。

跨文件窄改：Root／Owner 授权的 `EvaBodyPose` fixed late hook、`EvaUnit01Entity` fixed 输入／frame 字段、`NervArmamentStationEntity.refreshFiniteMissionStockR52`、`AutoSortieR32` 屋岛独立分支、`NervAirTransportRuntimeR52.requestReceiver` 精确 receiver ID 过滤，以及驾驶客户端独立 handler／packet action 27。其余 Owner／Air／动作源码保持各代理所有权。

## Root 审批后的真实炮架接入（2026-10-11）

`FixedCannonCradleR52` 使用原炮三角面 9023／986 的内部承托面，两处支撑接到实际 160 地坪。34 件机构包含双地脚、六级定长套筒、双横台、连接框、球铰和两节定长瞄准杆；原炮网格、64m 尺度、握点和已批准机体姿势均未改。升降量仅为同原炮 rootY 减 closedRootY，承托和瞄准杆端点仅由同一 AIM／原源面派生。杆件超出实际搭接范围即拒绝运动。

station manifest 必须新增 `cradle: {"floor_top":160,"closed_root_y":157.5,"raised_root_y":174}`，原样同步和保存为 `GunCradleR52`；客户端无需读世界文件。`source_position` 为实际迁后 `[-1305.5,114,-1373.5]`，`interaction_control` 为 Root 实按钮 `[-1302,175,-1374]`。按钮只下令升炮；驾驶员接炮后使用原正常开火输入。

renderer 采用既有真实机械材质／GPU 绘制路径；服务器使用同一个 `Piece` 的源 mesh／frame 和同 AIM 连续曲线证书，完整核对托架与机体（包含全部手／腕）及实际 SILO 源面。唯一跨 Owner 窄点为 `NervFlightProofR52.actualObstacleMeshes` 的固定炮 typed 分支，配合实体 `canBeCollidedWith`，使关门／机械原有检查看到原炮及炮架真实几何。

`.Codex/r52_operations/cradle_candidate/PRODUCTION_GEOMETRY_AUDIT.json` 为已编译生产几何读回：完整 16.5m 升程及升起状态，与全开原 SILO 和完整 19 部分同帧原皮肤均无交叉；三个轴各 ±2° 瞄准的真实搭接／门面扫掠通过。承托只允许原源承面接触，保留微小表面接触记录。此证据仍不是原生按钮／战役通过。最终图为 `CRADLE_PRODUCTION_SOURCE_REVIEW.png`，六文件冻结 receipt 为 `CRADLE_SOURCE_RECEIPT.json`。
