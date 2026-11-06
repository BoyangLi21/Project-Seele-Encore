# 哈希闸门删除报告（2026-11-06）

删除了代码库里所有"资产/数据字节必须与写死的摘要一致才放行"的校验。改动 153 个文件（+586 / −5261 行），删 14 个类、1 个测试、1 个资源清单。网格、地图数据、设施数据现在都可以直接改，不再因为字节变化报错。

## 判定口径

| 情况 | 处理 |
|---|---|
| 钉死常量或 JSON/NBT/配置里的摘要，与实际字节比较 | 删比较和拒绝分支，保留读取 |
| 存档里盖的摘要与当前值比较（"目录/网格变了就拒绝或挂起"） | 删；存档照常接受 |
| 只为把关存在的类（合同表、准入、验收、候选绑定） | 整类删，调用方走正常路径 |
| 钉死某个冻结版本的精确计数（如"必须 15998 个三角形"） | 删，或改成非空检查 |
| 只作缓存键、ID、日志、诊断报告的摘要 | 保留 |
| 同一进程内两个运行时值的一致性比较（资产改动不可能让它失败） | 保留 |
| 结构/物理有效性（非空、有限数、schema、路径安全、几何合法） | 保留 |
| 安装 `epoch` 版本号 | 保留（是显式版本号，不是字节摘要） |

## EVA 网格（优先项）

- `world/EvaOriginalMeshGeometryR52`：删三个带期望哈希表的 `install*` 入口和 `CLASSPATH_SELECTION`；`read()` 不再要求 SHA 一致（原 "Actual rendered resource changed" 的出处），只要求资源存在；删 `held_hand_surface_predecessors` 迁移白名单和 `replacesHeldHandSurface()`、`handContractFingerprint()`；`load()` 去掉哈希参数。保留 `sha()`：只给 `Part.sourceSHA256`、`Provider.sourceFingerprint` 作实际字节的标识。
- 删资源 `eva/eva_original_mesh_geometry_r52_sources.json`（内容只有 12 个钉死哈希）。
- `eva/ordinary_standing_support_hulls_r52.json`、`eva/prone_leg_support_hulls_r52.json`：删 `source_sha256`；`entity/EvaOrdinaryStandingSupportR52`、`EvaProneLegSupportR52` 删重算原网格 SHA 的块。
- `client/render/LocalVisualAssetFingerprint`：删 R11–R53 全部合同表、`MeshContract`、`SelectedR50Contract` 和 7 个 `matches*` 方法（−255 行）。`valid` 现在只表示四个资源齐全；逐资源 SHA 保留作抓帧标签和日志。
- `client/visual/VisualCaptureManager`：删钉死 14391/292|240/356 三角形的武器网格检查，改为只要求存在。
- `entity/EvaMechanicalFrameR52`：删 `HeldGeometrySource`、`GeometrySourceR52` 的比较和写入，删 `load()` 里两段 predecessor 迁移；`GroundGuideSourceR52` 改为"非空即已声明"。
- `entity/EvaFrozenHandsR52`：删 `ContractSHA256` 的写入和比较，`encode`/`decode` 去掉合同参数；新增 `sameFrozen()`，比较冻结手势时忽略旧存档里的这个键，否则 `capture().equals(...)` 仍是隐性摘要比较。
- `entity/EvaMechanicalReleaseR52`：删落地释放存档 `Source` 比较。`entity/NervCarrierPlatformEntity`：`lowerFrameDeclaredR52`、`declaredServiceFootDriveR52` 改为"戳非空"，`configureDeclaredCollisionSourceR52` 去十六进制要求。`entity/NervSiloDoorEntity`：删龙门架 cage 源比较。
- `physics/CombatBodyDynamics`：删手部合同指纹比较。
- 测试：`EvaOriginalMeshGeometryR52Test`、`NervServiceMeshR52Test` 不再读哈希回执，删"伪造合同必须被拒"断言。

## 其它 entity / client / network

