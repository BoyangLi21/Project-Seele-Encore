# R50 第40项地表修复记录

2026-10-06。Root已把下列物理组件及完整生成源安装到两份实际存档：施工源 `D:/eva/artifacts/rebuild_r49/construction/SEELE_R49_WORLD`，以及同一原生QA副本 `D:/eva/artifacts/rebuild_r49/native_qa/worlds/SEELE_R49_QA`。工作目录名仍沿用 `rebuild_r49`，本记录属于未发布R50施工。

第40项本轮已完成的成果是：清理确定退役的原构件、恢复有限地表低列和现铁路侧床、重塑两处有限山肩、保留有真实用途的桥梁与船体开口，并把相同完整声明同步到生成模板。**5,497个Heightmap筛查对象没有全部完成设施功能或美术验收。** 本文以实际安装回执和已保存测量为依据，没有重新扫描世界或启动游戏。

## 已安装的完整组件

| 组件 | 修前问题与判据 | 本轮物理修改 | 完整模板声明 |
|---|---|---:|---:|
| 73个原C1退役构件 | 原完整创建源489个组件中，55个仍有外露残构件；另17个埋入当前土岩、1个外露且无后来承载用途。按原成员逐块核对，不清理后来复用的19个构件。 | 899 + 286 = 1,185格 | 原489组件掩码5,063格；包括已经为空和后来复用的当前完整状态 |
| 两处西侧自然山肩 | 实测局部单格阶壁；有限坡面重塑保留原山峰、谷地与洞腔。高度阈值和X=-2304位置不足以证明旧R02制造了断层。 | 21,553格 | 1,365,336格，含原土岩、air及受保护的洞腔状态 |
| 70处孤立地表低列 | 每处读取实际5×5邻域及中心全列，确认自然土岩和四邻高度关系，排除水、植物、交通、固定设施与船体用途。对已测低列补连续土岩和草帽，未声称所有低列都来自历史生成bug。 | 1,203格 | 52,406格完整有限邻域 |
| 21处当前铁路侧床孔洞 | 实际当前TRAIN轴、当前床层及四邻混凝土吻合，属于孤立AIR孔洞；只恢复三层侧床。原车体空间、轨道身份、下方道路和旧构件保持。 | 63格 | 7,675格完整有限邻域 |
| 原P1公共广场复用 | 已退役站台不能自动重建；现公共地面、边栏和原基础有真实连接。保留后来改写的502格及原720格承载，补齐既有公共广场有限实体。 | 104格 | 86,342格，含既有air、公共复用、原基础和后来边栏 |
| 完整旧S2隧道及11个原墩源体积 | 扫描到的80米“低梁”是旧Y105轨道隧道的尾部，真实创建源连续327米；不是现铁路下弦梁。核真实承载后退役外露衬砌、恢复埋入土岩的材料，保留现柱接口。 | 20,083格：13,538变air，6,545恢复自然土岩 | 36,561格完整源；包括11个旧墩源体积的当前状态 |

另外，67个已记录退役掩码的 **13,128格** 当前完整状态也已进入生成源：12,988格已是air，140格为当前其它材料或公共复用。它们不能作为“又拆了67个组件”重复计入物理修改。

组件、精确before/after、完整NBT、逆补丁和正掩码分别见 [M40清单](D:/eva/artifacts/rebuild_r49/surface_r50/M40_EXACT_CANDIDATE_MANIFEST.json)、[山肩冻结索引](D:/eva/artifacts/rebuild_r49/surface_r50/terrain_interface_repairs/final_handoff_index.json)、[P1复用报告](D:/eva/artifacts/rebuild_r49/surface_r50/retired_routes_r50/P1_public_reuse_candidate_v1/report.json) 与 [S2冻结索引](D:/eva/artifacts/rebuild_r49/surface_r50/retired_routes_r50/S2_tunnel_lining_candidate_r50/final_handoff_index.json)。这些候选中的 `world_written=false` 是其准备阶段记录，实际落地状态由下面的双方安装回执证明。

## 双方实际安装回执

