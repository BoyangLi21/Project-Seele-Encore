# Project SEELE: Encore

An open-source **Neon Genesis Evangelion** universe mod for Minecraft **Forge 1.20.1**.

一个开源的《新世纪福音战士》世界观 Minecraft 模组（Forge 1.20.1）。

一个 EVA 粉丝和算法爱好者，献给 EVA 与自己大学生涯的一次 Encore。

源码仓库：[Project-Seele-Encore](https://github.com/BoyangLi21/Project-Seele-Encore)。原 main 的完整历史已按原提交哈希迁入独立新仓库；旧 Project-Seele 仓库保留。已按负责人要求移除 Encore 的旧 feat/mcp-bridge 分支。

> God's in his heaven. All's right with the world.

## Status / 状态

R47 为当前人工验收候选，已生成并回读 **Server** 与 **Full Client** 两包：`Project_SEELE_Encore_R47_20261005_Server.zip`（618,645,000 字节）与 `Project_SEELE_Encore_R47_20261005_Client.zip`（376,629,795 字节）。Minecraft 1.20.1 / Forge 47.4.10 / Java 17，网络协议 **55**；服务端最大堆内存 **20G**。两端安装到新目录，使用同批模组、配置和 `SEELE_R47_WORLD`。个人交付包保存在本机 `D:/eva/delivery`，不作为公开源码仓库的素材下载。

三名原驾驶员已改在机库干区休息室待命，正常起身、短线步行登栓、离栓返回坐席均通过；保存重载后仍保持原驾驶员与坐席身份。旧登机桥的维护清理曾删除新房间下半部，现已修正房间位置与维护边界。总指挥直梯新增 Y=-364 的 SEELE 会议层，配最高权限刷卡入口、十二座编号碑、中央桌椅和局部灯光；保存后实体仍在。刷卡乘梯的玩家操作、画面和远端服务器效果由用户验收。

本轮加入零号机专用盾井、二号机专用剑井、独立12秒同步实验、原UUID回收与安全维护、NPC返程修补、指挥室灯总开关和运输/机库音效，并安装地形、围护、公共设施和旅客导视修补。Root最新八批应用汇总 **226,211条操作记录**，已包含48盏灯275格；这是分批状态/NBT记录，不是去重净差量。八地下精确平台ID已有20条实际自然停靠、96组四叶门及45份完整再生shard；五家北区住宅两层unknown=0，美里住宅全三宽楼梯与六份recipe、四店屋面维护结构已收束。实际开合、登车、步行和观感边界见 [世界覆盖事实](docs/R47_WORLD_COVERAGE.md)。

三机持刀与二号机长剑的精确三角静态检查均为0穿插；动作连贯性、观感与听感仍由用户验收。城市生产碰撞管线已在两端启用，代表塔的碰撞优化已有原生记录；整条城市恢复最近实测 **171.684 秒**，新增只读准备预算尚未实测，整体速度问题仍未关闭，见 [性能实录](docs/CITY_PERFORMANCE_R47.md)。默认 Terrain128 包关闭光影时的 LCL 橙红已在原生画面确认；光影观感、手动科研操作和远端服务器仍待用户验收。完整屋岛和港口战役按用户要求延期，不把工程候选或任务菜单称为全战役可玩。详见 [R47安装与人工验收](docs/MANUAL_ACCEPTANCE_R47.md)；[R46手册](docs/MANUAL_ACCEPTANCE_R46.md)及接续文档保留为历史记录。

进入配套世界：`/seele enter`。机库：`/seele tp hanger`。输入 `/seele tp` 查看全部传送地点。旧地图生成与原型实验指令不再出现在正式游戏中。

Development build with playable EVA piloting, physical entry-plug insertion, rail transfer, launch/recovery and NPC-operated controls. The local world connects Tokyo-3, a second city, stations, airports, the GeoFront headquarters and a separate UN test base. The ordered TV campaign currently covers Sachiel (episodes 1–2) and Shamshel (episode 3); later chapters and Third Impact remain in development.

当前开发版已经接通驾驶、真实插入栓吊装、轨道转运、发射回收和 NPC 操作控制台。地图修复采用逐格差量、真实人物碰撞、门／电梯联锁及全高度扫描。R24 增加地下设施路径导引、按用途细化的侧室与九十年代公共设施细节。

**Public source and the complete local demonstration world are different deliverables.** The repository includes code, project-authored resources and fallback visuals. Private evaluation maps, extracted models and uncleared third-party artwork are not bundled. / **公开源码不等于完整本机演示包。** 私有测试地图、提取模型及尚未确认公开许可的第三方素材不随仓库分发。参与和构建见 [CONTRIBUTING.md](CONTRIBUTING.md)，具体区别见 [公开准备](docs/OPEN_SOURCE_RELEASE_R24.md)。

Pilot controls / 驾驶操作：`WASD` 移动、`Space` 跳跃、`Shift` 蹲姿、`Z` 趴下/匍匐、`Ctrl` 奔跑、`B` 踢击、`R` 切换武器、`G` 开关 A.T. Field、左键近战/步枪、右键空手或近战武器重击（炮模式蓄能，N² 模式保险流程）、`V` 弹出插入栓、`O` 驾驶通信。三台 NERV 机体空手/短刀站姿下，方向键配合 `C` 闪避，奔跑配合 `C` 翻滚；机械准备/发射期间 `C` 仍优先取消发射。零号机盾牌与二号机长剑须从各自专用井实际领取，部署可用 /seele armament deploy shield / deploy sword 或卫星电话作战操作；错机不能领取。

## Docs / 文档

- [R47 安装与人工验收草稿](docs/MANUAL_ACCEPTANCE_R47.md) — 当前两包、实际操作、应用回执及未验证项
- [R46 安装与人工验收（历史）](docs/MANUAL_ACCEPTANCE_R46.md)
- [R45 安装与人工验收（历史）](docs/MANUAL_ACCEPTANCE_R45.md)
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

当前人工试玩使用 **R47独立新实例**、协议 **55** 与同批Server/Full Client。Full Client是普通实例目录包，先解压并沿用现有R46安装器流程，或在PCL新建1.20.1/Forge47.4.10后将本批文件按原层级复制到实例游戏目录；具体见R47手册。完整客户端保留配套模型、动作、材质及光影资料，默认渲染与光影中的地下亮度、橙红LCL和透明度分别验收。旧R45/R46实例只用于历史回退，不混入本批。

原生开发检查在专用副本运行，不能对玩家正式存档开启自动复核脚本。需要旧实验命令时显式设置 JVM 参数 `-Dprojectseele.developerCommands=true`。截图、检查记录及第三方评估素材不随公开源码分发；本轮具体检查范围见阶段手册。

## License / 许可

- Code is licensed under [MIT](LICENSE). / 代码使用 MIT 协议。
- This is an unofficial, **non-commercial fan work** created in the spirit of [khara's fan works guideline](https://www.khara.co.jp/guideline/). Not affiliated with or endorsed by khara, inc. / 本项目为非官方、非商业的粉丝创作，遵循 khara 官方二次创作指引精神，与 khara 公司无任何关联。
- No official assets (audio, artwork, footage) are or ever will be included. / 本项目不包含且永远不会包含任何官方素材（音频、原画、影像）。
