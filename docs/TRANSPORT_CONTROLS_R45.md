# R45 非模型交通与控制交接

本子任务不启动Minecraft/build、不写任何世界；Root为唯一施工与运行者。模型、网格、骨架、声音、Create城市、Terrain和通用世界写器均未改。本批没有新的原生功能、美术或发布通过结论。

入口：`artifacts/rebuild_r45/transport_controls_agent/handoff.json`。源码控制修复、完整NBT/派生候选和当前原生任务顺序分别冻结；不能从只读MTR副本复制运行进度回世界。

## 当前真实数据与全部对象

从R45实际世界的251个MTR文件作独立只读副本，使用安装版4.0.5引擎自己的 `TransitSnapshotR20` 读取拓扑，得到171 rails、20 stations、38 platforms、6 routes。原世界251文件前后SHA均不变；没有启动Minecraft。34个铁路、4个航空接口与旧38个原生接口ID集合逐项相等，当前38个站外staging均有已知原生承重与净空。

`prepared_v1` 保存全部38接口/来源与到达端口、80真实MTR公共票闸、7个MovingElevators组/24个实际停层及原完整控制器/遥控器NBT，并提供90个有向from/to原生菜单选择组合。现有24源/25趟检查并不等于90对、冷启动、占用、保存中断和双客户端均已完成。

NPC实际登记库是222个UUID，岗位源列236个；差14个均为UN `un_crew`。这里只记录差异，不生成替身、迁移岗位或清除身份。是否是旧未加载/未生成岗位或其他上下文仍需Root现场核对。NERV指挥/技术岗位与原UUID保留。

## 已实际修改的首因与源码

| 首因 | 修复 | 仍需Root证明 |
|---|---|---|
| `StaffPilotOrdersR25.request` 在队列/其他下令者拒绝检查之前已经 `assignCommander` | 移除提前改归属，只有真实 `TrainingPilotDirector.start` 接受以后改指挥归属 | 两个真实客户端：他人任务/重复/权限不足/设施不就绪的拒绝均不改变指挥归属 |
| 驾驶员pending队列独立于既有 `StaffCommandBookR24.cancel` | 加带caller UUID、officer UUID、unit、岗位/权限检查的pending取消，并接入既有cancel入口 | 远端机库未加载时取消，之后加载也不再登机；他人取消拒绝；已启动机械流程保持安全运行 |
| `NervLiftPassengerSync` 在controller/group/cage缺失时只是continue，保留旧bounds/乘员/移动状态 | 失效/卸载清除补充约束；只使用最近有效server tick；停server清理。原插件carry/真实cage保持 | 失效控制器、分区卸载/返回、维度切换、退出重登、完整到层离开；正常原生乘梯无回退 |
| server teleport/client packet诊断仅在mode包含riding时启用，全38用r44-transit-all | 两专用诊断mixin纳入该模式及显式r45TransportTrace，只观测不改包处理 | 与实际同jar/source epoch的F2最后64帧，区分server延迟与client相对坐标/校正 |
| 四条旧map_approach首点处于关闭票闸自身 | 当前真实承重/形状下恢复闸外公共首点，完整保留旧reader与后续路径 | 实际卡片/免费既有服务，闸内外、阅读侧和关闭/开门完整行为 |
| NERV旧(-398,82,698)已为空气 | 指向当前(-396,82,698) S1实际地图，并连续延长原公共读板路径 | 新点视线/中文站序/实际平台绑定与当前画面 |
| 机库两高MTR图板的upper仍存projectseele BE/MapRows，lower为正确mtr BE/platform_id | 两upper完整NBT改为安装版原生MTR注册schema，两个完整旧SNBT保留inverse。块种、两半、位置和真实platform ID保留 | 实际冷加载、两个正面动态图板字形/原生绑定、另一客户端 |

源码增加 `StaffOperationsTraceR45`、`TransportLifecycleTraceR45`、`TransportClientTraceR45`、`ElevatorInterfaceTraceR45` 的opt-in观测。未更改台词或动作；日志包含实际UUID、队列接受/取消/物理按键、native组/菜单/cage、server原生rider相对坐标、client raw/presented progress、校正余量、原生door值与最后64条。buffer只为证据，超过15米仅触发dump，不把合法快进自动定为失败。