| 批次 | construction物理回执 | 同一QA物理回执 | 每份物理写入量 | 同步源回执 |
|---|---|---|---:|---|
| C1 + 两山肩 | [surface_01](D:/eva/artifacts/rebuild_r49/applied/r50_surface_01/components/applied_20261006_195001_860008/receipt.json) | [surface_qa_01](D:/eva/artifacts/rebuild_r49/applied/r50_surface_qa_01/components/applied_20261006_200618_870566/receipt.json) | 22,738格，107区块 | [construction源](D:/eva/artifacts/rebuild_r49/applied/r50_surface_sources_01/receipt.json)、[QA源](D:/eva/artifacts/rebuild_r49/applied/r50_surface_sources_qa_01/receipt.json)：各234文件 |
| 70低列 + 21侧床 + P1 | [surface_02](D:/eva/artifacts/rebuild_r49/applied/r50_surface_02/components/applied_20261006_202011_678371/receipt.json) | [surface_qa_02](D:/eva/artifacts/rebuild_r49/applied/r50_surface_qa_02/components/applied_20261006_202109_448057/receipt.json) | 1,370格，84区块 | [construction源](D:/eva/artifacts/rebuild_r49/applied/r50_surface_sources_02/receipt.json)、[QA源](D:/eva/artifacts/rebuild_r49/applied/r50_surface_sources_qa_02/receipt.json)：各244文件 |
| 完整S2退役与承载保留 | [surface_s2_01](D:/eva/artifacts/rebuild_r49/applied/r50_surface_s2_01/components/applied_20261006_210210_123414/receipt.json) | [surface_s2_qa_01](D:/eva/artifacts/rebuild_r49/applied/r50_surface_s2_qa_01/components/applied_20261006_210308_319803/receipt.json) | 20,083格，44区块 | [construction源](D:/eva/artifacts/rebuild_r49/applied/r50_surface_s2_sources_01/receipt.json)、[QA源](D:/eva/artifacts/rebuild_r49/applied/r50_surface_s2_sources_qa_01/receipt.json)：各44文件 |

六份物理回执均记录 `verified=true`、0个BE写入，construction与QA对应批次数值相同。三批每份副本累计物理写入44,191格；区块数和源文件数是各批写入次数，不能直接相加宣称为唯一覆盖数。六份源回执记录实际目标文件、原文件备份以及 `progress_files_replaced=false`。源文件回执本身没有 `verified` 字段，不把它改写成原生冷区块验证。

完整生成声明包含已为空的退役体积、原土岩、现桥柱和公共复用，避免只修当次残留几格而让旧模板重新造回构件。Root按精确源单元合成原Static分片；同值重叠合并，冲突拒绝。原Palette前缀、其它Static、Ground和未列字段保留，不能用旧完整分片覆盖后来施工。相关离线源/NBT回读见 [C1与低列源检查](D:/eva/artifacts/rebuild_r49/surface_r50/complete_sources_payload_readback.json)、[山肩实际分片检查](D:/eva/artifacts/rebuild_r49/surface_r50/terrain_interface_repairs/actual_recipe_readback.json)、[S2实际分片检查](D:/eva/artifacts/rebuild_r49/surface_r50/retired_routes_r50/S2_lower_lining_readback/actual_recipe_readback.json)。P1另在 `tools/build_r07_port_transit.py` 设置有限入口保护：有当前 `native_transit_r22.json` 的世界拒绝重跑已退役P1旧生产器，历史原源和旧存档仍保留。

P1对应的 `quality_walk_cases.json` 是派生步行目标更新；实际MTR列车、线路、车站身份及交通进度没有重置。上述补丁没有写玩家、EVA、NPC、舰炮或舰船身份、库存和任务SavedData。

## 保留结构与S2待判项的关闭

**旧S2归属待判项已经解决并安装，不再列为待判HOLD。** 早期交接表的80米框 X-2048..-1969、Y112..115、Z746..752 只截到残衬尾部。实际创建源为R02 `estate_track_envelopes/ops.json.gz` 的160条 `rail/S2_city_street/tunnel` 操作，完整范围 X-2292..-1966、Y102..112、Z744..752。旧Y105直线已被当前曲向北的R1双线替代。本文以327米完整源、实际连接证据及双方安装回执替代早期未判记录。

S2保留承载有具体实体证据：西端X-2292/Z752的旧衬砌夹在stone101与stone113..115之间，上方现桥床116..118，恢复stone保持原固体几何；中段7根现柱芯由113..119连续light_gray连接120层machine_edge，再横连到当前formation。完整3×3接口 X-2099..-2097、Z747..749 保留77格混凝土和原空格。这里没有用“离轨道9米”代替承载判定，也没有另造替身铁路。详见 [S2判定与路径](D:/eva/artifacts/rebuild_r49/surface_r50/retired_routes_r50/S2_lower_lining_readback/DECISION.md)。

其他保留决定同样有测量依据：