- 整类删除：`network/CombatBundleGateR44`、`client/CombatContractClientR44`、`network/ClientboundCombatContractR44`、`ServerboundCombatContractR44`。这是登录时互发动作资源 SHA 清单、不一致或未确认就断线的握手。`SeeleNetwork` 去两条注册，协议号 76→77。`entity/CombatMotionResourcesR44.fingerprints()`、`config/PortableRuntimeOwnersR45.fingerprint()`、`physics/CombatBodyProfiles.fingerprint()`、`EvaAnatomicalHandsR45.contractFingerprintR45()` 随之无人调用，一并删除。
- `entity/CombatMotionResourcesR44.read`：删 `combat_bundle_r44.json` 清单 SHA 比对。
- `entity/EvaAnatomicalHandsR45`：Unit02 长剑不再要求 `source_mesh_sha256`，改为查网格是否存在。
- `entity/EvaRifleClearance`：删 `mesh_sha256` 比对；`EvaRifleGeometryR53Test` 改为断言旧哈希被忽略。
- `entity/EvaCannonFrameR45`：删未使用的 `MESH_SHA256`。
- `entity/FirstBattleClip`：删 `surface_deformation_r14` 对 `sachiel_wrap_r14.bin` 的校验（该文件全代码无人读取）及 `surfaceHash`。
- `entity/AngelGrappleSurfaceR31`：删只记录不比较的 `mesh_sha256` 字段。
- `entity/Unit03ReviewContractR53`：删文件哈希清单、runtime 清单逐项比对、`triangleCount==3909`、骨骼数 `==108`；保留评审包结构检查。
- `client/LocalPrivateShaderBootstrapR46`：删光影包、配方全部 SHA。**保留一条**：输出的 `License.txt` 必须与原包逐字节相同（运行时比较两份字节，为遵守光影许可证）。已有输出不同时改为重建覆盖，不再报错。
- `client/render/RamielSourceModelR53`：删 `source_faces==8816`、`removed_faces==0`。
- `world/RamielRemoteResourcesR52`、`RamielRemoteResourcesR53Test`、gradle 任务 `verifyRamielResourcesR53`：整体删除（运行时已无调用方）。
- `client/DeadSeaArchiveScreenR45`、`world/DeadSeaReadingR45`：死海文书"记为已阅"不再要求客户端和服务器文本摘要一致。
- `client/render/CarrierRearGuideRendererR53`：后导轨不再要求两份导轨文件摘要相同才绘制。
- `visual/TransportReturnR39Review`：删 class 字节 SHA 检查。
- `world/S20LiftManifestR52`、`S20LiftDirectoryR52`：电梯清单不再绑定路线目录指纹，`directory_fingerprint` 字段可有可无，保留 epoch。
- `world/LocalMapAssetLoader`：删 `buildPlanHash` 必填。
- `world/SurfaceAngelAssaultR52`、`event/TvEncounterDirectorR45`、`world/YashimaCannonHatchR54`：删阵地/站台布局摘要与存档戳比较，保留 ID/UUID 比较。

## NERV 几何源（`SOURCE_SHA` 类）

下列类的共同改法：删资源字节对 `SOURCE_SHA` 的比较、JSON 里 `*_sha256` 交叉校验，删 `SOURCE_SHA` 常量。

- 仅上述改动：`NervOuterCarrierGuideR52`、`NervFootGuideRigR52`、`NervShoulderBearingR52`、`NervHangarGateGeometryR52`、`NervSiloHatchGeometryR52`（保留 R16 的 240/876 原语数，后续按下标切割）。
- `NervBankHeadTransferR53`、`NervFootGuideDockR52`、`NervFootGuideStationR52`、`NervTurnStationRuntimeR52`：另外不再写入、检查 NBT 里的 `Source`/`GuideSource`；站点几何比较前剔除旧键，兼容旧存档。
- `NervOriginalCarrierR52`：`declared()` 只要求原 EVA 和 epoch；timeline/dock 不再写或比较 `Source`/`Deck`；删全部目录指纹比较。
- `NervLegacyCarrierRideR52`：删 `checked()` 和 4 个常量（`SOURCE_SHA`、`FLOOR_OVERLAY_SHA`、`FLOOR_MASK_SHA`、`DECK_SHA`）。
- `NervLegacyCompactLevelR52`、`NervLegacyServiceBypassR52`、`NervLegacyDeepFrameR53`、`NervLegacyBankClearanceR53`、`NervLowerFrameR52`、`NervFixedFootGuidesR52`：另外删 345、9、4912、21、6、`wall faces==4` 等版本计数和三角形摘要，改为非空检查。
- `NervMechanicalRailBindingR52`：删四个覆盖层 sha 规则和 guide/source sha 比较；旧键仍在白名单，缺失时为空串。
- `NervUprightGuidewayR52`：删 expectedSha 检查；已装导轨字节不同时改为重新解析替换（原来抛异常）。
- `NervCraneGeometryR52`：删 wheel SHA、28092/28044 三角形数，`load` 去哈希参数。`NervAirframeGeometryR52`、`NervPlantMotionR52`：不再比较期望摘要。
- `NervAircraftFrameR52`、`NervAirTransportManifestR52`、`NervAirTransportRuntimeR52`、`NervAirTransportStateR52`：删 `Sources`、`Manifest`、`FlightSourceR52`、目录和清单指纹比较；`mesh_sources` 可选；保留 epoch。
- `NervTravelDirectoryR52`、`NervPersonnelTransferR53`、`NervHeadquartersFrameR52`、`CommandRoomSlidingDoorDirector`：删 `directory_fingerprint`、门清单 SHA、`buttons==39`。
- `YashimaCannonMeshR52`、`TvYashimaStationR52`：删炮网格 SHA、手部合同、`StationLayoutR52` 比较。布局变化后已存在的炮不会自动重配。
- `client/render/NervUprightGuideRendererR52`：去掉诊断里的已校验字段。

