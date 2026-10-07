> 历史诊断：本文保存的是attempt07～08当时状态；后续出站、首炮、机场和吊装进展见FINAL_STATUS_R50.md，不能把本文的“最新”当作R50交付末态。

# R50 屋岛原机进山受阻：attempt07 实际首错误

本记录对应 build candidate09 的同一份原生 QA 保存；没有重置战役、玩家、驾驶员、插入栓或 EVA。这里只诊断当前保存状态的下一步阻挡，并给出完整自然树组件的可逆土建候选。它不把静态筛查称为原生战役通过。

随后Root已将78格整树修复及150格完整生成源安装到construction和同一QA；[construction实际回执](../artifacts/rebuild_r49/applied/r50_yashima_approach_tree_01/components/applied_20261007_020958_683261/receipt.json)、[同QA实际回执](../artifacts/rebuild_r49/applied/r50_yashima_approach_tree_qa_01/components/applied_20261007_021106_566701/receipt.json)均为`verified:true`。下文“候选未写世界”描述代理制作阶段，不能当作目前未安装。后续build11 attempt08确切起吊首阻挡变为保留山肩的土/草与原姿态左脚壳交叠，说明树修复已安装但尚未完成原机实际出障；不会通过削掉山肩代替验收。最新实读仍为`ramiel/approach`，PilotReturn与StaffRecovery订单为空，表面空运`Returning=0`；八板贯穿不能自行推成任务已failure或返航。

## 实际保存状态与故障边界

原目标 `59e37a68-0acf-43ed-af67-db927988a8dc` 仍在 `(30.5,144,355.5)`，血量 350。原零号机 `fbe61635-4d0e-42e7-b3d4-f08cf2061f74` 保存脚位为 `(-78.95420399087843,83,450.5)`，原初号机 `66519c87-962b-4877-b553-f85cd3360a12` 为 `(-33.29227557822054,95,498.5000000185867)`；两机均保留原插入栓及栓内原驾驶员 passenger 链。

零号机的 route cursor 是 0，当前目标为 `(-85.5,82,498.5)`，stall 9783。初号机 cursor 52、stall 0，距炮位水平约 63.79 米。`TvYashimaArrivalR50` 在射手距炮位小于 65 米且盾机未完成待命时，明确要求射手等盾；初号机当前等待是正确同步行为，本候选不修改它。城市控制账本为 `IDLE/Depth312`，不是城市没有下降导致的这次入口树木阻挡。

同一任务 scope 记录原两机分别在 01:10:37、01:11:04 完成真实发射；本次运行因进山受阻、表面运输机无法起吊而未完成屋岛战役，八层装甲已被打穿。保存的 campaign 字段仍为 `Active=ramiel/Phase=approach/Generation=1`，不能据失败描述自行改为完成或重置。空运 job 保存为原零号机 `PREPARE/Carrying=false`，提示“机体或四肢上方有遮挡，等待起吊通道清空”。该提示没有记录精确 GJK 受阻肢体；本报告不冒称已证明具体某一身体部件的起吊碰撞。

attempt08的新默认日志明确给出原姿态`foot_l#0`在向上238米扫掠时碰到`(-65,83,454)`，另有`(-65,83,452/453)`及`(-65,84,454)`。cold construction实读分别为泥土、草地、草地、草地，完整Y01源均登记为连续自然西肩的新增土壤，保留理由充分。当前优先恢复同一原任务的真实步行并继续首供货节点；若再次受阻，已测西向段最早满足35×35开阔柱的备用点为`(-92.5,81,450.5)`，水平西移13.55米，Y81..319整柱及其112吊距上方飞机全yaw95包络均无固定方块。该点没有移机或改地形，也未获得实际姿态起吊通过；使用前仍须原机真实步行到达和完整GJK检查。备用交付仍去原取盾冠，不切任务。证据见[保留山肩与原任务接应选项](../artifacts/rebuild_r50/yashima/attempt08_lift/preserved_shoulder_and_original_mission_option.json)。

## 当前第一处可以逐格复查的阻挡

当前零号机 17 米宽、60 米高的原生实体盒没有固定方块交叠。向第一个真实路线目标前进一米后，盒体进入 Z459，撞上 `(-74,85,459)` 及同列树冠的橡树叶；原移动方法尝试的 +1.6 米抬步仍撞上树叶。construction 与同一 QA 的全部 78 格树木修前状态一致，两份世界下一米均有 12 格叶块相交。

完整植物个体由相邻原橡木干和叶组成，共 78 格，范围 `[-74,82,459]..[-70,87,463]`。清理完整植物个体后，虚拟下一米的 17×60 原生盒与抬步盒相交数均从 12 变为 0。这里的“第一处”严格指当前保存位置沿真实目标的下一步；没有把保存末态当作整次运行第一帧的历史证据。

