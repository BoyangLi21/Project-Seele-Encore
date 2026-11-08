# 道路换用 TrafficCraft（本轮验收前）

负责人 2026-11-08 决定：现在的道路长得太差，很多方块不合理，用最通用、最成熟的道路 mod，让路面平整、合理。选定 TrafficCraft，本轮验收前换完。

## 为什么选它

- 在 Modrinth 上，Forge 1.20.1 能用的专门铺路 mod 里它下载最多（17.6 万次）。2023-11 发布，一直在更新，Forge、Fabric、NeoForge 都有。
- 许可是 GPL-3.0-or-later，可以随整合包分发，附上许可证和源码链接即可。对比：Saro's Road Blocks（6 万次）和 City Craft 是 All Rights Reserved，不能放进我们的包；Roads 'n' Vehicles 在 Forge 上要靠 Sinytra Connector；Ruhuna's Road 只有 154 次下载。
- 方块够用：8 层沥青（`asphalt_slope`），324 种标线（细线、双线、宽带、箭头、字母、数字），路缘，混凝土人行道，排水口，井盖，护栏，反光柱，路灯，红绿灯，标志牌。
- 标线的颜色由 BlockColor 着色，直接画进区块网格，不走逐帧渲染器，所以标线再多也不额外掉帧。只有红绿灯和各种标志牌有逐帧渲染器。

## 版本和安装

