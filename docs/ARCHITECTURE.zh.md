# Project SEELE 架构导览

Minecraft 1.20.1 与 Forge 47.4.10 负责实体、方块、网络事件和存档生命周期。模组入口在 `src/main/java/com/projectseele/ProjectSeele.java`。下表中的类名可直接在该目录下检索。

| 子系统 | 从哪里读 | 数据如何流动 |
|---|---|---|
| EVA 动作 | `EvaMotionModelR64`、`EvaGameplayMotionR32`、`EvaPlantedGaitR64`、`EvaUnit01Renderer` | 服务端同步移动模式与机体状态，客户端按步态、动作片段和地面接触绘制骨骼。改姿态时也检查世界坐标中的脚掌和骨盆。 |
| 战斗 | `EvaCombatModelR64`、`EvaCombatCommandsR64` | 机体的战斗模型决定可用招式及帧阶段。显示用的手臂动作、服务器位移和有效击中时段应按同一招式核对。 |
| 驾驶舱 | `PilotCockpitR64`、`CockpitMeshR64` | 第一人称相机和驾驶舱网格在客户端合成。供电、机体和武器面板读取驾驶状态。 |
| 城市升降 | `CityCreateDistrictR45`、`CityRigidGenerationR45` | 每栋楼有轮廓、升起和回收位置。移动开始时按现存方块采集货载，行程日志记录两个端点。新区块从存档中的地面配方和有效货载恢复。 |
| 出击和运输 | `NervRouteRuntimeR52`、`NervAirTransportRuntimeR52` | 运行时读取已安装的路线、站位与门的归属。地面发射架和空运分别管理各自负责的行程。 |
| 屋岛作战 | `TvYashimaDirectorR50`、`YashimaCannonEntityR52` | 剧情推进与炮实体分别管理阶段和机体交互，客户端显示相应的灯光、动作与场景。 |
| 地图生成与记录 | `HakoneSurfaceField`、`OuterBoundaryTerrain`、`tools/map_pipeline/` | 地形采样、原生区块、可重建配方与远景缓存各有自己的数据。修复需要明确 XYZ、维度和修改前后的方块状态。 |

## 地图修改与交付

1. 用 `tools/query_blocks.py` 从目标世界的副本读取实际方块。记录所用维度、坐标、区块和当前城市升降状态。
2. 依据原生数据生成修改清单，在停服副本写入。深层坐标可使用 `tools/write_deep_cells.py`。可移动建筑同时需要处理货载，机械区域还要核对开口和设备。
3. 写入后读回目标方块，确认周围方块及方块实体。地图批次使用 `tools/map_pipeline/defect_ledger.py` 和 `delivery_check.py` 记录缺陷和交付状态。
4. 对实际修改区域更新 Xaero 图块、远景层级和相关缓存；启动前核对客户端、世界、维度和地图包使用同一批数据。
5. 从已冻结的输入生成服务端与客户端交付件。构建和打包命令见[构建与打包](BUILD_AND_PACK.zh.md)。

美术贡献和动作资料见[贡献指南](../CONTRIBUTING.md)、[动作改造说明](MOTION_OVERHAUL.zh.md)和[素材登记](ASSETS.md)。