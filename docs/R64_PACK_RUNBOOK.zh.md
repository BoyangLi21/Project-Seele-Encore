# R64 打包流程（2026-11-15 干跑后写）

> 2026-11-22：R64 没有单独发布，本流程适用于 R65（打包工具里的版本名已改成 R65）。

工具在分支 `claude/r64-pack-prep`（385c7ea3）：`tools/package_r60.py`（R64）、`tools/rebake_r63.py`、`tools/dh_v6_prepare.py`、`tools/gen_green_grass_side.py`。所有 Python 用 `F:/eva/.claude/fable-review/pyfr/Scripts/frpy.exe -I` 跑；设 `JAVA_HOME=E:\Users\liboy\jdks\jdk-17.0.19+10`。工作目录 `WORK = E:/eva-r64-rebake`（每条命令加 `--work E:/eva-r64-rebake`）。开客户端的步骤先看 `slot.py status`，按规矩拿槽位。

## 前提

- 世界最后一批写完，记下批次号 N；代码定在 main 的某个提交，并已装进主客户端（`F:/eva/artifacts/r53_repair_20261015/client/mods`）。`--compare-build` 用同一提交的构建。
- R63r 客户端模板为 `Project_SEELE_Encore_R63r_20261115_Client_PCL.zip`。服务端模板和变动对照使用 `Project_SEELE_Encore_R63r_20261115_Server_Fix1.zip`。Fix1 回执逐项核对过 80,497 个世界条目，两种服务端模板的世界和起始远景相同。Fix1 还带 `server.jar`、启动器源码和 Forge 47.4.10 参数文件，打包时一并继承。
- 在其他磁盘彩排时，对每个烘焙步骤传入 `--work <工作目录> --source-world <停机副本> --source-client <配好候选私包的客户端> --reference-server <Fix1.zip> --batch-log <该副本对应的批次记录> --delivery <输出目录> --slot-name codex-pack`。打包时传入同一个 `--world`、`--client` 和 `--delivery`，并分别用 `--server-template`、`--client-template` 指定模板的完整路径。副本更名后，用 `--logged-world-folder HOTFIX_20261025` 指定同一世界在所选客户端日志中的原目录名，保留原有 DH 缓存标识。彩排最后只在副本验证远景替换。
- 磁盘预算见第 1 步输出。工具读取实际世界、客户端、起始库和外圈库的大小，给两份世界镜像、SQLite 写入和导出、指定范围的预生成、两份 ZIP 及打包临时远景库预留容量。WORK 与 delivery 在同一卷时合并计算。解压后的两套进服实例需另留空间。
- 当游戏候选构建与打包工具位于不同工作树时，对 `report` 和打包命令传入 `--release-source <候选代码工作树>`。配置默认值从这个工作树中的 Forge 定义读取，包内启动说明和发布说明也取同一版本。跨午夜运行时，生成命令及实际打包均传入同一个 `--date YYYYMMDD`，可保留原定版本日期。

## 步骤