- 用 `trafficcraft-forge-1.20.1-1.1.3.jar`：6,030,955 字节，SHA-1 `b5793501c821591019d537f9eb3809227cd7738f`，来自 [Modrinth](https://modrinth.com/mod/trafficcraft/version/ARucrtsU)。这是 2025-01-04 发布的最新正式版；1.2.0 还是 beta，先不用。
- jar 里已经嵌了 DragonLib 1.20.1-2.2.24 和 Architectury 9.1.12，只装这一个文件。
- 本机存放在 `external-assets/incoming/trafficcraft_20261108/`，不进仓库。同目录的 `pattern_sheet.png` 是 324 种标线的编号图。
- 2026-11-08 在装了全套 mod 的评审客户端里实测：能进世界，巡检 320 tick 跑完，正常退出。新增的报错只有一条：`trafficcraft:plants` 标签引用了 1.20.2 才有的 `#minecraft:replaceable_plants`。它只影响铺路工具会替换哪些植物，不碍事。
- 主客户端 `artifacts/r53_repair_20261015/client/mods` 已于 2026-11-08 装好。

## 硬规则：先装 mod，再写方块

1. 正式存档写入第一个 `trafficcraft:` 方块之前，所有会打开它的实例都要先装好这个 jar：主客户端、地图会话的测试客户端、map-roads 和 map-edges 的测试客户端，以及 R60 的客户端包和服务端包。
2. 没装的实例打开正式存档时，Forge 会提示缺少方块。这时如果继续进入，路面会被清成空气，存档一保存就再也找不回来。出现这个提示一律退出，不要点继续。
3. 联机时客户端和服务端都必须装。

## 怎么换

### 路面高度改成 1/8 格

- 现在：`grade2` 是半格台阶，路面用整块黑混凝土或半砖。
- 改成：按 1/8 格取整，`h8 = rint(8 × 路面高度)`。整数部分用 `trafficcraft:asphalt`；余下的 k = 1..7 层，用 `trafficcraft:asphalt_slope[layers=k]` 放在最上面，下面垫整块（沥青，或者原来的石头路基）。
- 沿路方向，相邻两格最多差 2 层，也就是 25%，和现有的 `maximum_grade` 0.25 一致。横断面上同一排一样高。
- `corridors` 生成的路，用对位曲线的连续高度重新取整。其他老路先沿路方向把半格台阶抹平，再取整。路口、站前广场和建筑入口要和相接的地面对齐。
- 车辆净空仍然是 5 格，从新路面算起。

### 人行道

- 用 `trafficcraft:concrete` 加 `trafficcraft:concrete_slope[layers=k]`，比旁边的车道高 1 层（12.5 厘米，接近日本常见的 15 厘米路缘）。人行道整条跟着车道一起起伏，不再出现半格高的“路缘墙”。
- 车道最外一列可以换成 `trafficcraft:asphalt_curb`（坡上用 `asphalt_curb_slope`），`facing` 朝人行道，画出路缘石。它只是贴图，不会把方块抬高。

### 标线（按日本规则简化）

- 标线方块：整块用 `trafficcraft:asphalt_pattern_<N>[facing=…]`，带层的用 `trafficcraft:asphalt_slope_pattern_<N>[facing=…,layers=k]`。
- 颜色存在方块实体里：`{id:"trafficcraft:colored_block_entity", x, y, z, color:<int>}`。白色是 0，黄色是 4。完整顺序：白 0、橙 1、品红 2、淡蓝 3、黄 4、黄绿 5、粉 6、灰 7、淡灰 8、青 9、紫 10、蓝 11、棕 12、绿 13、红 14、黑 15。
- 每个标线方块都要一起写方块实体。不写的话，颜色不对。
- 方向：`facing=north` 时，纹理的上边朝北；`east`、`south`、`west` 依次顺时针转 90°。纹理里的竖线在 `north` 和 `south` 时沿南北走，在 `east` 和 `west` 时沿东西走。

常用图案（纹理 16×16 像素，1 像素约 6 厘米）：

| 用途 | 图案 | 形状 |
|---|---:|---|
| 实线、虚线 | 1 | 居中一条 4 像素宽的线（25 厘米） |
| 车道外侧线 | 23 | 第 9–12 像素的偏线；`facing=north` 时靠东，用 `facing` 把线转到靠路缘的一侧 |
| 双线 | 54 | 两条 4 像素线，中间隔 2 像素 |
| 斑马线 | 108 | 10 像素宽的带（62.5 厘米），一格挨一格排开，就成了条和间隔 |
| 细双线 | 162 | 两条 2 像素线 |
| 转角、分流合流、箭头、字母数字 | 2–53、243–258、261–296 | 对照编号图 |

画法：
- 双车道山路（国道 1 号、138 号这类坡多弯多的路）：中心画黄色实线（图案 1，颜色 4）。
- 市区双车道：中心画白色虚线（图案 1，白色），画 5 格空 5 格。
- 多车道：车道分界画白色虚线，画 5 格空 5 格；中心画白色实线，或者用双线（54）。
- 有人行道或路肩的路，画白色车道外侧线（23）。
- 停止线：路口前横跨本方向的车道，白色，用图案 1 横着放。
- 斑马线：画在路口和车站前，横跨整个车道，沿路方向长 4 格，用 108，条纹顺着车流方向。
- 路宽不到 4 格的小路不画中心线。
- 箭头和文字这次先不做。

### 附属物（可选，放在后面做）

- 山路有落差的外侧放 `trafficcraft:guardrail`，弯道外侧加反光柱（`white_delineator`）。
- 路边隔一段放排水口 `road_gully`，路中偶尔放井盖 `manhole_cover`，当点缀。
- 现有的隐形光源 `minecraft:light` 保留。要不要换成看得见的路灯另议。

### 不变的部分

- 我们自己的 `projectseele:road_asphalt_slab` 和 `road_marking_slab` 继续注册（老存档还在用），地图换完以后不再新写。
- 路基、桥和隧道衬砌的石头、石砖不变。

## 验证

1. 先在存档副本里写一段样例：直线、坡道（每格升 1 层和升 2 层两种）、弯道、带停止线和斑马线的路口、人行道。用测试客户端截图，检查标线颜色和朝向、坡道是否连续、人行道高差。
2. 全图换完后：沿主要道路巡检截图；逐个核对标线方块都有方块实体，`color` 也对；搜一遍路面上残留的 `black_concrete`、`white_concrete`、`smooth_stone` 和 `road_*_slab`。
3. 写正式存档之前，按“先装 mod，再写方块”那一节逐项确认。

## 分工

- 地图会话（map）是正式存档唯一的写入者：负责转换工具、样例和写入批次，并把这些任务加进 `docs/hakone_progress.json`。
- map-roads 手上的 55 段连接路照常写。转换工具最后会把所有路统一过一遍；工具做好以后，新写的路直接用新方块。
- 总控负责选 mod、往主客户端装 jar，以及打包规则。

## 发布

- R60 的客户端包和服务端包都要带这个 jar。`licenses/` 里放 GPL-3.0 全文，并附源码链接：<https://github.com/MisterJulsen/TrafficCraft>。
- 素材登记见 [ASSETS.md](ASSETS.md)，打包规则见 [RELEASE_LOG.zh.md](RELEASE_LOG.zh.md)。
