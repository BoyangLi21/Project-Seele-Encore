# R63 重烘和打包清单

R63 的远景（Distant Horizons）和小地图（Xaero）都在副本上重做，正式世界不打开、不写入。工具是 `tools/rebake_r63.py`（重烘）和 `tools/package_r60.py`（打包，版本已改成 R63）。下面的命令都在仓库根目录跑。电话工具开着时，Python 的可执行文件名不能以 `python` 开头，用 `F:/eva/.claude/fable-review/pyfr/Scripts/frpy.exe`，下文写作 `frpy`。

## 为什么要重做

- 正式世界的 GeoFront 远景库还是 R62 那份（第 378 批，2026-11-10 06:53）。拿 R62 服务端包里的世界逐区块比对，到第 455 批为止：9,828 个区块内容变了，54,538 个外圈区块被删（第 415 批），没有新增区块。
- 旧远景库 90,949 行里有 80,965 行画的是删掉的旧外圈（远处那堵“墙”），必须换成 map-edges 在 E 盘按新边界烘的外圈。
- 小地图是 R62 当天烘的，世界之后又写了很多批，打包工具会拒绝。

## 远景怎么合

在镜像副本的 GeoFront 远景库上（`prepare` 一步做完，不碰正式世界）：
1. 按正式世界当前已保存的区块给每一行分类：全部已保存 = 核心，一个都没保存 = 外圈，其余 = 边缘。
2. 删掉：外圈行、边缘行，以及含有变动区块的核心 level-0 行。
3. 从 map-edges 的远景库（E 盘副本，用 SQLite 备份接口只读快照）取：外圈的所有层级，加上没有变动区块的边缘 level-0 行。
4. 父行被删掉的行打上 `ApplyToParent`，让 DH 自己重建上层（DH 平时就是这样从下往上合成粗层级的）。
5. 列出所有有已保存区块、却没有 level-0 行的段，按每个视点覆盖 40 段（2,560 格）贪心选视点。

然后 `core` 一步开一个客户端（`PRE_EXISTING_ONLY`，Oculus 移开；加 `--exclusive` 时在独占窗口里跑，默认 8 GB 堆、4 个 DH 线程，不独占时 6 GB、3 线程，都可用 `--heap`、`--dh-threads` 改），DH 只用已保存的区块重建这些段并处理上层，结果导出成 `WORK/out/geofront_lod.sqlite`，打包时用 `--geofront-lod` 传进去。服务端包里那份照旧调早一天。主世界远景库没变，照旧从正式世界取。

2026-11-13 00:20 的演练结果（第 448 批之前的世界，外圈烘到 29%）：删 83,779 行（变动 1,172、外圈 80,965、边缘 1,642），从外圈取 12,895 行，合并后 20,195 行，打标 792 行，完整性检查 ok，仍是 WAL 模式。要重建 1,999 个 level-0 段，4 个视点：(-160,160) 1,439 段、(2656,-224) 452 段、(-2784,608) 96 段、(288,2784) 12 段。

2026-11-13 00:47–01:23 的试跑（不持锁镜像，只跑第一个视点 16 分钟，4 线程、-Xmx6G）：
- 模组正常加载，脚本跑完。
- **上层重建成立**：删掉的 7–9 层由 DH 重建回来（各 4 行），打标行从 828 降到 24。
- 核心缺段 1,172 → 709。视点范围内 1,433 段补了 801 段，但越近的越少：开局两分钟 DH 线程 15 次堆内存溢出，最先处理的近处任务丢了。主会话 2026-11-13 定了：最终重烘在独占窗口里用 R62 验证过的 8 GB 堆、4 线程（`--exclusive` 的默认）；6 GB 的规矩是为了两个共享客户端能同时放下，独占时不适用。不独占时退回 6 GB、3 线程。
- 第一次试跑客户端一分钟就退了：探针 jar 漏了内部类。现在探针类整套从 map-edges 的 jar 取，客户端日志里必须看到 `Project SEELE initialized`、没有坏模组的行才算过。

## 第 455 批的镜像（2026-11-13 06:48–06:52）

主会话说计划内的写入全部完成，正式世界停在第 455 批（449–455：学校和 B17 的陡坎、H02、17 个高架桥墩、路面带、A10 坡、R1 最后的连接路和断头）。负责人上午游戏内验收后如果再下修补单，从“镜像”一步重来。

