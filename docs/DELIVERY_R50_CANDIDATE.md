# R50 测试版交付准备

用户已同意本轮先完成原机吊装修复，再发R50测试版Server与Client_PCL两包；整体远距屋岛、大型运输井、多机并行、升炮/趴姿接驳留下一轮。测试版可明确携带未验收清单，不因完整艺术自审未完成就把既有实现归零；也不冒称全功能/用户认可。41大项主状态为9项有有限功能原生证据、31项已有实现/资料/资源候选待场景或人工、1项两包/Git执行未完成，详见[事实表](FINAL_STATUS_R50.md)。本材料没有运行构建/封包或改世界。

launch18已过脚部，实际hand_r#0在39/109/452浅交叠2.93cm仍拒；新纯up充分条件与全现场73骨/19部件上扫blockingPairs0仅离线，最终build23完整构建及针对性碰撞回归已通过，不预填native起飞。用户09:12:39保存退出后不反复开客户端，最终实际起飞交用户验收；两包日期仍20261006。

新增独立入口：`tools/prepare_r50_two_pack.py`、`tools/r50_selected_payload.py`、`tools/prepare_r50_resource_identity.py` 和 `tools/templates/r50`。R49脚本、模板、结果和旧R48交付均保留。默认只准备计划，不启动Java/Gradle、不写世界、不生成正式身份、不创建ZIP、不改已安装PCL。

输入默认仍是 `artifacts/rebuild_r49/assets`、`runtime`、唯一 `construction/SEELE_R49_WORLD` 与 `release_inputs`。只允许显式选择受信R49/R50输入根的规范assets/runtime和construction目录，拒绝QA/session/review世界。服务端ZIP内世界目录为 `SEELE_R50_WORLD`，直接流式读取原冷施工源，R50 staging不复制世界，客户端不再带完整世界。

输出拟为Server和Client_PCL两包。Client_PCL保留标准CF manifest v1与全部21模组，远程mod列表为空，可直接PCL导入；服务端保留全部17模组、Java17、Forge47.4.10、-Xmx20G、NERV图标、EVANGELION:Encore R50测试版MOTD与默认eula=false。协议每次从SeeleNetwork源码动态读取，并核对最终Jar实际常量；当前计划快照是60，未来源码变化将重新读出，不能硬写旧57。

最终执行入口要求Root结束真实会话、给出绑定唯一施工源的实际进度收据、定稿无占位符的四份选中说明、生成当前R50正式资源身份、选择同批最终Jar。身份工具默认只打印计划；正式生成时记录输入mtime/size及摘要，包验证查同一源epoch而不追加SHA套件。Jar验证覆盖继承R48、所有R49/R50源类、实际Gaghiel资源和新原机/炮盾/回收/到场钩子。实际包回读覆盖完整成员名/大小、选中Jar/runtime字节及有限小型原进度.dat/.json字节，不把打包检查叫原生或视觉通过。当前PACK_PLAN仍`prepared_only:true/ZIP_created:false`；缺失EXECUTION_RECEIPT，未把计划输出路径写成现成发行包。

仅准备计划的入口：

```powershell
python tools/prepare_r50_two_pack.py
python tools/prepare_r50_resource_identity.py --out artifacts/rebuild_r50/resource_identity_final
```

`WORLD_AUTHORITY_R50.example.json`只是收据结构示例，保留false/pending，不是假造保留进度证明；root实际确认后自行建立正式收据。不得把默认准备工具当成execute授权或实际发包结果。

屋岛/港区源码和civil已安装；地下机场双方有160,316格/263完整分片、唯一授权飞机与两个installed marker。屋岛真领/两束盾/同柜维修有有限实测，gen1及gen2仍未首炮并真实失败；旧161.609米保存拒绝不是gen2唯一原因，也未捕获03:51首帧。机场已有断电闭环、有电准入和一次活CRUISE重登闭环，不扩大成全程有电、全姿态/节点/NPC/其他重登或美术通过。港区未测；八板有实损与实际按钮修复，原总部/Terminal未贯通，原舰航行/TV沉舰未实现。

attempt11/build14完整build通过并实测原01真人登原栓、电话prepare→SILO_READY→地下DEPLOYED、真实S/A沿平台驾驶。电话自动选路进入地下链后nearest判据拒绝，未生成飞机job，完整flight没有通过；当时保存机体root(33.41616755272836,-410,99.02259963102118)/yaw152。重复4米余量造成0.1874米盒外过估，build15已包含修正，仍未证明实际飞行。

[attempt12](../artifacts/rebuild_r50/native_client/attempt12_scope.md)证明退役carrier clock重登回放经client root和原版MoveVehicle反写了server/autosave，实际原机变成旧pad(30.5,-410,6.5)，并非只视觉。Root已修load/首次tracking finalframe/关机本地驾驶权/server packetguard；没有离线恢复旧位、编辑NBT或替换原机。旧pad回收误拒合法17/-411/6铁跑条的三个消费者已修且世界未改，attempt13已以正常机械回收实证。

[attempt13/build16](../artifacts/rebuild_r50/native_client/attempt13_scope.md)断电同原机闭环通过；[05:44:29保存](../artifacts/rebuild_r50/underground_airlift/build16_original_return_proof.json)原飞机回场无Job/Cargo=false，原栓OCCUPIED1真人仍乘坐。后来真人正常潜行加移动离座，不把后来变化倒填到这个保存。