## 数据/派生候选施装

`current_audit_v1/native_sign_BE_integrity/{forward,inverse}.jsonl.gz` 是2格state不变的完整BE修复。Root须走 `Painter.update_block_entity` 或已支持NBT-only的精确施工器；普通只改state的无BE分支会漏改。所有旧/新完整SNBT与正逆一一对应，不能用平台/运行数据库整包替代。

`current_audit_v1/exact_derived_plan.json` 保留当前路线记录顺序/无关字段，精确修改8条：四个闸外起点、NERVreader/连续approach、两个MTR reader合同。安装前重查当前文件SHA；若Root同时新增了别的路线，只按每条完整before匹配合入，不覆盖新进度或其他路线。

`StationDiagramContractR45`核对完整两半、原生注册BE schema、同真实platform_id、实际MTR平台和运营路由、中文站序及实际模型正面。它不把动态图板内容当已显示，真实client glyph、光影可读性与源数据/纹理缓存仍需证明。

Root已占用的 `RegionalSpatialAuditDriver.java` 本子任务未改。请应用 `station_reader_dispatch.patch`；已 `git apply --check` 通过。只对新明确合同走完整检查，原有OUTLINE视线继续运行，没有关闭碰撞/取消票闸或只放宽类型判PASS。

## 原生顺序与证据边界

1. Root编译当前控制源，固定实际jar/资源SHA/协议与正确R45世界身份。子任务只做过源diff/语法准备与安装版JAR API核对，没有声称Java编译通过。
2. 安装2个完整BE修复、8条精确路线合同并合入专用reader dispatch。
3. 检查全部80票闸真实卡片/免费服务边界、占用保持、关闭恢复、双向、重登/双客户端；检查50实时牌真正源钟/预测和全部已知地图决策口。
4. 七组/每个24楼层门厅，真实来车→开门→进入→原生完整菜单→运行→到层→离开→回程；再做90可选from/to组合、占用、中断、保存/冷启动与两客户端。观测器读真正native floor menu，不以照片/旧组名推断高度。
5. 先F2两个方向，开启 `projectseele.r45TransportTrace=true`。server/player/raw vehicle/rider offset、client/raw/presented/correction、position packet必须同epoch；再按 `all38_cases.json` 覆盖全部铁路/飞机真实车门、站台门、登机梯、负载同步、supported arrival/exit和返程。不得补猜测地面来掩盖失败。
6. 对全部已登记岗位按权限和owner验证，尤其取消pending登机、拒绝不改指挥归属、实际控制台按键/故障/中断/返回岗位。`projectseele.r45StaffControlTrace=true`；`projectseele.r45DeviceControlTrace=true`。

旧有效继承仅：R44一个铁路接口3154024312482277635实际上下车/退出，两轮重复不是两个新增；R44原24源/25趟完整native call/entry/selector/ride/exit。R45改过约束缓存/邻近几何，其他生命周期仍需复验。

50实时源旧103506结果是1 `VERIFIED_LIVE_SERVICE`、49 `DIVERGED_OR_UNVERIFIED`；这不能写为全50 live PASS。其后caption/板面修订另有epoch，须当前新capture再分辨预测变化与helper偏差，不能扩大容差取PASS。256静态reader同样不代替全部1324门口合适导视。

F2最新旧失败20261001_202045在phase5，completed0，last32字段不存在；当前源码才包含last32。因此不能凭旧文件宣称当前源码first cause已关闭。新trace已准备，实际首次偏差必须Root重抓。技术中心柜前四去回的既有几何证据保留，但原生按钮/认证未通过，certifiedflag保持false；没有借此声明设备可用。

## 依据

运行权威为本机pinned MTR4.0.5和MovingElevators1.4.12实际JAR，SHA/API/bytecode已冻结。MTR的两高route-sign factory给两半建立原生BE，`platform_id`为Long，renderer使用真实动态route-map/arrow缓存；不是随意存ProjectSEELE MapRows。

[MTR官方源码](https://github.com/Minecraft-Transit-Railway/Minecraft-Transit-Railway)和[MovingElevators官方源码/控制说明](https://github.com/SuperMartijn642/MovingElevators)仅作机制参考；当前版本实现以pinned JAR为准，没有升级依赖或换掉现有模拟器。
