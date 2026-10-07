# R50 GeoFront地下运输机机场安装记录

2026-10-07，用户新增地下运输与自动地表/地下回收需求。Root已将西北自然地坪、三轴Z100.5接应位及完整侧向人员重接安装到construction和同一原生QA：两份实际施工回执各确认160,316格、260个物理区块，生成源合并为263个完整分片；每份副本仅追加一架地下运输机，两份世界的机场与运输标记均已`installed:true`。attempt13通过一次断电同原初号机闭环，attempt14又通过有电准入及一次活CRUISE保存重登后的同原链回库；全程有电、全部姿态/节点、人员通行和美术仍不计通过。

## 原作与原创边界

本轮重新阅读 [GeoFront资料](https://wiki.evageeks.org/Geofront)与 [NERV总部布局](https://wiki.evageeks.org/Nerv_Headquarters)：采用顶部收纳城市、下方总部与森林/湖/自然地坪并存，以及机库、移送和发射机构的功能分层。它们是爱好者对TV资料的整理，布局仍有争议；不把文字中的公里尺度直接套到当前缩尺存档。项目已读运输资料及版本区分见 [AIR_TRANSPORT_R31.md](D:/eva/docs/AIR_TRANSPORT_R31.md)。

地下待命机场、具体停泊场、三条延伸接应轨道与侧人员阶梯是用户授权的原创工程；未声称TV展示了同形机场，也没有导入官方影像、音轨或模型。飞行载荷仍使用原EVA及其实际姿态，原surfaceplane和两台UNplanes保持。

## 真实场地与停泊

西北地坪中心X-440/Z-270，180×160范围 X-530..-350、Z-350..-190 的29,141列全部有实测草地，标高-481..-474，构筑和木材计数均0。场地远离旧机库、原地下铁路与湖区。本轮只作有限硬地坪、12米缓坡肩及五米人员联络路，不重塑整个地下地貌。联络路向东到X-150，再南行Z131接原R48人员阶梯草地交接端，绕开湿式机库与铁路。

地坪方块Y=-476、顶面-475；飞机停泊根为 `[-440,-464,-270]`、yaw0。实际选中机体网格 local bounds 为 `[-69,-11,-56]..[69,19,58]`，-11最低点是四个起落轮，因此轮底恰接真实地坪。停泊不是用EntityType的8×8代替138×114机体。空机停车保持yaw0，升到开放高度后才允许转向；全yaw规划半径95，真实飞行仍由完整机体/旋翼及冻结EVA形状扫掠判断。

机场容量为一台重型VTOL，包含完整硬地坪、坡肩、实灯杆、带墙/顶/窗/门的控制岗、原生完整NBT导视和地面通路。驾驶通信O是现航空部门接口，没有放置未绑定的假调度按钮。原结构外的自然树若与新人员路实际相交，按完整树体及精确逆补丁处理。

## 三轴接应与人员通路

接应位为 `[-11.5,-410,100.5]`、`[30.5,-410,100.5]`、`[72.5,-410,100.5]`，机体与飞机最终yaw180。飞机根为对应X/Y-298/Z100.5，保留112真实吊距。机械架绑定原机体整姿后，沿同轴31宽实轨回原padZ6.5及bedZ-35.5，原三机身份、后门与任务进度不变。

原padZ6.5头顶的飞机体域实际撞28,050/35,768/28,749格竖井与相关构件，不能直接飞到旧pad。南延Z100.5固定body及全yaw主干留出净空，没有挖毁原井。接应冠覆盖完整35宽承载，轴上65高全身域保持；深边桁架、面连接横梁及柱脚到逐列实测自然地坪，原Z20侧墩明确复用于头部承重。

平直新轨会覆盖原Z17..33人员阶梯上段，故完整退休该段踏步/上层基础/边护并重接，原Z34..128低段保留。零/初号机共享X9五米侧阶梯，二号机用X93侧阶梯，三处顶口与下口实接原pad及低阶梯，六米下穿净空保持；旧`r48_underground_sortie.json`床/pad/门接口不变，追加重接路线并改剩余阶梯边界。旧R48准备器在实际R50机场installed后拒绝重建退役上段。四块真实墙牌分别由原pad边基础/新桁架支承，指向侧人员入口，中央明确为机械轨道。

## 完整组件与安装边界

候选目录为 `D:/eva/artifacts/rebuild_r50/underground_airport/candidates/`：

| 组件 | 物理变化 | 完整生成声明 | 实际NBT分片 |
|---|---:|---:|---:|
| airport/UG01_northwest_heavy_VTOL_airfield | 124,473 | 1,625,777 | 196 |
| receiver/UG02_three_rail_receivers_and_crews | 35,823 | 762,419 | 67 |
| guidance/UG03_actual_crew_side_guidance | 20 | 20 | 4 |

每个父目录含 `complete_generation_source.jsonl.gz` 与完整原Static/Palette/Ground保留的recipe；子组件有精确forward/inverse、完整NBT与正掩码。三者独立检查通过；633,404个声明几何单元的35冠、65高机械域、五米侧阶梯、六米原低阶梯净空及四轮接地检查通过。这是离线几何检查。上表分片数是独立组件输出，合并重叠完整声明后实际安装263个生成分片；不能将离线检查数量当作原生飞行次数。

`r50_underground_airport.json` 为Root接应模块使用的schema50文件，保留全部`receivers[].feet`精确坐标。冻结候选仍为`installed:false`；两份实际世界文件在土建、生成源与唯一飞机回读后已激活为`installed:true`。机场标记补丁在 `airport_marker_metadata_patch.json`，原R48路线补丁在receiver目录。航空逻辑的 `nerv_underground_transport_r50.json` 由航空代理生成，两份实际世界也已激活；额外GeoFront外场域已并入有限连通图，运行时仍逐步校验完整飞机和原载荷。该航空图的airspace是受限操作域，保留原地面、接地面和边护，不能当作清除域内任意原设备的许可。

唯一新地下飞机UUID为 `2c408ff4-6978-45db-8ffa-dfa2743d17b5`，完整factory NBT在 `new_underground_plane_candidate.snbt`。`tools/prepare_underground_aircraft_entity_r50.py` 默认plan、只有Root跑`--apply`；只接受construction与原同一QA、本副本真实verified civil receipt、UUID不存在、session.lock、完整停泊实际几何。它复用现精确entity-region codec，保原实体/完整NBT、备份MCA、只追加一个新飞机并回读，写一次receipt；不生成库存、不重置原演员或SavedData。早期预安装plan因缺回执和地坪而阻止apply是历史准备证据；之后Root已分别完成两份实际安装，各自receipt确认`new_entities:1`与完整原实体NBT保留，不能再次commission同UUID。

实际安装依据为[construction土建回执](../artifacts/rebuild_r49/applied/r50_underground_airport_01/components/applied_20261007_012713_950457/receipt.json)、[同QA土建回执](../artifacts/rebuild_r49/applied/r50_underground_airport_qa_01/components/applied_20261007_013844_011144/receipt.json)、[construction完整生成源回执](../artifacts/rebuild_r49/applied/r50_underground_airport_generation_01/receipt.json)、[同QA完整源及元数据回执](../artifacts/rebuild_r49/applied/r50_underground_airport_sources_qa_01/receipt.json)，以及[construction唯一飞机回执](../artifacts/rebuild_r50/underground_airport/actor_construction_01/receipt.json)、[同QA唯一飞机回执](../artifacts/rebuild_r50/underground_airport/actor_qa_01/receipt.json)。两份[construction激活回执](../artifacts/rebuild_r49/applied/r50_underground_airport_activation_01/receipt.json)、[同QA激活回执](../artifacts/rebuild_r49/applied/r50_underground_airport_activation_qa_01/receipt.json)登记机场与运输marker；测试日志不代替这些回执。

主干航点采用机场根→垂直升空[-440,-260,-270]→南侧空腔[-440,-260,100.5]→[-200,-260,100.5]→三机接应上空→对应-298卸载。实际城市NBT按各tower的RetractedBaseY判断：该南主干XZ范围相交的44栋最低为-101；三座更深高楼不在此主干XZ内，不能用80-312估值替代真实所有权。原飞机/载荷连续扫掠、原姿态接架、一般GeoFront外场额外可接载域及就近图分支由Root/航空代理接续验证，不能把所有负Y房间当同一空腔。

## 本轮原生断电闭环

[attempt13/build16](../artifacts/rebuild_r50/native_client/attempt13_scope.md)先正常回收旧pad上的原断电01，于05:24:20完成PARKED，确认登记钢跑条的兼容修复。随后同原机正常整备到05:28:45 SILO_READY、05:30:04地下DEPLOYED，并以真实S/A驾驶到外平台。05:32:53真实电话创建地下job，有电时旧Motion静止判据仍等待；自然断电后05:35:04原机场飞机实际离场，完成approach/clamp/lift/stow，05:36:38报告俯卧运输，05:36:46进入到站卸载，05:36:51下降。

05:37:09以真实最低部位接触`(14.965291786871234,-410,92.93580757668536)`完成positive receiver handoff，原机沿轨回库，05:39:07原01PARKED。没有假接触、强置PARKED、替换EVA/栓/真人、离线恢复旧位或人工补电。

[05:44:29保存回读](../artifacts/rebuild_r50/underground_airlift/build16_original_return_proof.json)确认同原01 `66519c87-962b-4877-b553-f85cd3360a12`在原库位、健康300；唯一原飞机`2c408ff4-6978-45db-8ffa-dfa2743d17b5`已回`[-440,-464,-270]`，yaw-360等价0，Cargo=false、地下状态无Job。原栓`a5390e79-8d48-4edc-9076-81adef18f6cf`在原吊位，stage为**OCCUPIED1**，原真人仍乘坐；不能把原机回库写成栓已EMPTY0或真人已离座。此结果属于QA实际运行，未复制进度到construction。

上述有效结论为“断电同原机闭环本轮实测通过”，不能倒填为有电通过。随后[attempt14/build17](../artifacts/rebuild_r50/native_client/attempt14_scope.md)在06:03:33通过12tick实际稳定/contact准入并离场，06:03:57才自然断电，早24秒；只证明有电准入，不是全程有电接载或flight。

06:05:07在活CRUISE中实际暂停存盘，[三文件checkpoint回读](../artifacts/rebuild_r50/underground_airlift/build17_airborne_checkpoint_readback.json)确认原飞机cargo=true、同原01/栓/真人、age1/duration183和已接受pitch90/restraint1。没有序列化paused标志，不虚构这个字段。正常退出至菜单并进入同一存档后续航，06:09:14真实touchdown/positive handoff、06:09:32receiver整姿、06:11:13同原01PARKED。后来真人以正常潜行加移动真实离座，05:44:29的OCCUPIED1保存事实仍保留其时间范围。

全姿态、所有接载节点、NPC返航、其他飞行中断阶段、自由机体走离场地后的重登原位回归、人员实走、外部逐段运输画面、用户美术与专服仍待完成。build17日志保留当时旧文案，后续文字源码不倒填为它的实际效果。R50仍为未发布工程；两例窄范围通过不等于整机场或最终两包验收。
