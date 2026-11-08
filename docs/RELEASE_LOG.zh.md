# 发布记录

每次打包后在这里加一行，并写明回执位置。

| 版本 | 日期 | 状态 | 客户端包 | 服务端包 | 记录 |
|---|---|---|---:|---:|---|
| R54 fix2 | 2026-10-28 | 旧版 | 929 MB | 1,294 MB | `delivery/R54_20261028_fix2_DELIVERY_RECEIPT.json` |
| R55 | 2026-10-29 | 上一版，保留 | 945 MB | 1,328 MB | `delivery/R55_20261029_receipt.json`，[说明](R55_RELEASE.zh.md)，[快速开始](R55_QUICKSTART.zh.md) |
| R60 | 2026-11-08 | 朋友小测试包，地图未完工 | 904 MB | 1,891 MB | `delivery/R60_20261108_receipt.json`，[说明](R60_RELEASE.zh.md)，[快速开始](R60_QUICKSTART.zh.md) |

版本号从 R55 直接到 R60。R56–R59 是开发轮次，没有发布过。

## R60 打包规则

**格式沿用 R55：**
- `delivery/Project_SEELE_Encore_R60_<日期>_Client_PCL.zip`：PCL 整合包，`manifest.json` 加 `overrides/`，实例名 `EVANGELION_Encore_R60`，不含存档。
- `delivery/Project_SEELE_Encore_R60_<日期>_Server.zip`：服务端和世界。
- 随包放 `R60_QUICKSTART.zh.md`、`R60_RELEASE.zh.md`、`R60_BATCH.json`，以及 JIT 指令文件 `jit-recovery-r54.json`。
- 回执写到 `delivery/R60_<日期>_receipt.json`。
- R55 的两个包不动。
- 打包时世界必须已正常保存并停止，打包工具会检查。

**打包工具：** `tools/package_r60.py`。默认只列清单，加 `--pack` 才写 zip，写完逐个校验 CRC。服务端启动文件、`server.properties`、图标和 PCL 清单取自 R55 的两个包。

**联机：** 清理删掉了一批网络包，R60 客户端连不上 R55 服务器，两边必须一起发。

**jar：** 用 `client/mods` 里的完整 jar，不要用 `build/libs` 的公开构建，后者没有私有模型和贴图。

**道路 mod：** R60 地图的道路用 TrafficCraft 1.1.3 的方块，客户端包和服务端包都必须带 `trafficcraft-forge-1.20.1-1.1.3.jar`（本机在 `external-assets/incoming/trafficcraft_20261108/`），`licenses/` 里放 GPL-3.0 全文和源码链接。少了它，进世界后路面会变成空气。见 [道路换用计划](ROAD_TRAFFICCRAFT_PLAN.zh.md)。

## 齐全检查

客户端包打完后在干净实例里验证：
- mod、`projectseele-local-maps`、资源包、光影、配置和 `licenses/` 都在，PCL 实例设置带 JIT 指令。
- 能连上同版本服务器，进世界后 EVA、使徒、NPC、武器和车站模型都能显示，没有缺贴图。
- 远景能加载，第 7 项修掉的 Distant Horizons 假墙没有带回来。
- 道路标线有颜色，坡道是连续的 1/8 格，没有出现缺方块的提示。

## 客户端减重

目标是齐全的前提下尽量小。下表是 R55 客户端 945 MB 的构成：

| 部分 | 大小 | 说明 |
|---|---:|---|
| `projectseele-0.1.0-all.jar` | 410 MB | 贴图 213 MB，网格 165 MB（解压后 1.4 GB） |
| Distant Horizons 预生成远景 | 284 MB | GeoFront 247 MB，主世界 37 MB；R60 地图更大，这项会变大 |
| 其他 mod | 200 MB | MTR 85 MB，superbwarfare 42 MB，Create 19 MB，DH 18 MB，Ars Nouveau 12 MB |
| 资源包 | 71 MB | 地形贴图 |
| `projectseele-local-maps` | 24 MB | 解压后 97 MB |

可以试的方向，每项都要做齐全检查：
1. 贴图：162 张 PNG 占 213 MB，单张最大 14.5 MB。先查有没有用不到的，再无损压缩，最后才考虑降分辨率。
2. 网格：`eva_prototype.mesh.json` 解压后 860 MB，压缩后 92 MB，占网格的一半以上。改成二进制格式还能缩短加载时间。
3. jar 和 zip 的压缩级别：现在是 3，非媒体文件改高级别。
4. 远景：只预生成玩家常去的区域，其余让客户端自己生成。

## 发布前待办

- 把新包的链接发给 Audijon2，告诉他 NERV 总部地图的来源和署名。草稿在 [开放准备文档](OPEN_SOURCE_RELEASE_R24.md)。
- 在地图合适的位置给 Audijon2 做一个致敬，位置由负责人定。
- 第 7 项修掉假墙后再打包，地图验收通过前不发。
- `R60_QUICKSTART.zh.md` 写明：地图的道路需要 TrafficCraft，包里已经带了；把世界搬进自己装的实例时，先放好这个 jar 再打开存档，遇到缺方块的提示一律退出，不要继续。
