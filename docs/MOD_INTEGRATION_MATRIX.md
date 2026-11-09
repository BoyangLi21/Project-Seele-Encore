# Project SEELE 模组联动矩阵

更新日期：2026-11-08

本文件记录私人开发环境中允许启用、仅作参考、以及明确禁止接管 EVA 骨骼的模组。正式发布前仍需重新核对许可证与作者授权。

## 已启用

| 模组 | 当前版本 | 用途 | SEELE 边界 |
|---|---:|---|---|
| [GeckoLib](https://modrinth.com/mod/geckolib) | 4.8.4 / MC 1.20.1 Forge | EVA、插入栓与复杂实体动画 | EVA 唯一骨骼、动画与状态机权威 |
| [Moving Elevators](https://www.curseforge.com/minecraft/mc-mods/moving-elevators) | 1.4.12 / MC 1.20.1 Forge | S20 人员电梯连续轿厢、楼层面板 | 只接管人员轿厢；不得接管 EVA 发射台、插入栓或物流机械 |
| [TrafficCraft](https://modrinth.com/mod/trafficcraft) | 1.20.1-1.1.3 / MC 1.20.1 Forge | 地图道路的沥青、1/8 格坡道、标线、路缘和人行道 | 只提供方块；GPL-3.0，随包附许可证和源码链接；正式存档写入它的方块前，所有实例必须先装好，见 [道路换用计划](ROAD_TRAFFICCRAFT_PLAN.zh.md) |

Create 与 Create: Connected 已于 2026-08-16 从运行时、构建、私人整合包和
R28 权威存档退役。SEELE 吊机、轨道和状态机只能使用自身实体/原版方块；代码中
保留的 `create:*` 判定仅用于读取并清除旧存档遗留，绝不是可选依赖。

## 可继续评估

| 模组 | 候选用途 | 采用条件 |
|---|---|---|
| [CC: Tweaked](https://modrinth.com/mod/cc-tweaked) | 指挥室可编程只读遥测屏 | 只有完成 SEELE 只读外围 API 后才安装；不得反向控制 EVA 状态机 |
| Simple Animator | 人类动作参考、NPC 表演参考 | 只借鉴动作节奏；不得覆盖 EVA GeckoLib 骨骼 |
| [Spears of Longinus](https://www.curseforge.com/minecraft/mc-mods/spears-of-longinus) | 朗基努斯枪的持握尺度、物品轮廓与命中反馈参考 | 1.20.1 Forge、MIT；先独立实例核验其实体/动画接口，不能让玩家骨骼动画接管 EVA |
| [Electrodynamics](https://www.curseforge.com/minecraft/mc-mods/electrodynamics) | NERV 高压供电、变电设备与阳电子炮供电场景 | 只在独立实例做性能与依赖审计；不把其能源网设为 EVA 状态权威 |

官方资料核验结果：Simple Animator 1.20.1 同时支持 Forge 客户端与服务器，
但其对象是玩家骨骼；Epic Fight 有自己完整的姿态与渲染体系。因此两者只进入
离线动作参考流程。CC:Tweaked 1.20.1 提供正式 peripheral API，未来只开放只读 NERV 遥测，
不开放 PREPARE、LAUNCH、RECOVER 等写操作。

### 2026-08-16 非 Create 交通与机械调研结论

| 候选 | 结论 | 原因/边界 |
|---|---|---|
| LittleTiles 1.6.0-pre161 + CreativeCore 2.12.39 | 仅作机械外形原型参考 | 能制作精细运动结构，但会成为存档硬依赖，也没有稳定的外部进度驱动 API；不得接管插入栓坐标 |
| PneumaticCraft: Repressurized 6.0.23 | 仅作工业机械臂造型参考 | 装配机械臂拥有自己的业务状态，不适合作为 SEELE 状态机的被动执行器 |
| Immersive Engineering 10.2.0-183 | 仅作工业美术参考 | 没有通用巨型吊机/机械臂控制接口 |
| FasterLadderClimbing（Forge 1.20.1） | 可选的维护直梯 QoL | MIT、客户端与服务端均需安装；只改变攀爬手感，不接管实体电梯 |
| Moving Elevators 1.4.12 | 已转入“已启用” | S20 既有 5x5 轿厢由适配层接入其连续运动与楼层面板；旧逐格搬运器随迁移停用 |
| Minecraft Transit Railway 4.0.5 | 条件评估公共区扶梯 | 有真实扶梯/自动步道，但依赖体量很大；只能用于人员公共区，不能进入 EVA/插栓物流链 |

结论：三台 EVA 的插入栓吊机和发射台继续由 SEELE 自己的状态机、实体和
原版方块渲染共同实现，任何第三方模组都不能成为第二坐标权威。Moving
Elevators 只负责人员电梯；扶梯候选仍须在独立副本验收后决定。

### TV 版兵装大楼资料边界

现有公开资料能高置信确认的是第 3 话镜头序列：屋顶锁销抬起、警示灯与四根
圆柱导向件、单扇大型前门，以及另一座装甲建筑横向展示备用步枪供 EVA 抓取。
地下输送路径、自动补充机构和内部货架没有公开官方剖面，不能再把推测写成
“原作 1:1”。正式重做兵装大楼时，应把上述可见镜头作为视觉合同；武器仍是
持久化权威实体，不能通过每次部署凭空刷新。

## 仅作本机参考，不自动打包

| 资源 | 可参考内容 | 禁止事项 |
|---|---|---|
| Ultimate Evangelion Addon (EUD) 1.1.0 | 物品分类、EVA 题材玩法覆盖面；本地 JAR 声明 CC BY-NC 4.0 | 发布前逐项保留作者署名并重新核对素材来源；不得无来源地改许可或去署名 |
| EvangelionAdd+ | EVA 物品轮廓与原型功能 | 自定义许可；不把 OBJ/贴图当正式发布资产，不接管 EVA 动画 |
| Rei Chikita Mod 1.1.7 | 旧 EVA 骨骼命名、动作节奏与内容覆盖面 | 本地 JAR 明确 All Rights Reserved，只能本机目视参考，绝不进入发行包 |
| EVANGELION END ADDON V1.0 | 使徒/EVA/量产机的题材覆盖与行为状态参考 | 它是基岩版 behavior/resource pack，不是 Forge 依赖；不直接移植资源 |
| Simple Animator 源码/样例 | 人体动作关键姿态 | 不作为 EVA 运行时依赖 |

参考 JAR 与源码只允许放在 `.Codex/reference-mods`、`.Codex/reference-sources`；这些目录不进入 Git、客户端包或服务器包。

## 禁止作为 EVA 运行时骨骼驱动

- Epic Fight
- Better Combat
- Player Animator / PAL
- VzlingLib 动画层
- 任何会在 GeckoLib 之后再次覆盖 EVA 手臂、躯干、腿部骨骼的系统

原因：双骨骼/双姿态权威会重现手臂反转、武器插胸、攻击时站起、第一与第三人称不同步等历史故障。战斗模组可以作为动作设计参考，但正式 EVA 动作必须转换为 SEELE 的 GeckoLib 动画并通过同一状态机播放。

## 联动设计原则

1. GeckoLib 唯一负责 EVA 骨骼、手指、姿态与动画混合。
2. SEELE 同时负责机械视觉和业务状态；不得再引入第二套 contraption/坐标权威。
3. 第三方 EVA 模组只用于私人参考评估，不自动复制、不自动打包。
4. 新联动先在独立本机实例验证，再进入 R28 权威存档。
5. 客户端和服务器必须来自同一次构建与同一份清单，禁止手工混用旧 JAR。
6. 许可证允许参考不等于所有内含素材都可再发布；正式包仍以 `docs/ASSETS.md`
   的逐项来源登记为准。

## 离线动作参考目录

私人参考 JAR 不进入发行包。用下面的命令只提取时长、骨骼覆盖与关键帧数量，
不会复制第三方矩阵或资源：

```bat
python tools\catalog_reference_motion_clips.py ^
  .Codex\reference-mods\epic-fight-20.14.17-mc1.20.1-forge.jar ^
  artifacts\mod-integration\epic_fight_motion_catalog.json
```

拳击、匕首、双手矛、跑步、跳跃和卧姿瞄准会映射到 SEELE 候选动作名，随后
仍须按 EVA 的 Tiger/SmOd 骨骼契约人工重定向并通过视觉验收；目录本身不改变
游戏运行时。

## 当前机械视觉层

- 三台 EVA 插入栓吊机使用 SEELE 登记的原版深板岩、铜、活塞与吊索几何；
  插入栓仍由唯一的 `EntryPlugDirector`/`EvaLogisticsDirector` 坐标契约驱动。
- 机库到发射仓的实体转运轨道使用铁块、深板岩、照明和 SEELE 载台实体。
- 战斗模组不得在 GeckoLib 之后覆盖 EVA 骨骼。

## 私人实机验收顺序

确认模组列表中不存在 Create/Create: Connected，再依次验收：

```mcfunction
/seele eva reset unit01
/seele dev eva dummy start unit01
/seele eva prepare unit01
/seele eva status unit01
```

`/seele dev ...` 只在开发构建里存在，见 [COMMANDS.zh.md](COMMANDS.zh.md)。

目视检查：固定拘束架不得随载台消失；原版吊机梁、吊索、推杆和夹具必须连续；
两条转运主轨必须可见；EVA 在解锁前仍由 SEELE 状态机固定。PREPARE 不得依赖
任何第三方机械方块。

动作资源刷新后执行 `F3+T` 或重启客户端，再看 `melee`、`knife_heavy`、
`lance_thrust`、`run`、`jump` 与卧姿瞄准。Epic Fight/Simple Animator 不应
出现在运行时模组清单中；它们只服务离线姿态参考。
