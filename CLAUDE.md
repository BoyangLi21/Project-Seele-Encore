# CLAUDE.md — Project SEELE 协作手册

> 给接手本项目的 Claude Code：先读这个文件，再读 `docs/ROADMAP.md`（完整计划）。
> 新机器环境搭建见 `docs/SETUP.md`；每个阶段的开工 prompt 见 `docs/PROMPTS.md`。

## 项目是什么

**Project SEELE**：开源的《新世纪福音战士》(EVA) 世界观 Minecraft 模组。
使徒 Boss 战 → 可驾驶 EVA → AT 力场体系 → NERV/GeoFront/第三新东京市 → 第三次冲击（生命之树）终局事件。
完全免费、完全开源、严格遵守 khara 二次创作指引（见下方红线）。

- 仓库：`git@github.com:BoyangLi21/Project-Seele-Encore.git`（GitHub 账号 BoyangLi21）。旧仓库 `Project-Seele`（remote `legacy-origin`）不再推送
- 当前进度：EVA 动作和战斗在打磨，地图收尾中。地图的现状、工具和规则见 `docs/HANDOFF_CODEX_20261106.zh.md`

## 技术栈（版本锁定，勿擅自升级）

| 组件 | 版本 | 备注 |
|---|---|---|
| Minecraft | 1.20.1 | Java 版 |
| Forge | 47.4.10 | MDK 模板化，属性在 `gradle.properties` |
| JDK | 17 (Temurin) | Forge 1.20.1 硬性要求 |
| Gradle | 8.8 | wrapper 已指向腾讯镜像（国内提速） |
| GeckoLib | 4.x（Phase 2 引入） | maven: `https://dl.cloudsmith.io/public/geckolib3/geckolib/maven/`，坐标 `software.bernie.geckolib:geckolib-forge-1.20.1:<ver>`，用 `fg.deobf()` |
| 映射 | official (Mojang) | |

## 常用命令

```
./gradlew build        # 编译 + 产出 build/libs/projectseele-<ver>.jar
./gradlew check        # 全部检查，一个 JVM 跑完（AllChecks），约 1 分钟
./gradlew runClient    # 启动开发客户端（离线账号，无需登录）
./gradlew runServer    # 专用服务器（Phase 6 验证用）
```

- 游戏日志：`run/logs/latest.log`（每次启动重建，验证 mod 加载搜 `Project SEELE initialized`）
- 首次构建要反编译 MC，视 CPU 10–60 分钟；之后增量构建 <1 分钟
- gradle daemon 已启用（`gradle.properties`），内存 4G

## 代码结构

```
com.projectseele
├── ProjectSeele.java        # 主类：注册 DeferredRegister、commonSetup
├── CommonEvents.java        # MOD 总线事件（实体属性注册等）
├── registry/                # ModItems / ModEntities / ModCreativeTabs（新注册类型都放这）
├── entity/                  # RamielEntity（含内嵌 MoveControl/Goal AI）
├── item/                    # PositronRifleItem
└── client/                  # ClientEvents（渲染器注册，Dist.CLIENT）
    └── render/              # RamielRenderer（直连顶点渲染，无模型文件）

resources/
├── assets/projectseele/     # lang(en_us+zh_cn)/models/textures
└── data/projectseele/       # loot_tables 等
```

**注册模式**：一律 `DeferredRegister` + `RegistryObject`，注册类放 `registry/`，在主类构造器挂到 mod 总线。
**指令**：`/seele` 只在 `visual/SeeleCommands` 注册一次，权限写在一级子指令上；别的类只提供返回 `LiteralArgumentBuilder` 的方法，不要再自己 `register(Commands.literal("seele"))`。指令表见 `docs/COMMANDS.zh.md`。
**代码风格**：跟随 Forge MDK（Allman 大括号、UTF-8），注释只写代码看不出来的约束。
**渲染惯例**：几何体（使徒、特效）优先直连顶点渲染（参考 `RamielRenderer` 的八面体画法）；人形/复杂动画用 GeckoLib。

## 协作约定（用户偏好，务必遵守）

1. **中文交流**。
2. **Commit 署名**：每个提交末尾加 `Co-Authored-By: Ayanami_Rei <liboyang_621@126.com>` 和 `Co-Authored-By: AsukaSoryu9 <2549517657@qq.com>` 两行（用户的项目分身账号），**不要**加 Claude 署名——这是用户明确要求。多行提交信息用 `git commit -F <文件>` 避免引号问题。
3. **工作流**：构建通过 + runClient 日志验证无误 → commit + push（用户已授权此流程）。提交用 `git -c user.name=BoyangLi21 -c user.email=liboyang621@gmail.com commit -F <文件>`；推送前 rebase 到 `origin/main`，`./gradlew build` 退出码为 0 才 `git push origin <分支>:main`。游戏内目视测试由用户负责——你看不到画面，写好日志检查点后把"看什么"列清楚交给用户。
4. `.claude/` 目录已 gitignore，**永不提交**。
5. 用户负责 GUI 安装类操作（装软件、网页建仓库）；其余全部你来。
6. 数值平衡（伤害/血量/冷却）改动要在回复里明确列出前后值，用户拍板。

