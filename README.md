# Project SEELE: Encore

An open-source **Neon Genesis Evangelion** universe mod for Minecraft **Forge 1.20.1**.

一个开源的《新世纪福音战士》世界观 Minecraft 模组（Forge 1.20.1）。

一个 EVA 粉丝和算法爱好者，献给 EVA 与自己大学生涯的一次 Encore。

源码仓库：[Project-Seele-Encore](https://github.com/BoyangLi21/Project-Seele-Encore)。原 main 的完整历史已按原提交哈希迁入独立新仓库；旧 Project-Seele 仓库保留。已按负责人要求移除 Encore 的旧 feat/mcp-bridge 分支。

> God's in his heaven. All's right with the world.

## Status / 状态

R45 已打包为本地人工验收版。负责人承担美术、战斗与驾驶观感及服务器实测；本轮保留资源、动作状态和存档完整性检查，不声明全域重构或用户验收已经完成。安装、实际改动、操作和未启用项目见 [R45 人工验收手册](docs/MANUAL_ACCEPTANCE_R45.md)。六个 ZIP 已完成完整性与逐文件回读，和公开源码分别交付，不代表已上传网络发布。存档目录为 `SEELE_R45_WORLD`；为保留底本元数据，游戏列表显示名仍为“Project SEELE R44 阶段验收”。

进入配套世界：`/seele enter`。机库：`/seele tp hanger`。输入 `/seele tp` 查看全部传送地点。旧地图生成与原型实验指令不再出现在正式游戏中。

Development build with playable EVA piloting, physical entry-plug insertion, rail transfer, launch/recovery and NPC-operated controls. The local world connects Tokyo-3, a second city, stations, airports, the GeoFront headquarters and a separate UN test base. The ordered TV campaign currently covers Sachiel (episodes 1–2) and Shamshel (episode 3); later chapters and Third Impact remain in development.

当前开发版已经接通驾驶、真实插入栓吊装、轨道转运、发射回收和 NPC 操作控制台。地图修复采用逐格差量、真实人物碰撞、门／电梯联锁及全高度扫描。R24 增加地下设施路径导引、按用途细化的侧室与九十年代公共设施细节。

**Public source and the complete local demonstration world are different deliverables.** The repository includes code, project-authored resources and fallback visuals. Private evaluation maps, extracted models and uncleared third-party artwork are not bundled. / **公开源码不等于完整本机演示包。** 私有测试地图、提取模型及尚未确认公开许可的第三方素材不随仓库分发。参与和构建见 [CONTRIBUTING.md](CONTRIBUTING.md)，具体区别见 [公开准备](docs/OPEN_SOURCE_RELEASE_R24.md)。

Pilot controls / 驾驶操作：`WASD` 移动、`Space` 跳跃、`Shift` 蹲姿、`Z` 趴下/匍匐、`Ctrl` 奔跑、`B` 踢击、`R` 切换武器、`G` 开关 A.T. Field、左键近战/步枪、右键空手或近战武器重击（炮模式蓄能，N² 模式保险流程）、`V` 弹出插入栓、`O` 驾驶通信。三台 NERV 机体空手/短刀站姿下，方向键配合 `C` 闪避，奔跑配合 `C` 翻滚；机械准备/发射期间 `C` 仍优先取消发射。零号机蹲姿不再强制举盾，完整独立盾装备尚未启用。

## Docs / 文档

- [R45 安装与人工验收](docs/MANUAL_ACCEPTANCE_R45.md) — 本轮六包、操作、实际改动与未验证项
- [Mesh2Motion 全部 178 条动作与接入状态](docs/MESH2MOTION_ACTION_PLAN_R45.md) — 来源、动作族、当前候选与真实检查边界
- [R44 阶段操作与人工验收（历史）](docs/MANUAL_ACCEPTANCE_R44_STAGE.md) — 上一批安装与试玩记录
- [R44 下一轮接续](docs/R44_STAGE_NEXT_ROUND.md) — 动作、AT／第一人称、机库、全域美术与剩余交通验收
- [R44 全域执行范围](docs/GLOBAL_RECONSTRUCTION_R44.md) — 本轮原始要求与质量边界
- [R43 阶段手册（历史）](docs/MANUAL_ACCEPTANCE_R43_STAGE.md) — 上批操作及验收基线
- [工程清理记录（R43 历史）](docs/STORAGE_CLEANUP_R43.md) — 旧源文件恢复方法
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

本次人工试玩使用 **R45 的独立新实例**，不要混装旧 R44 的 mod、动作文件或 JVM 调试参数。网络协议为 **53**；Client、Client_Plain 与 Server 必须同批。完整 Client 带额外材质和光影，光影默认关闭；Client_Plain 去掉额外材质、光影与 Oculus，仍内嵌完整核心机体模型。保留旧实例和存档作为回退，具体导入方法见 R45 手册。

原生开发检查在专用副本运行，不能对玩家正式存档开启自动复核脚本。需要旧实验命令时显式设置 JVM 参数 `-Dprojectseele.developerCommands=true`。截图、检查记录及第三方评估素材不随公开源码分发；本轮具体检查范围见阶段手册。

## License / 许可

- Code is licensed under [MIT](LICENSE). / 代码使用 MIT 协议。
- This is an unofficial, **non-commercial fan work** created in the spirit of [khara's fan works guideline](https://www.khara.co.jp/guideline/). Not affiliated with or endorsed by khara, inc. / 本项目为非官方、非商业的粉丝创作，遵循 khara 官方二次创作指引精神，与 khara 公司无任何关联。
- No official assets (audio, artwork, footage) are or ever will be included. / 本项目不包含且永远不会包含任何官方素材（音频、原画、影像）。