先前土建漏掉了原零号机进入既有 156 节点坡路之前的自然林接口。坡路本体是 EVA 通路；附近三格人员步道不能代替大机体净空。这次修复针对实际入口植物，不删除原道路、建筑、承重、供电桩、供货架或城市移动归属。

## 完整候选与生成源

所选 `eva_body_r44.json` 的 rig support 动作实测中，站姿过渡 `unarmed_stance` 横向包络宽约 32.315 米，idle 约 31.679 米，walk 约 16.600 米。候选采用 35 米横向净空筛查，并沿每条真实路线方向保留前后 32 米植物筛查裕量。范围包含保存零号机至首节点、156 节点供货路线、44 节点盾路线、56 节点炮路线；只命中上述一棵自然树，周边林木保留。实际动作包络来自选中文件的离线解码，不是另造 31 米实体盒，也没有修改模型或动作。

冻结候选在 `artifacts/rebuild_r50/yashima/attempt07_approach/corridor_tree_candidate_v2`：组件 `Y03_actual_north_entry_whole_trees` 退休 78 格，完整生成源覆盖该树 5×6×5 的 150 格外包络，包含原空气和保留的真实土壤。逐格 forward、inverse、positiveEditMask、完整 blockstate/NBT 均齐全；生成器完整模板将这一植物外包络内的原木叶设为 AIR，避免只修改当前世界却被原模板回填。没有 BE、实体、库存、任务进度或交通 SavedData 改动，metadata operations 为 0。

精确 mask/inverse/NBT 校验通过；实际生成 NBT 分片回读通过，并保留分片内掩码外原静态记录、原 palette 前缀和其余字段。Root 应将 `complete_generation_source.jsonl.gz` 合入当前生成分片，不能用旧整文件盖回已经安装的机场或其他新源。候选没有自行写世界，也没有翻转任何 installed 字段。

后续路线按约一米间距复查实际固定方块：供货／盾／炮路线分别 401／129／171 个样本。17 米原生盒的剩余相交只发生在缓坡承载面 `nerv_floor_panel`，均落在原 2.6 米抬步带内；没有超过抬步带的固定阻挡。沿每段真实方向计算的 35 米宽、前后 32 米、脚位上方 12..61 米上身包络筛查也没有命中建筑或设备。这是静态保守筛查，尚未逐姿态做原生碰撞回归；缓坡板不能因简单包络交叠被当作障碍拆除。最初轴向矩形过估会扫到路径侧后方的供电桩，方向修正后的结果保留原桩，并没有清除它。

## 证据与待验

- [本次原生运行 scope](../artifacts/rebuild_r50/native_client/attempt07/scope.json)、[日志](../artifacts/rebuild_r50/native_client/attempt07/client_launch_07.log)。
- [原机完整保存 NBT](../artifacts/rebuild_r50/yashima/attempt07_approach/saved_original_entity_evidence.json)、[原任务／空运／城市保存 NBT](../artifacts/rebuild_r50/yashima/attempt07_approach/saved_task_airlift_city_evidence.json)。
- [所选 rig 动作包络](../artifacts/rebuild_r50/yashima/attempt07_approach/selected_rig_locomotion_envelopes.json)、[两世界下一步修前与虚拟修后回读](../artifacts/rebuild_r50/yashima/attempt07_approach/first_step_two_world_virtual_readback_v2.json)。
- [后续三条完整路线的方向包络与原生盒静态筛查](../artifacts/rebuild_r50/yashima/attempt07_approach/remaining_full_routes_directional_screen_v2.json)。
- [冻结施工与完整 source 索引](../artifacts/rebuild_r50/yashima/attempt07_approach/corridor_tree_candidate_v2/final_handoff_index.json)、[mask/inverse 校验](../artifacts/rebuild_r50/yashima/attempt07_approach/corridor_tree_exact_audit_v2.json)、[实际 NBT 分片回读](../artifacts/rebuild_r50/yashima/attempt07_approach/corridor_tree_recipe_readback_v2.json)。

TV 屋岛战使用自然山地与工程炮位的既有设计依据仍见 [R49 战役设计讨论](BATTLE_DESIGN_DISCUSSION_R49.md)；本次完整植物清障是为真实 EVA 通行作的原创工程修正，不声称这棵树或路线尺度来自原作。

Root 安装后仍需让同一原零号机、原驾驶员与同一战役继续实际行走，复验取盾、侧坡入位和射手随后取炮。若运输 PREPARE 仍受阻，应记录实际起吊 hull 首阻挡后继续修复，不可以传送、跳过受阻或替换原机当作成功。静态模板校验不等于走完路线、击败原目标或用户美术验收。