## 合规红线（不可妥协）

- **永不**引入官方素材：音频（尤其 BGM）、原画、影像截图一概不行。音效用原创合成 / CC0 素材（登记来源），贴图全部原创。
- 永久免费、非商业。遵循 khara 指引：https://www.khara.co.jp/guideline/
- 代码 MIT；引用他人地图/模型必须先取得授权（待办清单见 ROADMAP §9）。

## 验证套路（无人值守测试）

1. `runClient` 用后台任务启动，同时起一个日志监听（PowerShell `Select-String` 轮询 `latest.log`）。
2. 检查点：`Project SEELE initialized` = 加载成功；再全文扫 `projectseele` 附近的 `error|missing|exception` = 资源/注册问题。
3. 实体行为验证：让用户 `/summon projectseele:ramiel ~ ~5 ~20`，生存模式触发 AI。
4. 提交前必须 `./gradlew build` 通过。

## 当前数值表（2026-07 的记录，改平衡前先核对 `SeeleConfig`）

数值已全部外置到 `SeeleConfig`（游戏目录 `config/projectseele-common.toml` / `-client.toml`），改平衡不用重新构建。下表为默认值：

| 项 | 值 | Config 键 |
|---|---|---|
| Ramiel 血量/护甲 | 350 / 6 | `ramiel.maxHealth` / `ramiel.armor`（`finalizeSpawn` 应用） |
| **AT Field** | 未露核**完全免伤**+近身8格推开 | 硬机制（无 config；`hurt()` 拦截） |
| **露核窗口** | 蓄力最后20t + 发射后60t | 常量 `EXPOSE_CHARGE_WINDOW` / `EXPOSED_AFTER_FIRE_TICKS` |
| 光束伤害/爆炸半径 | **120（核弹级）** / 12 | `ramiel.beamDamage` / `beamExplosionRadius` |
| 光束蓄力/冷却/射程 | 50t / 90t / 64 | `ramiel.beamChargeTicks` 等 |
| 二阶段蓄力（血量<40%） | 30t | `ramiel.beamChargeTicksEnraged` |
| 钻头伤害/持续/冷却 | 4×每10t / 80t / 300t | `ramiel.drillDamage` / `drillCooldownTicks` |
| **EVA初号机血量** | 300（抗两枪120，第三枪死） | `eva_unit01.maxHealth` |
| **EVA近战** | 拳20 / 粒子刀60，**接触中和拉米尔AT Field** | 常量（`EvaUnit01Entity`） |
| **EVA AT Field** | 值池200、普通伤害免疫、使徒伤害耗池溢出入血、5s后回复0.4/t | 常量；G键开关 |
| **狙击炮蓄力/射程/冷却** | 60t / 512 / 200t（EVA武器，R键切换，蓄力时定身） | `positron_cannon.*` |
| 狙击炮命中露核核心 | **210（两枪毙命，已计护甲减免）** | `positron_cannon.coreDamage`；命中壳=`mobDamage` 40；命中点爆炸半径 4 |
| EVA重砸（右键，非炮模式） | 拳35/刀80，9格AOE，3s冷却 | 常量；炮模式右键=蓄力 |
| 体型 | 拉米尔 12×12 / EVA 24 格（2026-07 用户拍板 ×2） | hitbox+渲染常量 |
| 步枪伤害/冷却/射程 | 16 / 25t / 96（对使徒被 AT Field 全弹开） | `positron_rifle.*` |
| 警报总开关/音量 | true / 0.45 | `ramiel.alarmEnabled`（音量为常量） |
| 客户端特效强度/警报红屏 | 1.0 / true | `screen_effects.*` |
| 核心碎片掉落 | 4–8 (+抢夺) | `loot_tables/entities/ramiel.json`（不在 config） |

非平衡类几何/演出常量（光束存续 tick、钻头半径、核心判定半径 2.2 等）仍在类顶常量区。

## 已知占位/技术债

- 贴图为程序生成 32×32（生成器：`tools/gen_textures.ps1`），欢迎高清重绘（资源包可覆盖）
- 音效已全部替换为原创合成（`tools/gen_sounds.ps1`，登记于 `docs/ASSETS.md`）；后续可迭代音色质感
- `ResourceLocation(String,String)` 有过时警告（Forge 迁移提示），1.20.1 内无害，Phase 6 统一清理
- `run/saves/` 内有本地测试地图，**永不提交**。NERV 总部地图源自 Audijon2（见 `docs/ASSETS.md`），发布时署名，发布前告知作者
- 写 `.ps1` 脚本只用 ASCII 注释：PS 5.1 把无 BOM UTF-8 当 ANSI 读，中文注释会炸解析