- 13处实测山坡界面分别分类；南Kirisato自然岸坡、R44完整作者岸坡与花园、机场整地及铁路切坡保留。两处山肩只在有限范围重塑，峰值124/123保持，10个浅洞列整列保留。中心边界单格跳变分别11→1、9→5；外围原陡坡没有全部压平，也不把边界巧合宣称为已证历史生成bug。
- 铁路第14处的“52米土壁”实为道砟116、混凝土桥面114/115及自然草地64。全域该界面的691列高架道砟有实际混凝土形成层，予以保留；grass-cap复核后≥8边从混合soil检测的1,202降为720，剩余自然地形仍按原山脊和工程归属判断。
- P1旧站台复用为现公共广场，四组原基础真实接stone，原720格承载及后来502格施工保持。没有新增地下入口。派生的两方向接应目标已更新，原生步行及中途真实票闸操作未据静态结果宣称通过。
- 全域116处孤立低点中，14处是原导入船体内部或甲板开口，8处属于当前水、植物或交通，3处有当前站台/楼梯上下文；均保留真实用途，未填成土盒。另91处历史坑框的当前判定为81处原拒绝标高已实心、2处有防护的道路边坡、8处当前自然标高低一格，不能按旧坑编号重复回填。
- 原C1中13个后来公共复用构件和6个在用归属复用构件保持；新屋岛、港口、上壳装甲及机库回收柜四组件未被本批地形重塑覆盖。港区原两舰、炮与船体功能开口保持原身份和构件。

对应依据见 [13界面分类](D:/eva/artifacts/rebuild_r49/surface_r50/terrain_interface_repairs/thirteen_interface_classification.json)、[道砟语义复核](D:/eva/artifacts/rebuild_r49/surface_r50/terrain_interface_repairs/rail_ballast_semantic_readback.json)、[116低点实测](D:/eva/artifacts/rebuild_r49/surface_r50/global_depressions/actual_global_depression_readback.json) 和 [91历史坑分类](D:/eva/artifacts/rebuild_r49/surface_r50/surface_pit_complete_classification.json)。

## 原作与原创工程依据

采用TV 1995的箱根山谷、第三新东京市生活交通与EVA出动设施分层，版本边界和实际阅读范围见 [R44资料账本](D:/eva/docs/EVA_REFERENCE_ATLAS_R44.md)。本轮山肩、公共广场、原隧道退役和具体桥柱接口是当前缩尺地图的原创工程，没有宣称是TV原画给出的米制尺寸或指定铁路下弦，也没有导入官方影像、贴图或音轨。

[箱根地质公园官方说明](https://www.hakone-geopark.jp/hakonegeopark/)中缓山坡、陡火山口壁与深切河谷共存，[神山崩塌与流山说明](https://www.hakone-geopark.jp/area-guide/hakone1/003kamiyamahoukai.html)表明崩塌地貌可以有真实地质成因。因此相邻高度大跳变不自动等于错误。[国土地理院火山地形分类说明](https://web2.gsi.go.jp/bousaichiri/volcano-terrain-classification-release.html)用于区分自然地貌和人工交通表面。制作采用的是这些地貌关系，具体48米山肩过渡、草土帽和现工程接口属于本轮原创缩尺处理；本轮没有新看完整TV分集的宣称。

## 全域筛查覆盖与验收边界

[全域Heightmap表](D:/eva/artifacts/rebuild_r49/surface_r50/global_heightmaps/global_screen.json)是本轮施工前筛查快照：101,139个已存储区块中，60,282个FULL区块的15,432,192列全部尝试读取，0个未读错误；40,857个proto区块不具备完整地形，另79个零字节region占位文件不作为地表。15,248个FULL区块缺保存Heightmap，通过选定正Y section的Palette/index重建。246对相邻已存region的正地表边界已筛查，没有为补齐地图而新生成区块。

最终5,497个初筛对象包括5,239个相邻Heightmap跳变、112个孤立低点、142个region接缝跳变和4个接缝低点。**这是待解释的地表信号，包含建筑、树、水、道砟、合理陡坡和可能错误；不是5,497个缺陷，也不是5,497次质量通过。** 早期少量样本或未完成接缝的5,351对象计数已由这份完整初筛表替代。

保存Heightmap与重建表主要描述顶面，不能证明桥下空洞、房间、全宽通路、设备开合扫掠或功能用途。重建用当前已知原生碰撞形状判据，未知状态保守计作固体并另记清单；这部分不当作已获原生注册/形状验收。proto边界、未存区域和地下设备未由该筛查覆盖。后续施工及原生加载也不会自动刷新这份历史筛查表。

已有精确安装和离线源一致性检查通过；本批完整原生行车、人员全宽通行、未来冷区块生成与重载、地表连续画面及用户美术认可仍需在实际最终副本验证。山肩正射和剖面是低成本几何候选预览，不能替代游戏画面；其它战役、模型或编译检查也不能转算为这批地表验收。第40项的已落地修复和未验范围按上述记录分别交付，未宣称全图质量关闭。