| # | 做什么 | 命令 | 时间 | 磁盘 |
|---|---|---|---|---|
| 1 | 只读检查：世界锁、Java、变动区块、估时 | `tools/rebake_r63.py check --city-raised --xaero-pregen=-6464,-5408,7584,5920` | 1–2 分钟，按第 9 步范围给出串行总时 | — |
| 2 | **外圈远景重烘（用 R64 的生成器）** | **已完成（2026-11-17）**：39,160 段全齐，库在 `D:/eva-ringbake/client/saves/MAP_REVIEW/dimensions/projectseele/geofront/data/DistantHorizons.sqlite`（`prepare` 的默认 `--ring-db`）。外圈生成器（`OuterBoundaryTerrain`、`outer_edge.bin.gz`）改了才要重烘 | 已完成 | 3.63 GB（LZ4，保留；见下文压缩测试） |
| 3 | 烘焙实例 | `tools/rebake_r63.py instance` | 2 分钟 | E 0.8 GB |
| 4 | 镜像正式世界（持锁） | `tools/rebake_r63.py mirror --batch N` | 第 646 批共 80,724 个受检文件。四路逐文件 SHA 单端实测 5 分 7 秒，另计复制和目标端核验；第 9 步还要再做一份镜像 | E 1.6 GB |
| 5 | 远景起点换成 R63r 的 | 从上述 R63r Fix1 服务端 zip 取 `SEELE_R53_WORLD/dimensions/projectseele/geofront/data/DistantHorizons.sqlite`，覆盖 `WORK/client/saves/MAP_REVIEW/dimensions/projectseele/geofront/data/DistantHorizons.sqlite` | 1 分钟 | E 0.9 GB |
| 5b | **把镜像里的城市升起来**（远景按城市升起的状态烘） | `tools/rebake_r63.py raise`：短客户端，视距 2、不带 DH，以玩家身份 `/seele city raise`，等 R45 升到 Depth 0 再存盘退出；城市已升起就跳过。只改镜像 | 约 8 分钟（含进世界） | — |
| 6 | 合并外圈、删变动行，并做 V6 | `tools/rebake_r63.py prepare --v6`：升起后的楼和正式世界不同，算作变动区块，它们的旧行被删、由第 8 步按升起状态重建；`--v6` 接着对重建清单跑 `dh_v6_prepare.py` | 4 分钟 | — |
| 8 | 核心远景重烘（独占，8 GB，4 线程，LZ4） | `tools/rebake_r63.py core --exclusive` | 约 55 分钟，缺段多时补烘再加 ≤25 分钟 | E 输出约 1.2 GB |
| 9 | 小地图：城市升起、预生成外圈，再烘地表和完整洞穴层 | `tools/rebake_r63.py xaero --exclusive --city-raised --xaero-pregen=-6464,-5408,7584,5920` | 预生成约 4.1 小时（约 62 万区块，42 个/秒）+ 烘焙约 10 分钟 | E 镜像 1.6 GB + 预生成 3 GB |
| 10 | 生成打包命令 | `tools/rebake_r63.py report` | — | — |
| 11 | 打包检查（必须 0 处失败） | `tools/package_r60.py --check <报告> --geofront-lod WORK/out/geofront_lod.sqlite --xaero-map <report 给的路径> --compare-build <main 构建 jar>` | 1 分钟 | — |
| 12 | 打包 | 同上把 `--check <报告>` 换成 `--pack --date YYYYMMDD --map-note "<一行地图说明>" --server-address <地址>` | 5 分钟 | F 峰值约 6 GB |
| 13 | 本机专用服务器进服测试 | 解压服务端包，`Start-Server.bat`；客户端用打出的 PCL 包 | 15 分钟 | E 约 3 GB |
| 14 | **把新远景库换进正式世界**（负责人主客户端看到的城北"平顶墙"是正式世界自己的旧库：R62 时期 11-09/10 烘的 90,949 行 LZMA2，不在包里） | 世界必须关着：没有客户端或服务端开着它，`session.lock` 没被占（写入会话确认）。旧库连同 `-wal`/`-shm` 先备份到 D 盘 junction 之外的目录；删掉正式世界里的 `-wal`/`-shm`，再把 `WORK/out/geofront_lod.sqlite` 复制成 `HOTFIX_20261025/dimensions/projectseele/geofront/data/DistantHorizons.sqlite`。之后正式世界每写一批，DH 只会在玩家走近时更新那些区块，远处保持烘焙时的样子 | 2 分钟 | F 约 1.2 GB |

外圈远景库已就绪时，完整串行烘焙约 6 小时，小地图预生成约占 4.1 小时。第 9 步从第 8 步的客户端复制运行环境，两步在同一 WORK 下共用暂存模组目录，须依次执行。使用各自独立 WORK 和槽位时才能同时跑。第 9 步用自己的世界镜像，第 5b 步升起核心镜像中的城市，须在第 6 步之前执行。

