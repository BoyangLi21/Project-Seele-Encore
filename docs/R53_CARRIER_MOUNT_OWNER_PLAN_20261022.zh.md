# CarrierMountProfileR53 的 owner 接入边界

> 2026-10-23 状态说明：下文保留 10 月 22 日的候选推导，旧 7.2 m 取消状态和“未安装”描述已不是当前现场。原机已正常取消回库；当前方案为原位完整直立架、独立四爪、浅槽承轨与原桥后框调整，零号机已原位装架。初／二号机装架和完整出击回库仍在验证，以[当前任务清单](R53_ACTIVE_BACKLOG_20261020.zh.md)为准。整架抬高 4.25 m 或整体后移不是当前交付方案。

本文记录尚未完成的候选接入，不能视为已解锁现场。原初号机仍应保留相同 UUID、任务、7.2 m 路线距离和 16 m/s 的取消制动时钟；没有原生迁移或存档写入。

## 已接入的一小处

`NervAssemblyOwnerR52.actualCageCollisions` 使用实际 gantry 的 mount profile 调用 `NervPlantMotionR52.actualCollisionMembers`。新 profile 生效时，把当前完整结构网格的实际包围域合并进旧 broadphase，避免新抬高的肩垫/杆件在窄相碰撞之前被旧域裁掉。此处没有建立新 profile，也没有改变任务或设备状态；以前置 `.Codex/rear-review-classes` 加现有 runtime classpath 单独 javac 通过，没有安装。

## 当前最小分支：只研究独立横收解障

在完整上抬路径出现明确负例之后，当前优先级改为：保持 legacy 载荷高度、body/deck、controller、源目录、时钟和 lease，单独验证后轨头横向收纳。**这还不是已证明可执行的恢复方案。**

评估起点的 `CarrierMountProfileR53.State` 禁止 `aboveFloor=false` 时设置非零 transverse，且 `aboveFloor=true` 会连带切换 1 m 行程、延长杆件和新增承托面。不能用这个开关“顺便”启用横收。几何负责人正在保留 State 签名、增加 NBT 显式 `AboveFloor`，用 `false/0/transverse` 表达独立横收；空通道仍等价旧源，false 模式不得伸杆、改 64 m rise、加 sole 或抬 body/payload。

来源转换仍是独立问题：V18 几何候选替换了旧工程件 `mount/5` 并新增横收套，因此“执行器零位”不等于“全源几何与旧件完全相等”。必须分别列出原用户部件 mesh/frame 等价证明、旧工程件的替换清单和新件零位占用/接合证明；没有该证据不能自动创建 profile 来绕过起点连续检查。

最小调用链是：

1. 独立读取横收源、epoch、原 controller root、当前 head lift=7、方向和 slide；形成固定 root 下每件起终 frame。
2. 在原 full body/deck 不动、原 clock 不变时，严格证明横收件与完整固定 gantry、hoist、EVA/栓/驾驶员、电缆、方块和其他源部件的整段扫掠。球关节、杆件与导向件的接合必须有实际有限接触；不能只有外部不碰撞。
3. 提交同 tick 的已验 token，只更新横收通道。其他任何原件、任务、连续时钟和空间租约都不写。
4. `CarrierRearGuideMotionR53.continuous/bank`、`CarrierRearGuideR53.Hardware.partsAt`、`NervOriginalCarrierR52.actualPartsR52` 和 renderer 同读该通道。后续原正常取消必须重新证明当前完整制动窗口，再按原 16 m/s、原减速度消耗时钟。
5. 恢复后轨捕获之前需证明反向展开并确认每个真实接触面；不能让收窄的轨头在原固定轨上继续声称已捕获。

这条分支无需更改 controller/payload 的共同高度，也无需先做全局载荷标高校准。它只可能排除已定位的 ball_socket/固定 gantry 阻挡。旧 deck、toe、retract_spine 与楼板的接触仍受修正后的全载荷 preflight 约束，不得因为横收成功恢复 R50 的检查短路。

## 不能仅写一个新 tag

现有 `DirectoryTrajectoryR52.sample` 和 `FootSupportFrameR52.Sample.evaRoot` 同时承担载荷根与旧 controller 根的含义。新 profile 的 `payloadFrame(controller)` 升高载荷 4.25 m 后，两者已经不同。应显式区分：