- 开镜像前确认没人打开正式世界：`session.lock` 能拿到锁；所有 java/javaw 的命令行里都没有正式世界或主客户端目录。当时在跑的两个客户端分别是 map-edges 的 E 盘副本和 Fable 的 `motion-work/review_client`，其余三个是 gradle。
- 持锁 216 秒。80,501 个文件两边逐个 sha256 一致（清单 `E:/eva-r63-rebake/logs/manifest-MAP_REVIEW.json`）。
  - 全部文件的总哈希：`67aef5a7f507609935f43a7ca349ced61155f03009d34d6922a486c155dea678`
  - GeoFront 区域文件的总哈希：`a7a9e6612c1fe5a3d6b8e567e19ec9514e2557caf81ff9d905a4deaee8b94c65`
  - 最新区域文件时间 2026-11-13 06:41:52；批次表（`docs/HAKONE_EXECUTION_ORDER_20261105.zh.md`）最大是 455。`continuation.json` 的 `latest_installed_batch` 还停在 334，不能用来判断批次。
- prepare：变动区块 9,828，删 83,801 行（变动 1,194、外圈 80,965、边缘 1,642），从外圈取 45,267 行，合并后 52,415 行（601 MB），integrity ok，打标 2,036 行。要重建 1,376 段，3 个视点：(160,544) 1,081 段、(4384,544) 289 段、(-3040,-736) 6 段。

打包检查（06:58，`--compare-build` 用这个工作树在 main b5ef09c1 上编的 jar，模板是交付目录里 R62 的两个包）：
- 主客户端 jar（06:50 装）2,136 个类，和 main b5ef09c1 的编译结果 0 处不同；sha256 `1c5fef6adf0e3781e306cae497a488c197093d478f15cd9e4a898ccaf0557cfd`。Fable 的 R63 代码再合进来、装机以后，这一项要重跑。
- 服务端 mod 20 个，含 MTR 和 TrafficCraft；配置和默认值没有不同，只缺两个 `shadows.*` 新键（首次启动写 64、128）。
- 未压缩大小：服务端 2.80 GB，客户端 1.47 GB（GeoFront 远景库 601 MB，合并后、核心重烘之前）。
- 唯一的失败：小地图还是 11-10 烘的，比世界旧。

小地图（07:00–07:11，普通槽位，自己的镜像 `R63_XAERO`，持锁 295 秒，全部文件总哈希同上）：烘完 133 个区域 zip（R62 是 191，少的是删掉的外圈），在 `E:/eva-r63-rebake/out/xaero/projectseele$geofront`。换上它再跑 `--check`：0 处失败。世界再写就要重烘。

所以第 455 批时打包还差：外圈烘完后的 `instance`、`mirror`、`prepare`，然后独占窗口里的 `core`；Fable 的 R63 代码装机后重跑一次 `--check`（jar 比对）。

### 烘焙客户端用的 jar（2026-11-13 07:15–07:33）

主会话要求 DH 烘焙客户端不用 415 MB 的私有 jar：私有 jar 里 821 MB 的零号机原型模型（`mesh/eva_prototype.mesh.json`）启动就读进堆，Fable 量到光它就占约 5.5 GB；map-edges 06:26 那次服务端 OOM 也是这个原因。打包照旧用私有 jar。
- **纯公开 jar 打不开世界。** 07:17 干跑：服务端开服前 `EvaMechanicalFrameR52.prepareBeforeServerLoadR52` 要读三台机体的私有模型、手部模型和 GEO，公开 jar 里没有 `mesh/eva_unit00.mesh.json`，世界载入前崩溃（`crash-2026-11-13_07.17.36-server.txt`）。
- map-edges 07:30 用公开 jar 也一样崩（`E:/eva-map-edges/client/crash-reports/crash-2026-11-13_07.30.18-server.txt`）。**主会话随后收回了这条要求：`core` 用打包的那份私有 jar**（和 main b5ef09c1 的类一致，sha256 `1c5fef6a…7cfd`），在 8 GB 独占窗口里没有别的进程，原型模型放得下。`instance` 默认就这样做：`jars/probe.jar` = 打包 jar + 探针类。
- 备选 `instance --slim-bake`：把打包 jar 里只给客户端渲染器用的 `eva_prototype.mesh.json` 换成公开构建（`--bake-jar`）里 26 MB 的占位版，其余 3,322 个条目逐个 CRC 核对一致，jar 从 415 MB 降到 325 MB。07:28–07:33 用它干跑通过（6 GB、3 线程，进入世界、DH 启动、正常退出，没有崩溃、内存溢出或缺方块）。只在 8 GB 也不够时才用。
- 干跑用过镜像里的远景库，所以 `core` 之前照原计划重跑 `mirror` 和 `prepare`。

## 开始之前

