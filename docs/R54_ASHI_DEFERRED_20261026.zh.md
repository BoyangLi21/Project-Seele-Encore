# 芦之湖与新增道路：用户要求下轮继续，未安装

> 2026-10-29：用户已授权继续。旧椭圆湖候选没有安装；已重新阅读现实官方地图，改用弯曲湖岸与东岸接驳方案并安装到实际存档。当前结果见 [R55 地图后续](R55_MAP_FOLLOWUP_20261029.zh.md)。以下保留旧候选历史。

2026-10-26 用户明确要求新道路与芦之湖留到下一轮，当前先提供可正常测试的包。本候选停止后续工作，不属于本轮交付；已安装城市、箱根站及山肩不回滚。

候选工具为 `tools/plan_ashi_landscape_r54.py`。未安装的逐格 forward/inverse、地点草案和地形数组保留在 `F:/eva/artifacts/r54_update_20261026/ashi_surface/`，最终写出 2,759,391 格。没有写存档、NPC、玩家、任务或交通数据，也没有接入运行时生成器。此候选未做原生通行、视觉复核或用户验收；下轮须继续完成道路/支承/岸边验证，不能直接标记可发布。

已核对现状：`regional_plan.json` 没有芦之湖、仙石原、金时山或汤本的地理对象；原新箱根是项目原创区域，车站借鉴汤本功能和外观不构成真实汤本定位。`TvWorldPreviewTerrain.lakeDistance` 控制的是 Y=-473 的地下湖，不是地表芦之湖。

地理来源：[国土地理院箱根登山道调查](https://www.gsi.go.jp/kihonjohochousa/kihonjohochousa40038.html)、[箱根官方登山地图](https://www.hakone.or.jp/files/AddB016_2025060916211130996.pdf)、[箱根地质公园地图](https://www.hakone-geopark.jp/global-image/units/upfiles/20016-1-20260331202209_b69cbae61d46a1.pdf)。参考关系是金时山在仙石原北侧、湖在南侧、汤本在东侧山谷；候选保留既有原创城市布局，不能声称真实一比一映射。

独立交付的空运预取修复：保持 duration、五次缓动速度、原 readyAt 与碰撞规则。连续未来20tick区间每≤16m一张radius1票据，实际未来tick根位置用radius2票据；5tick刷新、15tick TTL。有限算法验证含0/20/4800/8000/12000/40000m与5种方向，6325次下一刷新前位置及3×3 FULL覆盖通过；独立预取最大并集1181 FULL、36 entity-ticking（不含玩家、现有readyAt及其他系统票据）。报告在 `air_prefetch/logic.json`。尚未宣称实机冷路性能通过，由主代理统一构建与实测。
