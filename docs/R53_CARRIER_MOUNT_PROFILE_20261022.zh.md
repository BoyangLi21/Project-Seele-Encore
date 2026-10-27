# R53 共用承载基准：候选生产接入合同

状态：2026-10-22 17:21，源码及纯 Java 合同已通过，未安装、未激活、未修改实际存档。本文只描述当前候选；原生运行和画面仍须单独验收。输出根目录为 `F:/eva/artifacts/r53_repair_20261015/rear-rail1022/geometry-v18-lateral-candidate`。

## 坐标和实体绑定

`CarrierMountProfileR53.State(aboveFloor,elevation,transverse)` 是唯一安装基准。旧入口默认 `LEGACY`；aboveFloor 的 elevation 为 0..4.25m，transverse 为 0..1，最大内收 0.65m。controller 仍是原三通道与原主轨线根，目录长度、速度、加速度、根朝向均不因 profile 改变。

| 入口 | 输入与意义 |
|---|---|
| `State.payloadFrame(controller)` | 原根局部 Y 加 elevation；机体、原栓、脚底、已绑定供电端点必须共同使用 |
| `State.controllerFrame(payload)` | 上述逆变换；禁止将抬高后的 payload 再送入根接口重复升高 |
| `State.bodyFrame(controller,rise)` | 原架 body 与固定新背轨源焊点；原机库下沉 64m 改为地上 1m 行程 |
| `State.headLiftFrame(controller,rise,lift)` | rear LIFT/头保留原 0..7m 世界升降，不附加 payload elevation |
| `State.carrierLocalFrame(source,part,rise,release,deckTravel)` | 完整 8,727 源三角面，保留原 X/Z 夹持回缩；出口 deckTravel 原意保留 |
| `State.shoulderMovement` / `shoulderEndRotation` | 只调整原肩夹动端；液压固定锚点、固定柱及人员桥不移 |
| `State.powerReelFrame` | 原架上电源卷盘源锚点的同源 frame；调用方仍须正确接入实际线缆两端 |

`CarrierMountProfileR53.read(machine,partial)` 对 transfer、gantry、hoist 共用。绑定存于现有同步 `LowerFrameR52` NBT 下的 `MountProfileR53`：Schema、Source（64 位 SHA）、Epoch、At、Previous/Current。无需新增网络 accessor。空绑定就是 legacy；非法绑定拒绝，客户端只在相邻已同步状态之间插值。该 channel 不读取单独的 carrier 任务表，因此 hoist 和 gantry 也能明确绑定同一批来源。

`CarrierMountProfileR53.PreparedUpdate` 是 world 包内可构造的提交 token：同 tick、相同实体 UUID、相同原 tag、相同来源/epoch，构造和提交都重验 `geometryCurrent`。初次 legacy→aboveFloor 只允许 `(elevation=0,transverse=0)`；之后的实际位移必须有完整证明。token 自身不证明碰撞，不写 root/clock/任务。禁止传常量 true，也不能把首次零位绑定当作所有旧停放状态的几何等价证明。

owner 详细入口与原 stalled 01 迁移策略见 `R53_CARRIER_MOUNT_OWNER_PLAN_20261022.zh.md`。原 `FootSupportFrameR52.Sample.evaRoot` 的含义必须拆清，连续路径缓存、租约、前视、最终 commit、PortableWindow 和脱离回落须使用同一组 controller/payload 样本。

## 生产文件与职责

| 文件 | 职责 |
|---|---|
| `world/CarrierMountProfileR53.java` | 共用 frame、两根工程杆延长、横向收纳、来源绑定 token |
| `entity/NervCarrierPlatformEntity.java` | 现有同步 NBT 的只读 getter 与 token 接收；旧 save/load 自动持久化 |
| `world/CarrierAssemblyR53.java` | 原源架 frame 的显式 profile 重载 |
| `world/CarrierRearGuideR53.java` | `Hardware.partsAt(...,State)`，原五参入口保留 legacy |
| `world/CarrierFootBearingR53.java` | 有限脚垫来源、足底/deck 支承与精确接触许可 |
| `world/NervShoulderBearingR52.java` | 完整液压杆件统一 transforms、有限肩部接触的 profile 重载 |
| `world/NervPlantMotionR52.java` | 完整 gantry 实网格和 broadphase 均用同一 profile |
| `world/NervOriginalCarrierR52.java` | 显式全架/后轨/脚垫 partsAt；实际载荷逆算根；aboveFloor 足底支承 |
| `client/render/CarrierAssemblyRendererR53.java` | 原架完整源渲染及新脚垫 |
| `client/render/CarrierRearGuideRendererR53.java` | 同一 partsAt 输出、区分旧/加长杆 GPU 缓存 |
| `client/render/NervOriginalCarrierRendererR52.java` | 读取实际 profile，地上收纳不再按旧地下 rise=0 隐藏 |
| `client/render/TvShoulderRestraintsR44.java` | 直接画生产 shoulder transforms，避免两套液压公式 |
| `client/render/TvCageEnclosureR44.java`、`TvFacilityMeshes.java`、`NervCarrierPlatformRenderer.java` | 贯通实际 gantry profile 和原 lower 状态 |

`NervAssemblyOwnerR52` 由 owner 接入分工负责，不在本实现范围。`CarrierRearGuideMotionR53` 的连续路径与迁移也未由本候选改动。hoist 由独立分工提供与本 profile 显式绑定的完整候选。

## 资源与有限接触

候选 `hardware.json` 是 V18 新横向工程件，SHA-256 `9ac0ecfb9a8d1a42d227c24128e75df05c2a445975f7ffaee7b17539341cceb1`。98 个件、45,498 三角面；原头、球、夹持器和原 carrier 源面完整保留。运行时仅把两个新增工程 lift rod 的最高端延长 4.25m；这一步由 renderer 和实际碰撞共同执行。实际 world 轨道不改。

`carrier_sole_bearings_r53.json` 为六个拟合原足底的新增支承件。运行时路径：`assets/projectseele/mesh/carrier_sole_bearings_r53.json`；选择文件：`assets/projectseele/eva/carrier_sole_bearings_r53_sources.json`。选择文件 resources 绑定准确字节 SHA；几何内的 carrier_source_sha256 还绑定原 `CarrierAssemblyR53.MESH`。尚未把上述文件装入实际包。

`CarrierFootBearingR53.bears(source,body,bodyFrame,controller,mounting,carrier)` 返回完整双脚有限支承；`permitsContact(...,bone,obstacle)` 仅允许实际源垫、同 frame、对应足底在限定多边形内的真实贴合。foot pads 不是整架/整机碰撞豁免。缺选择文件时 `selected()` 为空，显式 aboveFloor 原架全几何入口拒绝缺失源。

纯 Java 对照使用 `tools/java/AuditCarrierMountContractR53.java`；其独立旧候选没有改为调用新生产 frame，所以逐面一致不是同一函数自比。源码单编输出为 checkout 的 `.Codex/rear-review-classes`，无 Gradle/安装。结果 `PRODUCTION_PROFILE_CONTRACT.json`：rear 60,270、carrier 11,070、gantry 35,816 项一致；三机支承正例及 20mm 抬离反例、六只脚有限许可均符合预期。

完整静态/开合样本、原生固定柱反例、门代理及原楼板反例都保留。尚缺连续迁移、V18 全换轨/全部 actor、正常打开门后的真实路线、hoist 联动、正常 prepare/cancel/recover/再次出击、重载与画面验证。完成这些之前不得以候选资源或本合同宣称现场已解锁。
