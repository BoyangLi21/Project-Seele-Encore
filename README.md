# Project SEELE

An open-source **Neon Genesis Evangelion** universe mod for Minecraft **Forge 1.20.1**.

一个开源的《新世纪福音战士》世界观 Minecraft 模组（Forge 1.20.1）。

> God's in his heaven. All's right with the world.

## Status / 状态

R43 阶段验收已收尾，全域质量重构仍在进行。当前安装与指令以 [R43 阶段手册](docs/MANUAL_ACCEPTANCE_R43_STAGE.md) 为准；未完成范围见 [下一轮清单](docs/R43_STAGE_NEXT_ROUND.md)。历史版本的通过记录不代表当前动作或美术已获认可。

进入配套世界：`/seele enter`。机库：`/seele tp hanger`。输入 `/seele tp` 查看全部传送地点。旧地图生成与原型实验指令不再出现在正式游戏中。

Development build with playable EVA piloting, physical entry-plug insertion, rail transfer, launch/recovery and NPC-operated controls. The local world connects Tokyo-3, a second city, stations, airports, the GeoFront headquarters and a separate UN test base. The ordered TV campaign currently covers Sachiel (episodes 1–2) and Shamshel (episode 3); later chapters and Third Impact remain in development.

当前开发版已经接通驾驶、真实插入栓吊装、轨道转运、发射回收和 NPC 操作控制台。地图修复采用逐格差量、真实人物碰撞、门／电梯联锁及全高度扫描。R24 增加地下设施路径导引、按用途细化的侧室与九十年代公共设施细节。

**Public source and the complete local demonstration world are different deliverables.** The repository includes code, project-authored resources and fallback visuals. Private evaluation maps, extracted models and uncleared third-party artwork are not bundled. / **公开源码不等于完整本机演示包。** 私有测试地图、提取模型及尚未确认公开许可的第三方素材不随仓库分发。参与和构建见 [CONTRIBUTING.md](CONTRIBUTING.md)，具体区别见 [公开准备](docs/OPEN_SOURCE_RELEASE_R24.md)。

Pilot controls / 驾驶操作：`WASD` 移动、`Space` 跳跃、`Shift` 单膝跪地、`Z` 趴下/匍匐、`Ctrl` 冲刺、`B` 踩踏、`R` 切换武器、`G` 开关 A.T. Field、左键近战/自动步枪、右键空手／刀重击（炮模式蓄能，N² 模式保险流程）、`V` 弹出插入栓。零号机展开 A.T. Field 后按住 `Shift`，即进入单膝举盾防御。战略武器测试与数值见 [`docs/WEAPONS_TEST.md`](docs/WEAPONS_TEST.md)。

## Docs / 文档