[attempt14/build17](../artifacts/rebuild_r50/native_client/attempt14_scope.md)在06:03:33通过有电12tick/contact准入，06:03:57自然断电，早24秒，不能写全程有电。06:05:07活CRUISE存盘的[未改checkpoint](../artifacts/rebuild_r50/underground_airlift/build17_airborne_checkpoint_readback.json)证明原飞机cargo=true、原01/栓/真人链和pitch90/restraint1；退出菜单正常重登后06:09:14真实handoff、06:11:13原01PARKED。只覆盖这个活CRUISE重登，不覆盖自由机体场外重登、全部阶段/节点/姿态/NPC、专服或美术。

同attempt14的屋岛gen2仍真实失败，目标d5328fab-dec5-4ac6-a0fd-b8eed7034d9c与早期gen1不同，原机/原驾驶员/原库存复用。没有炮日志不是未进npcTactic的证明；源码已确证每tick同武器selectWeapon清充能。Root已做幂等选择与NPC实际≤1.5米到场首锁同步，build18 jarJar成功，launch15准备同gen2 retry；首炮/完整屋岛未通过。build17日志当时旧文案不因后续text-only源码更新而倒填。

后续build20完整build通过，launch17将续同原00的实际受阻请求，尚无新原生起吊通过。`EvaPoseSnapshotR50`仅使原encode/decode脱离MC注册初始化，NBT格式不变，真实codec2400组轴/位移回归通过。原00脚49点LP证明在障碍柱内最小Y110.908>top110；query skin由7.5cm改1mm，旧kernel/新fixture失败而新kernel通过，真薄roof及足上障碍仍拒，接触solver不改。玩家doPush现先测实际部件，不据粗restBBox认定reload一定空；Ramiel tracking12→32 chunks仍受真实StartTracking/视距cap约束。这些是根因/源码/数学范围，不替代原生或发行验收。

[build18/gen2实际首炮](../artifacts/rebuild_r50/native_client/build18_gen2_actual_first_cannon_damage.json)已记录07:01:08、mission Shots1/原库存炮counter1、同目标350→150.0800018实际伤损；core伤害解释是数值推断，不作直接core-hit日志。两柜原物保持同UUID/Count1，三原机PARKED，炮后coolant/reload Readyfalse且未观察到服务完成。仅首炮/实际伤损通过，第二炮和屋岛完整胜利未通过。

## 机场实际内容与两包纳入规则

只读审计直接读取当前冷施工源、实际263分片安装回执及飞机MCA，不调用两包工具的prepare/execute/finish函数。依据为[DELIVERY_CONTENT_AUDIT_R50.json](../artifacts/rebuild_r50/final_docs/DELIVERY_CONTENT_AUDIT_R50.json)。

| 内容 | 当前施工源 | Server包规则 | Client_PCL规则 |
|---|---|---|---|
| r50_underground_airport.json | 存在，installed=true，receiver脚位齐全 | SEELE_R50_WORLD根目录，未被排除 | 不含world，按服务端权威同步 |
| nerv_underground_transport_r50.json | 存在，installed=true，同唯一飞机UUID | 同世界根目录，未被排除 | 不含world |
| r50_underground_aircraft_receipt.json | 存在，真实新实体1与原NBT保留 | 同世界根目录，未被排除 | 不含world |
| 机场/receiver完整生成源 | 263/263文件存在，当前大小均匹配实际安装回执 | dimensions/projectseele/geofront/data/city_rigid_generation_r45/chunks/下递归纳入 | 不含world |
| 唯一地下飞机2c408ff4-6978-45db-8ffa-dfa2743d17b5 | 实际记录区域内恰一匹配，完整typed NBT等于安装回执 | dimensions/projectseele/geofront/entities/r.-1.-1.mca整体纳入 | 不含world，不另造客户端飞机 |
| Jar与运行资源 | 选择同批最终Jar/runtime，正式身份仍由Root收口 | mods/config/projectseele-local-maps | overrides内同批Jar与runtime |

脚本从唯一施工world递归枚举真实文件，只排除session.lock、日志/截图/crash/debug/reports/native_qa、inbox及ack诊断记录。已核机场两metadata、飞机receipt、263source与actor所在MCA均不触发排除，因此本次没有确认的机场文件遗漏；这不等于最终ZIP已存在或已经回读。

明确尚缺的检查与材料纳入边界：

- Root已授权补齐`validate_inputs`专项前置：两实际installed metadata、真实飞机receipt、263个完整source与actor区域，共267必需成员；冷施工源已只读检查通过。源文件遗漏、marker未装或原飞机缺失/重复会拒绝。
- 已补`archive_readback`实际Server包的267成员字节、两个完整metadata及唯一actor完整typed NBT检查，使用既有region/parse_chunk codec，不另造解析器或临时解包、不新增hash测试。本次没有运行封包，最终ZIP实际通过仍待Root执行。
- 类名/资源/有限hook检查不证明最新NPC幂等充能/到场首锁行为；最终选中Jar及同场首炮仍待Root原生复验。
- 两包只固定纳入README_R50.zh.md、MANUAL_R50.zh.md、NEXT_ROUND_R50.zh.md、FINAL_STATUS_R50.md。本工程DELIVERY_R50_CANDIDATE及专项审计JSON/Markdown不在DOCUMENTS清单；说明里的工程证据链接不是承诺在ZIP内附带完整artifacts。
- 最终ZIP实际成员回读、PCL GUI导入和同批双端运行没有本次结果；当前仍是prepared-only计划。

Git追踪建议见 `artifacts/rebuild_r50/final_docs/GIT_TRACKING_R50.json`，其状态只代表记录时点，不能替代Root最终diff/stage/commit审阅。本次没有stage或commit；不修改个人PCL、R48/R49已存在交付、资产或打包源码。