- [ ] 地图会话说最后一批写完了。批次以 `docs/HAKONE_EXECUTION_ORDER_20261105.zh.md` 的批次表为准，`mirror --batch N` 会核对。之后任何一次写入都要从“镜像”重来；`core` 发现正式世界的区域文件在镜像之后变过会拒绝。
- [ ] map-edges 的外圈烘焙停了（`loop.sh` 那个文件夹里放 `STOP`，或者等它自己结束），它的客户端已经退出。没烘完也可以打，覆盖率会写进说明（见“卡点”）。
- [ ] 要进 R63 的分支都合进 main 并装进主客户端（`client/mods/projectseele-0.1.0-all.jar`）。拿 main 编一个 jar 给 `--compare-build` 比对：`slot.py status` 没有别人的 exclusive 时，在这个工作树里 `./gradlew build`。
- [ ] `frpy F:/eva/.claude/client-slots/slot.py status`：没有别人的 exclusive。
- [ ] F 盘至少 10 GB 空闲，E 盘至少 15 GB 空闲。

## 步骤

| # | 命令 | 时间 | 看什么 |
|---|---|---|---|
| 1 | `frpy tools/rebake_r63.py check` | 20 秒 | `problems` 为空；记下变动区块数、视点、外圈覆盖率、估时和磁盘 |
| 2 | `frpy tools/rebake_r63.py instance` | 1 分钟 | 把主客户端（不含存档、日志、旧小地图）复制到 `E:/eva-r63-rebake/client`，0.77 GB；DH 配置改成烘焙用，静音；`jars/` 里有最终 jar 和加了探针类的最终 jar（`--slim-bake` 时改用去掉原型模型的瘦身 jar） |
| 3 | `frpy tools/rebake_r63.py mirror --batch <批次>` | 约 4 分钟（持锁复制再两边算哈希） | 期间持有正式世界的 `session.lock`，地图会话的写入会等；全部文件 sha256 一致；把两个总哈希抄进本清单 |
| 4 | `frpy tools/rebake_r63.py prepare` | 1 分钟 | `integrity` = ok；`world_unchanged_since_mirror` = true；删/取/打标数目和上次同一量级；视点和分钟数 |
| 5 | `frpy tools/rebake_r63.py core --exclusive`（8 GB、4 线程；`slot.py exclusive r63-pack` 会等别的客户端退出） | 30–40 分钟，缺得多时再加 15–25 分钟的补烘 | 先拿到 slot 的 `ok:` 才启动；`ok` = true：模组加载成功、脚本跑完、quick_check ok、核心缺段不超过 50；`pending_parent_updates` 接近 0；`out_of_memory` 应为 0 |
| 6 | `frpy tools/rebake_r63.py xaero` | 约 12 分钟 | 不用独占，普通槽位就行；用自己的镜像 `saves/R63_XAERO`，不会冲掉第 4 步的结果；日志有 `Xaero map bake finished`，区域 zip 数和 R62 的 191 差不多（外圈删掉后可能更少） |

**第 2–4 步要在第 5 步之前紧挨着重跑一遍**，因为：`instance` 要拿主客户端里最新装的 jar（Fable 的代码合进来、装机之后）；`prepare` 要在 map-edges 烘完之后重新快照外圈库；`mirror` 会把镜像里的远景库还原成正式世界那份，所以 `prepare` 必须跟在它后面。这三步都不用独占，合计约 6 分钟。第 6 步只依赖世界，世界不再写之后什么时候跑都行。
| 7 | `frpy tools/rebake_r63.py report` | — | 打印打包命令 |
| 8 | `frpy tools/package_r60.py --check <报告路径> --geofront-lod E:/eva-r63-rebake/out/geofront_lod.sqlite --xaero-map "E:/eva-r63-rebake/out/xaero/projectseele$geofront" --compare-build <main 编出的 -all.jar> --server-address <服务器地址>` | 1 分钟 | `check_failures` 为空。配置检查只应报两个新键（`shadows.*`，首次启动自动写默认值 64 和 128） |
| 9 | 填好 `docs/R63_RELEASE.zh.md` 的空格并删掉“打包前确认”一节，提交 | — | |
| 10 | 同一条命令把 `--check <报告>` 换成 `--pack --date YYYYMMDD --map-note "<一行地图状态>"` | 3 分钟 | 两个 zip 写完并逐个校验 CRC；回执 `delivery/R63_<日期>_receipt.json` |
| 11 | 本机专用服务器进服测试（R62 的做法：服务器启动、小地图区域数、远景加载完的秒数、有没有 override 警告） | 15 分钟 | 回执和测试结果写进 `docs/RELEASE_LOG.zh.md` |

服务器地址只在命令行里给，不写进仓库。打包时世界要停着，打包工具会持锁检查。

## 时间和磁盘