同机有其他工作时，可用 `core --segment-minutes 5 --heap 8G --dh-threads 4` 分段重烘，或在长客户端正常保存退出后用同一个命令接续。每次从已保存数据库选择仍缺段的一个视点，短客户端退出后重新计算覆盖率，再排下一次槽位。工具默认在 Windows 可提交余量连续两次降到 6.5 GiB 时让当前分段客户端正常保存退出，并验明关闭日志及 SQLite 完整性。每段的补前、补后缺段数及原生日志写入 `WORK/logs/core-progress.json`。所有视点均无新增覆盖时会报告剩余缺段。

小地图启用 `--city-raised` 时会另建 `WORK/xaero-client/saves/MAP_REVIEW`。升城探针只接受已标记的审图世界或这个固定存档名。核心和小地图各用自己客户端里的审图存档，双方校验清单分别保留为 `manifest-MAP_REVIEW.json` 和 `manifest-R63_XAERO.json`。小地图成品统一导出至 `WORK/out/xaero`。烘图跨越午夜时，Log4j 会在结束前轮转日志。工具从同次 Forge 启动行拼接前一日归档和最新日志，将完整验收原文保存为 `WORK/logs/xaero-maps-native.log`。

小地图长客户端如需正常保存退出，等日志出现全部维度已保存、进程退出后，在同一 WORK 下执行 `tools/rebake_r63.py xaero --city-raised --xaero-pregen=-6464,-5408,7584,5920 --resume-pregen --pregen-strip-chunks 80000 --heap 8G`，沿用原有输入、槽位和路径参数。工具核对世界镜像、原始边界、升城状态及停机日志，从区域文件的每个区块槽位读取顶层 Status。整行已为 FULL 的部分可以跳过，剩余行分为互不重叠、含首尾的条带。每条使用一次短客户端，分别核验游戏完成计数、正常保存及该条带存盘后的全部 FULL。随后逐格复核整个矩形并烘焙地表及完整洞穴层。源世界原有 FULL、恢复前 FULL、分段访问数、最终新增 FULL 和各段时间见 `WORK/logs/xaero-strip-progress.json` 与 `WORK/logs/xaero.json`。

第 14 步换进去的库是按城市升起烘的；正式世界里城市现在是降下的（Depth 312），所以在正式世界里从远处看到的是升起的城市，走近后显示真实区块。

## R65 起：外圈存进包里的世界，城市升起（map-edges，2026-11-23）

R65 第一版发布后，负责人在远端服务器上看到外圈有缺口、一大片错误方块。
- 外圈区块从来没存进世界，都是服务器现场生成的。生成器有几处会生成错（第 5 项那 24 块），远景里显示的却是试玩副本里修好的样子。
- 包里的世界是降下的，远景却是按升起烘的，于是出现楼的虚影。

从 R65 起，打包用的世界在镜像上这样做（正式世界不改，保持降下）：

| 步 | 做什么 | 命令或做法 |
|---|---|---|
| a | 镜像正式世界 | 同第 4 步 |
| b | 把试玩副本里生成好的外圈原样拷进镜像 | `tools/ringcopy_r65.py <镜像>/dimensions/projectseele/geofront/region D:/eva-R64-playtest-fix/client/saves/MAP_REVIEW/dimensions/projectseele/geofront/region`<br>只填空位，镜像里已有的区块（包括第 697 批的 60 块）一律不碰；拷完逐条读回比对。<br>2026-11-23 实测：545,073 块，约 2.1 GB，十几秒，读回 0 错。 |
| c | 升城 | 第 5b 步 |
| d | 另存一份干净的包用世界 | 升城后立刻复制一份，不带 DH 库。level.dat 换回正式世界的那份（升城客户端改过游戏规则和时间），删掉正式世界里没有的 playerdata、stats、advancements 文件。这一份交打包；远景和小地图在另一份镜像上烘，因为烘焙客户端会改世界 |
| e | 远景和小地图 | 不再全量烘，以试玩副本的远景库和 Xaero 图为起点。`chunkdiff.py` 找出和试玩世界不同的区块，只删掉那些段，用短会话补烘（每次一个视点，悬停 5 分钟，开远处生成）；Xaero 在试玩的图上重转已存区域 |