1. 目录、路线长度、fraction、距离、制动 clock 继续定义 **controller 轨迹**，原轨道和 rear head 使用这个根。
2. 同一时刻由已绑定的 profile 计算 **payload 轨迹**；EVA、实际 plug binding、pilot、供电端点、脚底与新托板共用它。原始脚部局部点和 plugInEva 均保留。
3. 全载荷扫掠、前视、空间租约覆盖和最终 commit 必须使用同一 payload 轨迹；carrier 后部扫掠使用相应 controller 轨迹。禁止在某一个 commit 分支临时加 Y 偏移。
4. PortableWindow 中也要保留这一显式来源及状态，客户端用相同距离与变换恢复载荷位置，再逆算 controller；不能只改 renderer。

需要逐项复核的现有入口：`prepareContinuousRouteR52`/`continuousRoutePathsR52` 的缓存键，`prepareLeg` 与 `prepareBankHeadR53` 的根匹配，`sweptContinuousAssemblyR52`，`CheckedContinuousTraversalR52` 的同源切片/样本匹配，`applyVerifiedContinuousR52` 和最终 carrier commit，回库端点/接应/FinishRoot，以及供电连接器、原栓和 pilot 跟随。缓存必须包含 mount source、epoch 和执行器状态，不能重用旧高度的扫掠。

后续完整升高方案的具体调用映射如下；当前没有改这些路径：

| 现有入口 | 当前含义/风险 | 完整升高方案需要的分离 |
|---|---|---|
| `NervRouteRuntimeR52.continuousWindowR52`、每 tick `directory.routeSlices` | 由原目录距离生成统一 `DirectoryTrajectoryR52` | 继续保持 controller 源切片、原 fraction/长度；在 owner 处绑定同源 payload 视图，禁止更改 clock 总长 |
| `DirectoryTrajectoryR52.sample` | 目录脚底采样直接称为 `evaRoot` | 显式 controller sample 与 payload sample；同一绑定保留原本 `leftFoot/rightFoot/plugInEva` |
| `NervAssemblyOwnerR52.continuousGeometryR52` | cache 只比 route/binding/captured/from | 追加 source/epoch/profile，按 payload sweep 计算实际 chunk 域；执行器变化必须失效 |
| `prepareContinuousRouteR52`、`prepareLeg` | 实际 EVA 与目录根直接比较 | EVA 比 payload，carrier 比 controller；来源、绑定和旋转均不能只检查位置差 |
| `prepareBankHeadsR53` | 同一个 root 同时匹配 EVA 和 carrier | 分别匹配两根；轨头/方向/固定轨仍使用 controller |
| `NervRouteNativeR52.checkContinuousR52`、`CheckedContinuousTraversalR52` | proof 只存一份 source paths，`from/to` 直接取 sample | 同时持有 controller 源和不可变 payload 绑定；proof.current 重验 actor/profile/source/epoch |
| `FullAssemblyGeometryR52.CheckedAssemblySweep` | `TriangleSweepMeshR52.prepare`、pilot sweeps 和 actualFrame 都取统一 sample | 机体、手、栓、pilot 使用 payload 视图；`matchesSlices` 必须比较 profile 身份，防同目录不同高度冒充 |
| `DirectoryTrajectoryR52.footCentreLocal/error` | 半径以原脚底中点为旋转中心 | 如引入局部偏移，实际旋转中心在 payload-local 中也要相应逆移；非纯平移不能沿用旧曲率半径 |
| `NervOriginalCarrierR52.proposeContinuousR52`、`CarrierRearGuideMotionR53` | `path.sample().evaRoot()` 直接做 rear/source/controller | 保留 controller-only path；完整 carrier body/pads 按 mount 状态生成，rear head 固定原轨高 |
| `EvaMechanicalFrameR52.applyVerifiedContinuousR52` | 旧 portable path 与 from/to 的 EVA 根严格相等 | payload portable window 与 payload proof 相等；另保留原 controller 来源/clock 以供 carrier 逆算 |
| `DirectoryTrajectoryR52.encodePortableR52`、客户端解码 | v1 `RootOffset` 暗含 EVA/controller 同根 | 明确版本和绑定；payload offset 与 source identity 都可重验，旧空 profile 等价 v1；不能只在 renderer 加偏移 |
| `actualFrameMatches`、`rebindStoppedContinuousR52`、finishing placement / `FinishRoot` | 终点和重新捕获假设单根 | 真实停稳条件、原实体身份、payload 栓位和 controller 接应分别读回；不能靠重置 clock 重新捕获 |

