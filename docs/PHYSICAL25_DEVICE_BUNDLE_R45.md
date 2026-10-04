# R45 精确25格同基线物理组合包

最终候选是 `lifts_doors_lifecycle_sol_v2/physical25_combined_v4`，来源固定为R45_source_candidate_20261003_v4_01及其完整1736文件基线。18墙按钮、6 MTR出口、1 compact原地板共25格，无坐标重叠；完整before/after state/NBT均明确，所有NBT为null，精确inverse在heap还原。17门控制marker原bytes与候选bytes独立保存，只改变buttons/新增fixedInputContracts，不改变原17对象、两退役shaft门、轴/平面/设备字段。没有安装导航、启用模型或修改发车牌。

root命令在 `root_execution_commands.json`：正常退出目标MC后，新capture目标完整文件基线；preflight；显式apply --apply；重开MC前立即readback。新wrapper调用当前既有regional_voxels.Painter，拒绝immutable source/hot session/stale完整目标基线，保留backup+receipt。25格必须before/after无BE；当前source修改chunk内13个原BE全部完整保留，9chunk全部558section语义除25格外必须相同，未改chunk blob必须相同，两个region与一个marker以外所有UUID/level/实体/玩家/NPC/MTR/设备/任务/交通文件SHA必须不变。原writer会退役changed voxel里的BE，所以不能放宽null前检或拿本工具顺手删除invalid departure_board；当前(-124,97,-184)不在mask。

root本次事务失败会恢复同锁内3文件before bytes；可选rollback仅在整个post-write文件epoch仍原样时恢复原bytes。原生玩过、车移动或任何进度字段变化后拒绝region回滚，不能盲打静态inverse回原95,-395,-54坐标。需要新冷审计和新的原位/当前车归属inverse，不覆盖游戏进度。

源中14,-566,256精确feet位于固定阈口/缺车井边界，9点全幅bearing为NO_FULL_DATUM_BEARING；其格中心14.5,-566,256.5有完整固定承重。原rear车在-448，深层井内25air不是填地许可。追加native需真实呼到-566，原位置fringe占用必须安全拒绝或保持人物落脚、不夹人、不掉人、不强制re-seat；再经真实3宽轿门进入内边13.5,-566,254.5与中心走往返。14.5,-566,255.5是侧框碰撞拒绝探针，不能当合法车内lane。

同90配对集合保持不变，8个deep涉-566先、6compact次，接口JSON ARRAY符合冻结消费者；root可通过新bind工具在实际安装、新明确physical25 checkpoint及fresh lease后重排其普通bound suite与launch。24层完整外呼/车到/入车/native菜单/占用/出车/往返/reload/two-client输入、37指挥门真实按键与2MTR lane也已保存为UNBOUND。真正car入口80 lane、宽层门边缘44 census分别保存：普通car door halfWidth1为3宽，层门控制mask halfWidth2为5宽；gateway两门7宽。12个外侧直线proxy是原墙/玻璃/呼叫背衬，不能拆框；compact上层三点是原quartz stairs非平坦datum，需native步高验证。冻结90消费者的中心入车路径没有自动覆盖全部80lane或原始14点，不能用90通过假装这些追加项通过。

生成器现状已核源码及SHA：两个MTR/public bearing producer含实际.9375 guard，skin含whole native lift keepout；command有限frame修补producer和冻结Director完整孔/marker/支承守卫已在源码。原s41安装及s42按钮迁移authoring未改，新的rebuild仍需root修复该生成器，不能声称自动收敛。实际compact held-before负例的v6与17:27:36日志已按同一次字节读取冻结到工件；没有把City启动或日志当90成功。

默认五名机库NPC附查见 `default_crew_prepare_static_v2`：两pilot位于(-11.5,-394,-263.5)/(30.5,-394,-263.535141)，三个posted staff位于(8.5/50.5/92.5,-394,-263.5)。原UUID/完整saved NBT重读一致，按ModEntities注册的0.6F×1.8F standing body，与208 operator volumes交集0；formal2a真实collision_parts、源码quintic smooth及translation全行程交集0；canMove当前endpoint union加0.045判据也无交集。因此默认五岗位不是当前source会永久堵prepare的静态证据；没有真实运行证明。

现有prepare接线没有NPC清场阶段：EvaLogisticsDirector.requestPrepare一开始prepareFault，失败直接返回；prepareFault只加载登记区域/查实际entity、installed/model/occupancy/unique gantry，不给NPC下撤离订单。StaffCommandBook等待驾驶员boarded后让被选staff通过NervStaffDialogue/StaffNavigation走到控制台按实际按钮，再走NervOperationsConsole→requestPrepare；没有其他crew撤离步骤。NervStaffEntity闲置NoAI、只有begin任务时导航，finishTask/读取存档会return-to-post；three staff当前HadPendingStaffTask=false。TrainingPilotDirector具有显式board/return/standby流程，STANDBY tick止住导航并留在原安全岗；这不是prepare前撤离。metadata的crew_exit_routes与独立operator graph未接到NPC消费者，不能当已实现撤离路线。未移动NPC/改岗位/清任务/关闭碰撞/改模型。

剩余native项：root实际当前live NPC AABB/加载/活动/ROOT authority、真实gantry型号/clock与prepare时清场；来自游戏流程的新NPC或有人进入operator区仍需原生核验。若以后NPC真实进入危险区，源码没有自动撤离→同epoch复核→恢复prepare状态机，不能豁免NPC、挪其默认岗或绕过collision来宣称已通。