配置：两边 DH 都是 `enableDistantGeneration=true`、`distantGeneratorMode="PRE_EXISTING_ONLY"`，服务器不会在外圈现场生成。客户端默认堆 6 GB。打包工具已经这样写。

## 2026-11-18 远景压缩测试（map-edges）

同一条路线（出生点、城区、GeoFront、东边海、北边山、UN 基地，每处 180 秒），发布设置、负责人的启动参数（-Xmx7168m，G1），每种两遍交替，世界每遍还原。加载时间 = 画面稳定在最终画面 5% 以内所需秒数，五处（不含 GeoFront）合计：

| 外圈 / 核心 | 加载时间（两遍） | 远景库 / zip 里 | 完全回收 / 最长停顿 |
|---|---|---|---|
| LZ4 / LZMA2（现行） | 207 / 342 秒 | 3.54 / 2.29 GB | 0 / 102、66 ms |
| LZMA2 / LZMA2 | 516 / 450 秒 | 1.16 / 1.04 GB | 0 / 371、229 ms |
| LZ4 / LZ4 | 393 / 324 秒 | 3.89 / 2.51 GB | 0 / 683、206 ms |

结论：外圈保留 LZ4（加载快约 43%，两个包在 zip 里各多约 1.25 GB）；核心区沿用 R63r 的 LZMA2 行，改成 LZ4 没测出提速。核心重烘新写的行按配置是 LZ4。工具和数据在 `D:/eva-ringbake/lzma-test`。

## 2026-11-18 DH 工作线程数测试（map-edges）

同一条路线和设置，外圈 LZ4、核心 LZMA2，只改 `numberOfThreads`，每种两遍。其他会话的客户端同时在跑，机器不独占。

| 线程 | 加载合计（两遍） | 帧率中位 / 最低 | 堆中位 | 完全回收 / 最长停顿 |
|---|---|---|---|---|
| 4（现行） | 282 / 231 秒 | 60、59 / 52、42 | 5.6、5.4 GB | 0 / 40、283 ms |
| 8 | 219 / 192 秒 | 60、60 / 38、5 | 6.2、6.4 GB | 0 / 398、299 ms |
| 12 | 159 / 279 秒 | 60、57 / 47、40 | 6.5、6.5 GB | 4、5 次 / 537、706 ms |

结论：保留 4。8 的合计少约 20%，但大部分来自 4 线程第一遍东边海的一个 153 秒；各处逐个比，8 和 4 互有快慢，算不上明显更快，堆却多用约 0.8 GB。12 在 7 GB 堆下每遍有 4–5 次完全回收（每次 0.3–0.7 秒卡顿），不能用。

## 打包工具自动做的（R64 新增）

- 客户端和服务端的 DH 配置都写 `dataCompression = "LZ4"`。烘焙时新写的远景行也是 LZ4；从 R63r 留下没重建的行仍是 LZMA2，能正常读。
- 服务端世界里的 `serverconfig/superbwarfare-server.toml` 打包时改成 `vehicle_chunk_loading = false`（找不到这个键就报错）。正式世界本身不改。
- 绿色草边资源包由 `tools/gen_green_grass_side.py` 现场生成，放进客户端包，并在 `options.txt` 的资源包列表最后启用（在 PBRJG 地形包上面）。
- 服务端带 Xaero 内嵌的 `xaerolib`；GeoFront 小地图带 `dimension_config.txt`（`caveModeType:2`）。
- 光影包 V2（perf）：`SEELE_Local_Cavern_R53_Review_20261026.zip` 在打包时加远景深度测试（`tools/shader_dh_entity_depth_v2.py`，改 `gbuffers_entities.glsl`、`gbuffers_spidereyes.glsl` 两个文件），远处的实体不再隔着远景透出来。包名不变，客户端默认就用它，`oculus.properties` 和同名 `.zip.txt` 不用动。主客户端里的包不用先改，打包工具每次从它现场生成。
- 说明文件用 `docs/R65_QUICKSTART.zh.md`、`docs/R65_RELEASE.zh.md`（打包工具按 `VERSION` 取这两个文件名；后者是草稿，打包前要定稿）。

