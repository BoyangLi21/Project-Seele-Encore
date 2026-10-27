# Project SEELE: Encore

**在 Minecraft 中，从 NERV 的机库走向第三新东京市。**

一个开源、免费、非商业的《新世纪福音战士》世界观模组。驾驶 EVA，展开 A.T. Field，迎击使徒，并让整备、出击、供电和回收成为真正可操作的过程。

An open-source, non-commercial Evangelion fan mod for **Minecraft 1.20.1 / Forge 47.4.10**.

一个 EVA 粉丝和算法爱好者，献给 EVA 与自己大学生涯的一次 Encore。

![GeoFront：森林中的 NERV 总部、人工湖与水下灯带](docs/images/geofront-r53.jpg)

*GeoFront · R53 开发世界，2026-10-18。由实际存档导出，在 Blender Cycles 中离线渲染；连续斜面、水体和摄影灯光经过宣传处理，不代表实时游戏画质或帧率。[图片来源与处理说明](docs/images/README.md)。*

[开发环境](#从源码启动) · [参与贡献](CONTRIBUTING.md) · [当前进展](#当前进展) · [完整路线图](docs/ROADMAP.md) · [素材与许可](docs/ASSETS.md)

## 可以体验什么

- **EVA 驾驶与战斗**：初号机、零号机、二号机、三号机与 UN 实验机，近战、武器、A.T. Field、同步率与初号机暴走。
- **机库到战场的机械流程**：插入栓吊装与接入、LCL 排注、转移架、发射舱门、轨道运输、发射和回库。
- **供电与后勤**：外部电源、脐带电缆、内部电池、装备领用，以及运输机接载和地上／地下转运。
- **NERV 与城市设施**：GeoFront、指挥室、第三新东京市、车站、电梯、机场和 UN 试验基地；NPC 可以操作整备与指挥设备。
- **使徒与剧情原型**：萨基尔、夏姆榭尔、拉米尔等战斗；屋岛作战正在接入本轮大更新，第三次冲击仍是后续开发内容。

这些系统仍在持续开发。**源码仓库与完整演示世界是不同的交付物**：公开仓库包含代码、项目原创资源和回退美术；完整本机存档及部分模型含第三方材料，未作为公开下载提供。直接构建源码不会得到宣传图中的完整地图与资源组合。详见 [公开分发边界](docs/OPEN_SOURCE_RELEASE_R24.md)。

## 本轮实机画面

![第三新东京市西区：建筑立面、道路与过街设施](docs/images/r54/tokyo-west.png)

![箱根地区：车站木构外观、铁路与既有街道](docs/images/r54/hakone-station.png)

*2026-10-26 本地客户端实机截图，启用光影，1280×720。[场景和图片说明](docs/images/README.md)。*

## 当前进展

**2026-10-27 · R54 近三测。** 本轮更新机械流程、角色动作和城市设施，提供配套服务器与 PCL 客户端用于人工试玩。安装方式见 [R54 联机说明](docs/R54_FRIENDS_QUICKSTART.zh.md)，已安装内容及后续项目见 [R54 需求记录](docs/R54_REQUIREMENTS_LOG.zh.md)。

本次联机修订处理机械插值与排液、升架耗时、远处机库实体与液体遮挡，以及 UN 雨天粉雾。服务器加入同版 Distant Horizons 实时更新，客户端保留离线远景；Xaero 两个地图模组更新到对应的 1.20.1 版本。

NERV 与 UN 电话更新手持模型、独立贴图和通信界面。最新联机流程已完成原初号机整备、发射、返库与下机；返库碰撞网格重复构建的性能修订已加入，实际流畅度和音画继续由人工试玩确认。

| 项目 | 当前状态 |
|---|---|
| 机库、出击与回收 | 原零、初、二号机均已完整返库，三位驾驶员已回各自座位；开放场地脱困改为机械辅助牵引和扶正，取消细部接触与整段预检造成的停滞 |
| 手部、普通动作与机体 | 修正 UN00 地面动作路由，重定向独立走跑与普通攻击；三号机改用自身握把数据，当前候选继续画面检查 |
| 城市与箱根 | 既有区域立面、箱根站及暖灯、山肩与出击坪修订已安装；三栋下沉楼基座去土已装，区域升降待人工试玩；新增道路和芦之湖移至下一轮 |
| 远景、湖面与 A.T. Field | 本轮536个变化瓦片已原生导入，站灯修订涉及的6块随后刷新；UN既有离线远景、低云高度、运输洞口舱门及九层八边形力场已接入本地试玩 |
| 屋岛作战 | 山地炮位、远距射击和零号机盾护已接入；本轮实测战败后的原机及装备回收完成，胜利与通关归档尚待实际验收 |
| 普通战斗与结算 | 沿现有战役继续检查胜利、回收和归档衔接 |

本地操作与反馈入口见[人工试玩说明](docs/R53_LOCAL_REVIEW.zh.md)。R54 客户端不含存档，保留完整模型、当前光影与包含 UN 区域的离线远景；旧安装包不包含本轮修改。三间独立病房和加深后的步枪武器井已装入当前世界并查看游戏实景。

地图的已装范围和待完成项见[城市与箱根更新记录](docs/R54_CITY_GEOGRAPHY_20261026.zh.md)。本轮参考[箱根汤本站设施](https://www.hakonenavi.jp/transportation/station/hakone-yumoto/)、[金时山地貌](https://www.hakone-geopark.jp/area-guide/hakone2/009kintokiyama.html)和[日本道路标示](https://www.npa.go.jp/laws/notification/koutuu/kisei/kisei20240301_1.pdf)，保留既有站场、通道和设施关系，不宣称已完成真实箱根或原作场景的等比例复刻。

默认 NORMAL 用于正常操纵，保留实际舱门、通行租约、承托和主体碰撞检查；STRICT 用于按需精细模型诊断。模式操作见[人工试玩说明](docs/R53_LOCAL_REVIEW.zh.md#管理与定位)。

动作、音色和美术由实际游玩继续调整。宣传图保留独立的离线渲染说明，不作为实时画质或性能承诺。

## 从源码启动

需要 **Git、JDK 17、Python 3.11+**。使用仓库自带的 Gradle 8.8 wrapper，无需单独安装 Gradle。

Windows PowerShell：

```powershell
git clone https://github.com/BoyangLi21/Project-Seele-Encore.git
cd Project-Seele-Encore
python tools/bootstrap_dev_dependencies_r24.py
.\gradlew.bat build
.\gradlew.bat runClient
```

Linux/macOS 使用 `python3` 和 `./gradlew`。首次构建会下载依赖并准备 Minecraft 开发环境；地图工具的跨平台支持另见 [参与指南](CONTRIBUTING.md)。

下载助手获取固定版本的公开依赖并核对校验值，保存在 `.Codex/local-mods/`。它不会下载私有地图或模型。构建产物位于 `build/libs/`；开发客户端日志位于 `run/logs/latest.log`。

| 命令 | 用途 |
|---|---|
| `gradlew build` | 编译、执行已接入的回归检查并生成模组 JAR |
| `gradlew runClient` | 启动可见的 Forge 开发客户端 |
| `gradlew runServer` | 启动开发专用服务器 |

环境配置见 [SETUP](docs/SETUP.md)。安装包需要使用同一交付批次的模组、配置和地图；旧测试包不会随源码更新而自动升级。

## 默认驾驶操作

游戏内「选项 → 控制」可以查看和修改键位。机械联锁、机体型号和当前装备会影响可用操作。

| 操作 | 默认输入 |
|---|---|
| 移动／跳跃／奔跑 | WASD / Space / Ctrl |
| 蹲姿／匍匐 | Shift / Z |
| 攻击／重击或炮蓄力 | 鼠标左键 / 鼠标右键 |
| 踢击／切换武器 | B / R |
| A.T. Field／驾驶通信 | G / O |
| 弹出插入栓 | V |
| 方向闪避／奔跑翻滚 | 方向 + C / 奔跑 + C；机械准备或发射期间 C 优先取消发射 |

零号机盾牌与二号机长剑需要在配套世界中实际领取。当前普通世界与完整 NERV 演示世界的设备布置不同，开发指令不能代替设施流程的验收。

## 仓库导航

| 位置 | 内容 |
|---|---|
| `src/main/java/com/projectseele/` | 游戏逻辑、实体、机械、网络、渲染和设施系统 |
| `src/main/resources/` | 模组注册资源、原创音效、贴图、模型与数据 |
| [src/test](src/test/) | 数学、几何、状态持久化、编解码等回归检查 |
| [tools](tools/) | 依赖准备、资产生成、地图审计和交付工具 |
| `assets-source/`、`art_sources/` | 已入库的可编辑美术来源 |
| `docs/` | 设计、来源登记、阶段记录和验证边界 |

贡献前请读 [CONTRIBUTING](CONTRIBUTING.md)。修改存档先读 [地图编辑协议](docs/MAP_EDITING_PROTOCOL.md)；动作与画面检查见 [视觉工作流](docs/VISUAL_RECOVERY.md)。构建通过不等于玩法、手感或美术验收通过。

## 许可与致谢

- 代码采用 [MIT](LICENSE)；第三方和衍生美术遵守各自许可，不能统一改标 MIT。
- 本项目为非官方、永久免费、非商业的粉丝创作，与 khara, inc. 无关联或背书，遵循 [khara 二次创作指引](https://www.khara.co.jp/guideline/)。
- 不包含官方音频、原画或影像素材。音效、模型、地图与动作的来源和修改记录见 [素材登记](docs/ASSETS.md)、[动作声明](docs/THIRD_PARTY_MOTION_NOTICES.md)。
- 当前仓库为 [Project-Seele-Encore](https://github.com/BoyangLi21/Project-Seele-Encore)，旧 Project-Seele 历史继续保留。

> God's in his heaven. All's right with the world.