## NERV 装配 / 路线 / 飞行 / R53 载架

- `NervRouteRuntimeStateR52`：删 `claim()` 的 "Existing R52 jobs require explicit native migration"、存档加载时的 "Saved job/Root claim mismatch"、恢复提交、bank curb、待定安装的全部目录指纹比较；待定请求只比 bundle/epoch/restoring（新增 `sameRequestR52`）。
- `NervRouteReservationsR52`：删任务、租约、硬件、快照的 12 处目录指纹比较。
- `NervRouteRuntimeR52`：删 ready、人员电梯、飞行、连续提交恢复中的存档指纹比较。
- `NervMechanicalTravelR52`、`NervLaunchPhasesR53`、`NervEmptyCarrierTransferR52`：删 `Directory` 比较。
- `NervRouteDirectoryR52`：删 `installation_receipt_sha256` 必填和"不得出现指纹字段"。
- `NervRootAssemblyInstallationR52`：删组件 SHA、bundle 指纹比较、活动控制器和恢复分支的摘要要求；bundle 没有 `directory_fingerprint` 时用 bundle 摘要作标识。
- `NervAssemblyOwnerR52`：删 `continuousGuidePathsShaR52`、`directory_fingerprint`、`commissioning_receipt_sha256`、`mechanism_sources` 钉值、`MachineDirectoryR52`、`BridgeDirectory`、5 处 `FlightSourceR52`、90947 格总数钉等；新增 `cageSourceR52()`。
- `NervFlightProofR52`、`NervHullGroundRecoveryR52`：删存档 `Source` 比较，飞机源不再钉 SHA。
- `FullAssemblyGeometryR52`：删 geo/legacy SHA、`GeometrySourceR52` 比较（"改了 EVA 网格后路线永久卡住"的来源）。
- `CarrierAssemblyR53`、`CarrierFootBearingR53`、`CarrierRearGuideR53`、`CarrierTransferRailsR53`、`CarrierMountProfileR53`、`CarrierEquipmentUpdateR53`、`CarrierBayMotionR53`、`CarrierOutletMotionR53`、`CarrierRearGuideMotionR53`：删清单 SHA、前代保留比对、8727/1894/6833 三角形钉、目录和硬件指纹比较。

## 城市 / 设施准入 / 评审作业

- 整类删除：`world/CityAtomicCandidateBindingR45`、`FacilitySourceAdmissionR45`、`CityColliderOracleCandidateR45`、`CityRigidQualityR45`、`OperatorNavigationR45`，`visual/TvCampaignNativeAcceptanceR45`、`CandidateLiftTripCasesR45`，`client/visual/CommandDoorInteractionReviewR45`、`FacilityComponentReviewR45`。删除前确认普通玩法不依赖它们。
- 调用点：`ProjectSeele`、`CityCreateDistrictR45`、`CityRigidTopologyR45`、`NervOperationsConsole`、`NervSecurityLifecycleR45`、`RegionalStationPhoto`、`LiftPassengerR20Review`、`CombatQueryNativeR44`。
- `compat/CityUnionActivationR45`、`config/PortableRuntimeOwnersR45`：删 Create 类 SHA 钉；4 个 `*_sha256` 配置键不再必填但仍允许出现。`mixin/SeeleCompatibilityPlugin` 本来就是 ABI 检查，未改。
- `OperatorNavigationProductionR45`：删图和验收文件 SHA、`MODEL_REVISION` 里的截断摘要。`NervWayfindingR24`：删 `graph_sha256`。`TvPersonnelSemanticEpochR47`：删 4 个 hex 常量和全部 `*_sha256` 比较。`RegionalBuildingQualityR44`：删 catalogue SHA。`CityCoordinationSavedDataR44`：删 revision 比较。`CityCreateRigidLiftR45`：删 93 个归档 SHA 循环和 cargo 比较。
- `TvEncounterRulesR45`、`TvYashimaDirectorR50`、`TvYashimaTransitR52`：删场地/清单摘要比较。
- `FacilityV2BuildDirector`、`FacilityV2SavedData`、`FacilityV2RouteGateDirector`、`FacilityV2StagedBuildDirector`、`FacilityV2EvaRuntime`、`GeoFrontFabricSavedData`：删 `buildPlanHash`、`regionCoreHash`、`contractHash` 等拒绝性比较。这些摘要由代码常量算出，属旧生成路径（R52 世界已退役）。`commit()` 里"计划变了就重建"是缓存键用法，保留。