## 2026-11-15 干跑结果

- 打包检查（main 9ae55f64 + 正式世界只读，模板 R63r）：只剩 2 处失败，都是还没烘的东西：`--geofront-lod`、`--xaero-map`。主客户端装的 jar 和 main 的构建逐类相同；R64 标志类都在。
- 生成的包内容（直接调用打包工具查看）：两边 DH 都是 LZ4；服务端世界的 SuperbWarfare 配置为 false；客户端 options 启用草边包，草边包和 R63r 的字节相同。
- 烘焙检查：世界锁空闲，Java 17.0.19；从第 455 批到现在 45,469 个 GeoFront 区块变了。
- 第 5–7 步在副本上试算（R63r 的远景库，外圈库为空）：删 72,644 行（其中 R63 的旧外圈 66,475 行），要重建 5,371 个 level-0 段，4 个视点，约 55 分钟；V6 再删 1,654 个上级、标 1,918 个子段。


## 2026-11-20 第 646 批副本彩排实测

本次在 D 盘按 11 月 19 日版本日期彩排。完整镜像包含 80,724 个待复制、逐份核对 SHA-256 的文件。最终核心远景覆盖 6,822 / 6,822 个最细段，外圈 623,211 个不同区块的存盘状态全部为 FULL。升城后游戏用约 6 分 56 秒绘制地表，再用约 45 分 38 秒绘制完整洞穴层，两层各有 649 份区域图。

双包预检 3 分 04 秒，实际打包并核对每个条目的 CRC 共用 1 小时 08 分 40 秒。客户端 ZIP 为 3,436,072,763 字节、2,797 项，服务端 ZIP 为 4,533,595,238 字节、81,019 项。打包阶段 D 盘工作目录实测峰值为 33.40 GiB，解出两个运行实例用时 4 分 11 秒。专服使用包内 `server.jar` 启动。实包客户端完成了两轮登录、GeoFront 维度确认、游戏内持续回包和存档。

### 专服停机顺序

在独立服务器发送 `save-all flush`，确认存档完成。玩家正常退出后，在控制台用 `list` 确认在线人数为 0，再检查 DH 后台区块更新是否空闲，然后发送 `stop`。本机用 JDK 17 的 `jcmd <专服 Forge JVM 的 PID> Thread.print` 查看名为 `DH-PriorityTaskPicker` 的工作线程，检查线程栈是否仍处在 `SharedApi.processQueuedChunkUpdate`。按实际工作线程状态判断何时停服。

- 首轮在玩家关窗后立即发 `stop`。客户端正常退出，服务器于 01:31:55 收到停服命令，到 01:32:02 才记下玩家离开。01:32:04 全部维度已存盘，但 DH 线程经 `ServerLevelWrapper.tryGetChunk` 等待 `ServerChunkCache` 的 future，150 秒后仍未退出。测试终止了该专服进程树。这是本轮复现的已知限制。
- 第二轮使用相同的两个包及首次保存后的世界。01:42:39 的 `list` 已确认 0 人在线。约每 10 秒检查一次，五次采样中的区块更新工作线程数依次为 2、0、0、0、0。01:43:32 收到 `stop`，01:43:36 全部维度已保存，01:43:38 专服自然退出。客户端和服务端退出码均为 0。这些间隔是本机该次负载的观测值，其他机器应以自己的在线人数、工作线程状态、存盘日志和进程退出状态为准。

停机镜像的远景替换演练用时 44.5 秒，旧库已经单独备份，新库 105,771 行，SQLite 完整性复查通过。彩排期间目录采样峰值为 43.82 GiB，考虑原子替换前旧库、其备份和新库同时在场的瞬间，按实测文件大小还原为约 44.06 GiB。D 盘最低空闲约 130.73 GiB。分步采样、两轮原生日志、线程栈和清理回执在 `D:/eva-codex-pack/README.zh.md`。