最小实现方式应先建立一个不可变、可校验的 `controller path + mounted payload view` 类型，让 full assembly 消费 payload，carrier/rail 消费 controller。若选择在原 `DirectoryTrajectoryR52` 中增加双访问器，也必须保留清晰命名、上述半径修正与 portable 版本，不能悄悄改变现有 `sample` 而遗漏 rear 调用。全方案至少要补这些负例：同目录但 mount source/epoch 不同；proof 后 actuator 改变；载荷抬高后撞屋顶而旧 controller 仍净空；原 fixed head 在 payload 升高后不能跟着升高；正反路线 portable 相等且 clock 总长逐位保持；原栓和驾驶员与载荷绑定不可重新测量成假零偏移。

## 有限修复需要的真实证明

- 初次 `LEGACY → aboveFloor(0,0)` 是来源切换，不是普通运动。当前原 01 已升到 rise=1，旧 body 原位可保持；新增长杆、新托板仍须逐件核对新旧完整几何及占用域。其他停在 rise=0 的架体，旧 64 m 下沉与新 1 m 行程存在巨大差异，**不能套用这个原位切换许可**。
- 垂直升高阶段保持 controller 根、后轨头和路线时钟不变，载荷、承托 body/deck、plug、pilot、相应电缆端点一起沿真实局部 Y 轴运动。原 body 穿板的部件使用完整原网格、实际 block shapes 的有限单调退出证明；起点没有重叠的部件依旧走严格全段扫掠。该证明不能忽略整块起点障碍。
- 现有离线 `RescueTranslationEgressR53` 只证明固定姿态部件的有限平移。它不自动证明伸缩杆伸长、角色关节变化、旋转、actor mesh 相交或支承转交。必须按真实机构拆段，对每种运动分别证明；不准给这些阶段套用已有平移结果。
- 横向收纳 0.65 m 与升高是不同阶段，继续检查固定 gantry、hoist、其他原机体、完整电源与路线空间；当前 rear ball/gantry 反例不能通过删掉对方 mesh、排除整座 gantry 或放宽容差消除。
- `CarrierMountProfileR53.PreparedUpdate` 只提供同 tick 身份/tag/epoch/回调重验的提交容器，它本身没有几何证明。`geometryCurrent` 必须捕获真实冻结来源、全部原件和障碍版本，重新验证当前场景；不能传常量 `true`。
- 所有执行器 token 和载荷 token 预先通过，再同 tick 提交。部分提交失败必须明确报错并保留可审计状态，不能用清空 clock、FORCE/PARKED 或重建原实体掩盖。
- 装配修复到位后，先重新证明当前 7.2 m 开始的完整实际制动窗口，再由原正常取消继续消耗原 clock 到真实停稳；随后走正常 recover。迁移不等于取消成功。

原生验收仍缺：上述来源切换/每段运动的完整 proof、同 tick 全载荷读回、实际画面、正常取消回库、再次正常出发和冷重载。现有零距离回库 lease 修复、地图围边、原生导航回读均是独立完成项，不能替代这组机械验收。

## 当前旧架上抬的确定负例

`tools/java/AuditCarrierFloorEgressR53.java` 读取完整旧架 18 件和保留的实际 V17 root `(30.5,-1062,321.29999966919456)`，使用 `tools/query_blocks.py` 读取当前交付副本该网格及 +4.25 m 扫掠域的 76,296 格。源 mesh SHA 为 `4e0bd3c64a2904a166d1789a05a68fa8578095ce7dfacb3d53b9d1800956bffe`、profile SHA 为 `06023f8acd7ee912961eae283e6e07ccf66f1e4d6a916b683a4938de69435950`，均与实际 JAR 回读相同，相关 region 前后哈希相同。

仅已知 730 个原版完整立方碰撞就足以拒绝：`carrier/deck` 第 0 个三角面从下方上升时新扫入 `(38,-1063,333)` 的 `minecraft:light_gray_concrete`，结果 `new_contact_in_sweep`。这个三角面起点不与该方块相交，不能使用“初始重叠退出”例外。另以完整原局部 mesh 和实际 root 调用生产 `nativeBlockRejectionR53` 的零位回放，deck 已碰 `(19,-1063,314)`，retract_spine 已碰 `(28,-1063,314)`，toe_l 已碰 `(33,-1063,314)`，toe_r 已碰 `(22,-1063,314)`。独立横收不能自动消除这些原有阻挡。

其他已知件对子集的通过也不能冒充全场景通过：542 个特殊/模组 block shape 保留未知，完整 actors、EVA、原栓、驾驶员、后轨件和电源尚未纳入该单独反例。

证据在 `.Codex/carrier-floor1022/actual-current-floor.json` 与 `egress-current.json`，工具只读存档，没有原生移动，也没有安装候选。该结论停止当前统一上抬方案的推进，不证明任何其他机制必定无解。