## 刻意保留

- `EncounterObserverCacheR45`、`ServerboundEncounterObserverReadyPacket`、`EncounterObserverR45`、`RamielDistantViewR52`：`resourceSha256` 实为资源 ID 字符串，只防同一会话中途改变。
- `S20PhysicalElevatorDirector.fingerprint()`：电梯井坐标的字面描述，不是摘要；换井才拒绝。
- `TvEncounterSitesR45.fingerprint()`、`TvYashimaStationR52` 布局摘要：继续写入作任务身份，`TvMarineArrivalR50`、`TvYashimaArrivalR50`、`SurfaceAngelAssaultR52:70` 用它判断"是不是本次任务"，不因配置变化而拒绝。
- 同进程内存比较：`EvaMechanicalFrameR52`、`NervAssemblyOwnerR52`、`NervBallisticHandoffR52`、`NervFlightProofR52`、`NervHullGroundRecoveryR52`、`NervOwnerPlacementR52` 的几何证明对象；`FullAssemblyGeometryR52`、`NervRouteNativeR52` 的轨迹；`NervFixedFootGuidesR52`、`NervUprightGuidewayR52` 的 `enabledForDirectoryR52`。
- 仅日志、报告、缓存键：`EvaBodyPose`、`EvaGameplayMotionR32`、`CombatBodyProfiles`、`EvaEquipmentResourcesR45`、`EvaPoseGraph`、`TvCageEnclosureR44`、`AirLiftR40Client`、`TvCagePhysicalShapesR44`、`FirstBattleR10Review`、`EvaContactShadowsR24`、`FirstBattleRuntimeWitnessR52`、`LocalMeshJsonR53`（CRC32）、`FacilityV2Hashing`、`NervRouteRuntimeR52` 的距离复用。
- 非摘要的结构计数（个别可能带有版本味道）：34/30 手部关节，`NervSiloHatchGeometryR52` 240/876，`TvPersonnelPlatformInterlockR44` 208/12/6/202/427，`OperatorNavigationEngineR45` 202/201/24/6/12/291，`NervUprightGuidewayR52` bearings==10，`YashimaCannonMeshR52` 的包围盒/枪口检查。改这些资产时仍可能报结构错误，但报的是几何问题，不是字节不一致。

## 未处理

- `tools/` 不在本次范围：约千个脚本计算或写入哈希，其中生成器写的 `*_sha256` 字段已无运行时读取方。`tools/java` 里 11 个离线工具引用了已删常量，重新编译会失败；城市候选、设施准入、验收类脚本已失去作用。
- 资源文件里其余 `*_sha256` 字段保留，无害。
- `docs/` 里 `CITY_PERFORMANCE_R47`、`LIFTS_NERV_LIFECYCLE_R45`、`OPERATOR_NAVIGATION_R45`、`OPERATOR_NAVIGATION_PRODUCTION_R45` 仍描述已删机制。
- 个别已无用的参数保留：`NervAirframeGeometryR52.load(..,Map)`、`NervUprightGuidewayR52.install(..,expectedSha,..)`、`YashimaCannonMeshR52.requireOriginal`，`tools/java` 还在调用这些签名。

## 验证

- `./gradlew build` 通过，38 个校验任务全过（基于 efdf1d5）。
- 独立开发客户端（私有 r58 资产 + 完整本地模组，静音，世界 `HOTFIX_PERF` 副本），三轮都进入世界，各保持约 90 秒：
  - 本分支：无新增错误。
  - 本分支 + 改过字节的 `eva_unit01.mesh.json`（SHA `3f28daaf…` → `aedaf32c…`）：无新增错误。
  - 未改代码（8232103）对照：错误集合与上面两轮完全相同，都是已有的 superbwarfare 资源路径和注册表映射提示。
- 同一未改代码换用仓库资源覆盖私有资产时，服务器启动即崩溃：`Actual rendered resource changed: mesh/eva_unit00_anatomical_hands_r45.mesh.json`。本分支没有这个问题。
- 飞行、路线任务、出击等长流程只验证了编译、校验任务和进世界，没有在游戏里逐项跑。这些路径上的存档比较改动较多，建议用户实机过一遍。