- 槽位空着时，第 1–10 步合计约 1.5–2 小时，大头是第 5 步的客户端。
- **第 5 步要的独占窗口：申请 75 分钟。** 按第 455 批的计划，3 个视点悬停 16 + 6 + 6 分钟，加上启动约 4 分钟，约 32 分钟（视点悬停按每分钟 80 段估：试跑在 6 GB 下溢出时约 50 段/分钟，R62 在 8 GB、6 线程时约 170）。缺段超过 50 时自动补烘，最多 8 个视点，按现在的规模一般 1–3 个，再加 15–25 分钟。`slot.py exclusive` 还要先等正在跑的客户端退出，这段时间不算在内。
- 外圈：2026-11-13 00:20 还差 22,584 个 level-0 段；06:45 主会话说还差约 7,700 段（共 39,160）。map-edges 实测约 63 段/分钟。
- E 盘：工作目录约 6 GB（客户端 0.77 GB、世界镜像 1.6 GB、外圈快照和导出的远景库各约 0.3–1 GB）。
- F 盘：两个 zip。R62 是 0.95 GB 和 2.0 GB；R63 的 GeoFront 远景库现在 0.30 GB，外圈烘满后估计 0.7–1 GB，客户端包会到约 1.4 GB、服务端包约 2.6 GB，再加打包时的临时副本，留 10 GB。
- 2026-11-13 00:20 实测空闲：F 盘 50 GB，E 盘 53 GB；06:53 再测：F 盘 31 GB，E 盘 48 GB（第 455 批合并后的 GeoFront 远景库已经 601 MB，外圈烘满后还会再大）。

## 卡点和没验证的

- **外圈没烘完。** 要么等 map-edges 烘完，要么按当时的覆盖率打包，说明里写明“没烘到的要走近才出现”。这个由主会话或负责人定。
- **内存。** 6 GB 堆配 4 个 DH 线程会溢出，近处的段会漏（试跑实测）。最终重烘用 `--exclusive`（8 GB、4 线程）；不独占时默认 6 GB、3 线程。第 5 步结束看 `out_of_memory`，不为 0 时缺段多半要靠补烘。
- **上层重建在试跑里验证过**（打标 828 → 24，7–9 层重建回来）。剩下的少量标记服务器第一次启动时 DH 也会处理。
- **边缘段的取舍是近似的。** 边缘 level-0 行优先用外圈库里的（第 415 批的核心边缘 + 新边界）；只要其中有区块在 R62 之后变过，就改由第 5 步从已保存区块重建，这样不会带回旧内容，但边缘段里外圈那一半会空着，直到玩家走近。
- **探针类。** 第 5 步从 map-edges 烘外圈用的 jar（`E:/eva-map-edges/client/mods/`）取 `MapProbeLocal` 和它的内部类（只在本机，不进仓库），加进烘焙 jar。它的 `tp` 等满 1200 刻就超时，所以悬停用 `cmd` 步骤等待，和 map-edges 一样。map-edges 收工删副本前，先跑一次 `instance`，`jars/probe.jar` 就留在工作目录里了。
- **第 5、6 步要客户端槽位。** 夜里两个槽位常被占满，`acquire` 会排队等。

## 读正式世界的远景库

SQLite 就算用 `mode=ro` 只读打开 WAL 模式的库，也会在旁边建 `-wal` 和 `-shm` 两个文件。两个工具读正式世界的远景库时一律用 `immutable=1`，什么都不建；只有 map-edges 那份正在被它的客户端写的库、以及烘焙客户端刚写完的库才按普通只读打开（它们都不在正式世界里）。别的脚本要读正式世界的远景库，也照这样做。

2026-11-13 演练时我先用 `mode=ro` 读过，正式世界里因此多了：GeoFront `data/` 下一个空的 `DistantHorizons.sqlite-wal`（0 字节，00:06）和 32 KB 的 `-shm`（00:15），主世界 `data/` 下的 `-shm` 时间刷新到 00:24。库文件本身没变（大小、修改时间仍是 11-10 06:53 和 11-01 20:19）。空 WAL 没有要合并的内容，DH 下次打开会照常使用；打包工具只拒绝非空的 WAL。要不要删由地图会话在停写时决定。

## 相关文件

- 外圈烘焙进度：共享笔记 `map-edges-dh-outer-bake-handover-20261111.md`，工具在 `F:/eva/.claude/map-edges-work/f12bake/`。
- R62 的远景和小地图流程：`F:/eva/.claude/worktrees/map-bdb53d/.claude/dhjob/driver4.sh`，以及 `F:/eva/.claude/motion-work/agent-render/HANDOFF_20261109.md`（小地图只认区域 zip、服务端远景要调早、客户端 4 线程）。
- 每一步的结果：`E:/eva-r63-rebake/logs/<步骤>.json`。
