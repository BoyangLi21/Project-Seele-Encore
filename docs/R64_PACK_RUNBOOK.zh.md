# R64 打包流程（2026-11-15 干跑后写）

工具在分支 `claude/r64-pack-prep`（385c7ea3）：`tools/package_r60.py`（R64）、`tools/rebake_r63.py`、`tools/dh_v6_prepare.py`、`tools/gen_green_grass_side.py`。所有 Python 用 `F:/eva/.claude/fable-review/pyfr/Scripts/frpy.exe -I` 跑；设 `JAVA_HOME=E:\Users\liboy\jdks\jdk-17.0.19+10`。工作目录 `WORK = E:/eva-r64-rebake`（每条命令加 `--work E:/eva-r64-rebake`）。开客户端的步骤先看 `slot.py status`，按规矩拿槽位。

## 前提

- 世界最后一批写完，记下批次号 N；代码定在 main 的某个提交，并已装进主客户端（`F:/eva/artifacts/r53_repair_20261015/client/mods`）。`--compare-build` 用同一提交的构建。
- **R63r 的两个 zip 要留到 R64 打完**：服务端 zip 是变动比对的基准，也是远景的起点；两个 zip 都是 `--template`。R63 原包可以删。
- 磁盘：E 盘至少 15 GB 空（WORK 峰值约 10 GB，加 map-edges 外圈库增长）；F 盘至少 8 GB（两个 zip 约 1.8 + 3.0 GB，加约 1.2 GB 临时远景库副本）。

## 步骤

| # | 做什么 | 命令 | 时间 | 磁盘 |
|---|---|---|---|---|
| 1 | 只读检查：世界锁、Java、变动区块、估时 | `tools/rebake_r63.py check` | 1 分钟 | — |
| 2 | **外圈远景重烘（用 R64 的生成器）** | map-edges 的 `f12bake/batch.sh`，在它的 E 盘副本上换成 R64 jar，四边加核心整圈重跑；结果就是 `--ring-db` | 约 10.5 小时客户端（39,160 段，63 段/分钟，4 个 DH 线程） | map-edges 副本库约 +30%（LZ4） |
| 3 | 烘焙实例 | `tools/rebake_r63.py instance` | 2 分钟 | E 0.8 GB |
| 4 | 镜像正式世界（持锁） | `tools/rebake_r63.py mirror --batch N` | 8 分钟 | E 1.6 GB |
| 5 | 远景起点换成 R63r 的 | 从 R63r 服务端 zip 取 `SEELE_R53_WORLD/dimensions/projectseele/geofront/data/DistantHorizons.sqlite`，覆盖 `WORK/client/saves/MAP_REVIEW/dimensions/projectseele/geofront/data/DistantHorizons.sqlite` | 1 分钟 | E 0.9 GB |
| 6 | 合并外圈、删变动行 | `tools/rebake_r63.py prepare --ring-db <第 2 步的库>` | 3 分钟 | — |
| 7 | V6：远处也能重建 | `tools/dh_v6_prepare.py WORK/client/saves/MAP_REVIEW/dimensions/projectseele/geofront/data/DistantHorizons.sqlite WORK/lod/rebuild_sections.json`（先加 `--dry-run` 看数） | 1 分钟 | — |
| 8 | 核心远景重烘（独占，8 GB，4 线程，LZ4） | `tools/rebake_r63.py core --exclusive` | 约 55 分钟，缺段多时补烘再加 ≤25 分钟 | E 输出约 1.2 GB |
| 9 | 小地图：先预生成外圈，再烘地表和完整洞穴层 | `tools/rebake_r63.py xaero --exclusive --xaero-pregen -6464,-5408,7584,5920` | 预生成约 4.1 小时（约 62 万区块，42 个/秒）+ 烘焙约 10 分钟 | E 镜像 1.6 GB + 预生成 3 GB |
| 10 | 生成打包命令 | `tools/rebake_r63.py report` | — | — |
| 11 | 打包检查（必须 0 处失败） | `tools/package_r60.py --check <报告> --geofront-lod WORK/out/geofront_lod.sqlite --xaero-map <report 给的路径> --compare-build <main 构建 jar>` | 1 分钟 | — |
| 12 | 打包 | 同上把 `--check <报告>` 换成 `--pack --date YYYYMMDD --map-note "<一行地图说明>" --server-address <地址>` | 5 分钟 | F 峰值约 6 GB |
| 13 | 本机专用服务器进服测试 | 解压服务端包，`Start-Server.bat`；客户端用打出的 PCL 包 | 15 分钟 | E 约 3 GB |

合计：客户端约 16.5 小时（外圈 10.5 + 小地图预生成 4.1 + 核心 1.3 + 其他 0.6）。第 2 步和第 9 步的预生成都只占普通槽位时可以同时跑（两个客户端，各 6–8 GB），墙钟约 12 小时。第 9 步要用第 4 步之后的世界，第 6 步要等第 2 步完成。

## 打包工具自动做的（R64 新增）

- 客户端和服务端的 DH 配置都写 `dataCompression = "LZ4"`。烘焙时新写的远景行也是 LZ4；从 R63r 留下没重建的行仍是 LZMA2，能正常读。
- 服务端世界里的 `serverconfig/superbwarfare-server.toml` 打包时改成 `vehicle_chunk_loading = false`（找不到这个键就报错）。正式世界本身不改。
- 绿色草边资源包由 `tools/gen_green_grass_side.py` 现场生成，放进客户端包，并在 `options.txt` 的资源包列表最后启用（在 PBRJG 地形包上面）。
- 服务端带 Xaero 内嵌的 `xaerolib`；GeoFront 小地图带 `dimension_config.txt`（`caveModeType:2`）。
- 说明文件用 `docs/R64_QUICKSTART.zh.md`、`docs/R64_RELEASE.zh.md`（后者是草稿，打包前要定稿）。

## 2026-11-15 干跑结果

- 打包检查（main 9ae55f64 + 正式世界只读，模板 R63r）：只剩 2 处失败，都是还没烘的东西：`--geofront-lod`、`--xaero-map`。主客户端装的 jar 和 main 的构建逐类相同；R64 标志类都在。
- 生成的包内容（直接调用打包工具查看）：两边 DH 都是 LZ4；服务端世界的 SuperbWarfare 配置为 false；客户端 options 启用草边包，草边包和 R63r 的字节相同。
- 烘焙检查：世界锁空闲，Java 17.0.19；从第 455 批到现在 45,469 个 GeoFront 区块变了。
- 第 5–7 步在副本上试算（R63r 的远景库，外圈库为空）：删 72,644 行（其中 R63 的旧外圈 66,475 行），要重建 5,371 个 level-0 段，4 个视点，约 55 分钟；V6 再删 1,654 个上级、标 1,918 个子段。