- [R43 阶段操作与验收](docs/MANUAL_ACCEPTANCE_R43_STAGE.md) — 当前五包、传送与检查步骤
- [工程清理记录](docs/STORAGE_CLEANUP_R43.md) — 保留范围和旧源文件恢复方法
- [R24 操作与验收（历史）](docs/MANUAL_ACCEPTANCE_R24.md) — 旧版记录，不作为当前操作入口
- [R24 开发与验证](docs/TV_DEVELOPMENT_R24.md) — 实际完成内容、证据与限制
- [R24 渲染与性能](docs/PERFORMANCE_R24.md) — 24 区块实测、车辆优化及 UN 区域的当前瓶颈
- [环境美术与参考](docs/ART_DIRECTION_R24.md) — 原创资源、实景依据及版本区分
- [B 站展示与同好共建](docs/BILIBILI_AND_COMMUNITY_R24.md) — 一次完整出动的分镜与贡献方向
- **[docs/ROADMAP.md](docs/ROADMAP.md)** — full plan through Third Impact & the Tree of Life / 完整路线图（直到第三次冲击与生命之树）
- [docs/SETUP.md](docs/SETUP.md) — dev environment setup / 开发环境搭建
- [docs/PROMPTS.md](docs/PROMPTS.md) — kickoff prompts for AI-assisted sessions / AI 协作开工手册
- [docs/VISUAL_RECOVERY.md](docs/VISUAL_RECOVERY.md) — fixed Visual Lab workflow and acceptance gate / 固定视觉实验室与验收门槛
- [docs/THIRD_IMPACT_VISUAL.md](docs/THIRD_IMPACT_VISUAL.md) — deterministic Tree/tableau capture and current visual verdict / 生命之树固定构图与当前验收结论
- [docs/LAUNCH_SILO_TEST.md](docs/LAUNCH_SILO_TEST.md) — launch carrier, high entry-plug gantry and manual test / 发射井、高位插入栓栈桥与测试流程
- [docs/GEOFRONT_TEST.md](docs/GEOFRONT_TEST.md) — connected Tokyo-3 / GeoFront, LCL and command telemetry / 连续地图、LCL 与指挥室遥测
- [docs/FRIEND_TEST_PACK.md](docs/FRIEND_TEST_PACK.md) — private LAN test bundle and server/client install / 私有联机测试包与服务器部署
- [docs/MULTIPLAYER_OPERATIONS_TEST.md](docs/MULTIPLAYER_OPERATIONS_TEST.md) — persistent NERV crew stations and server readiness / 持久 NERV 席位与服务器就绪诊断
- [docs/OPERATION_YASHIMA_TEST.md](docs/OPERATION_YASHIMA_TEST.md) — persistent Ramiel battle and visual gate / 持久化屋岛作战与视觉验收
- [docs/ANGEL_SIEGE_TEST.md](docs/ANGEL_SIEGE_TEST.md) — restart-safe Sachiel/Shamshel/Zeruel beacon defense / 可重启的三使徒信标防卫
- [docs/LCL_TEST.md](docs/LCL_TEST.md) — breathable recovery fluid and submerged-item persistence / 可呼吸恢复与浸没物品保护
- [docs/EVA_POWER_TEST.md](docs/EVA_POWER_TEST.md) — five-minute battery, umbilical pylon and shutdown interlock / 五分钟电池、脐带供电与停机联锁
- [docs/EVA_SYNCHRONIZATION_TEST.md](docs/EVA_SYNCHRONIZATION_TEST.md) — persistent pilot growth, response scaling and neural feedback / 持久同步率成长、响应增益与神经反噬
- [docs/EVA_BERSERK_TEST.md](docs/EVA_BERSERK_TEST.md) — autonomous Unit-01 override and forced shutdown / 初号机自主暴走与强制停机
- [docs/EVA_ARMAMENT_RACK_TEST.md](docs/EVA_ARMAMENT_RACK_TEST.md) — persistent physical EVA weapon loading and launch-bay racks / 持久化 EVA 实体装载与发射笼武器柜
- [CLAUDE.md](CLAUDE.md) — project conventions for Claude Code / 项目协作约定

## Roadmap (short) / 路线图（简版）

1. ✅ **Angels attack** — Ramiel fight, alert siren, real beam rendering, cross explosions / 拉米尔战、警报、真光束、十字爆炸
2. 🔄 **EVA Unit-01** — piloting/combat function as a prototype; visual and first-person gates remain open / 驾驶与战斗原型可运行；模型、动作与第一人称门禁仍未关闭
3. 🔄 **A.T. Fields & more Angels** — Sachiel, Shamshel and Zeruel combat prototypes now share a restart-safe NERV beacon siege; final models and visual acceptance remain / 三使徒战斗原型已接入可重启的 NERV 信标围城；最终模型与目视验收仍待完成
4. 🔄 **NERV / GeoFront / Tokyo-3** — connected local prototype, real LCL, live command room, deeply buried 640-block sphere, ceiling city and 522-block launch; art, multiplayer visual validation and licensing remain / 本机连续原型、真实 LCL、实时指挥室、深埋 640 格球体、穹顶都市与 522 格发射已接线；多人目视验收、美术和授权仍待完成
5. 🔄 **SEELE's scenario** — local Longinus/Mass EVA/Tree prototypes exist but have not passed the tableau gate / 本地朗枪、量产机与生命树已有原型，但构图尚未通过验收
6. ⬜ **Release** — integrations, optimization, CurseForge/Modrinth / 发布

## Building / 构建

Requires **JDK 17**.

```
./gradlew build
```

The mod jar is written to `build/libs/`.

## Local visual testing / 本机视觉测试

本次人工试玩使用 PCL 中的 **Project SEELE R43 Stage** 独立实例。Client ZIP 已内置模组、模型、存档及视觉资源，原 R42 实例保留。不要再使用旧版本的桌面启动副本或历史模型重建入口。

原生开发检查在专用副本运行，不能对玩家正式存档开启自动复核脚本。需要旧实验命令时显式设置 JVM 参数 `-Dprojectseele.developerCommands=true`。截图、检查记录及第三方评估素材不随公开源码分发；本轮具体检查范围见阶段手册。

## License / 许可

- Code is licensed under [MIT](LICENSE). / 代码使用 MIT 协议。
- This is an unofficial, **non-commercial fan work** created in the spirit of [khara's fan works guideline](https://www.khara.co.jp/guideline/). Not affiliated with or endorsed by khara, inc. / 本项目为非官方、非商业的粉丝创作，遵循 khara 官方二次创作指引精神，与 khara 公司无任何关联。
- No official assets (audio, artwork, footage) are or ever will be included. / 本项目不包含且永远不会包含任何官方素材（音频、原画、影像）。
