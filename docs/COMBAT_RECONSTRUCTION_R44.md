# R44 战斗与全身动作重构记录

**2026-09-30 最新裁决：用户明确否决当前全部 3D 试片，warp/native 动作均为视觉 FAIL。本文下列通过项仅是结构、功能和诊断资料；它们不是动作样板或交付候选。完整二人 TV 风格 exchange 的重新制作见 `docs/TV_EXCHANGE_DIRECTION_R44.md`。**

本轮以负责人指定的本地 SEELE43 为底本。真实独立客户端／服务器 FISTS 修前记录有五机动作；初号机为 44 个服务端攻击 tick、59 个客户端攻击帧，肩臂变化 97.49°／117.16°。这不构成“无动画”投诉已复现或已修复的证据。网络记录在 `artifacts/rebuild_r44/network_runtime/before`。

## 已找到的第一处偏差

1. `beginKnifeMotion` 的动画时长除以 1.5，命中计时却没有同步除。普通刀约 15→10 tick，反手刀约 8→5 tick；60／80 伤害保持。R44 读取同一动作的接触相位，并由实际刀刃矩阵和连续扫掠结算。
2. 蹲／趴攻击走 Gecko strike controller，不设置 standing live action 标签。旧共享身体与基础走路层把它视作无动作，覆盖已播放的蹲／趴拳刀。现在依据真实 controller 的 triggered 状态保留这一姿态所有者；不使用固定十 tick 计时猜测私人动画长度。源分流已修，实际低姿态输入／画面仍待验证。
3. 旧刀为 51 通道，B 踢为 50 通道；当前五机为 73／72／72／95／97 通道。旧资源遗漏手指轴、拇指及 UN 关节适配。R44 完整按机体重定向并绑定 body／gameplay rig 合同；晚期手型层退出完整身体所有者，左手持刀待机采用独立松手条件。
4. Quaternion 与关节平移独立混合会破坏同心。新生成器曾被回读检出最大 3.62 model units 的肘中心差，修前失败保存为 `combat/candidate_validation_first_failure.json`。现在从最终旋转重算 `centre - rotation(centre - pivot)`；运行时和候选资源都执行此合同。
5. 原 R43 跑步约 104 格／周期。真实初号机跑速中位 3.146 格／tick，周期约 1.66 秒；直接除以 3.5 缩成 0.474 秒，并把支撑段滑动 RMS 从约 16.5 增至 72.4 格／周期。该增益只是失败风险对照，不能作为改善结论。
6. 实体 section 按 origin 索引。夏姆榭尔的高位小鞭段、雷米尔光束等会漏过脚不在该高度 section 的巨体。统一候选查询仅扩 origin 搜索，最后仍按真实 posed hull、原力场边界或有支持的实体 BBox 裁剪。
7. 已在锁定 Forge 1.20.1 的字节码确认：Level 版 `ProjectileUtil.getEntityHitResult` 返回实体构造器版本，其位置为实体 origin。EVA 步枪／炮直接拿该点，会令上身命中的弹道终点和炮爆炸跳到脚。统一 ray 现在返回明确的 `(entity, contact Vec3)`。

## 候选资源与步幅支撑

参考攻击包为 `artifacts/rebuild_r44/combat/motion`，签名 `R44-9cd7c54a2a44e89c`。普通两段、重击、刀、B 踢统一五机完整通道；TV 收尾采用 R43 直接前扑与共享时钟，在抓取段保持每帧的来源肩平面并重算肘轴／空间曲线。源 wrap 表面区间、终爆事件和停机端点继承保留。

步幅候选另存 `combat/locomotion_warp/motion`，签名以其中 `combat_bundle_r44.json` 为准。使用 walking 1.35／running 1.55 的适度周期提速，实际运行步幅约 43.2／67.3 格；同一实际速度下初号机约 1.28／1.07 秒一周期。每个循环支撑段固定同一前足 world 轨迹，缩短自由摆腿的水平残余轨迹，保留来源骨盆、胸肩、手臂和足滚转，再用固定解剖轴两骨 IK 重建腿／膝与同心 offset。

只在导出帧固定脚仍不足以保证运行时：Quaternion 插值会重新产生足位偏差。候选保存同源前足曲线，运行时在姿态混合／地形修正后按最终脚朝向对 end effector 反解，保留当前地形高度。跨 walk／run、idle／gait 的目标随同姿态权重混合；动作、低姿态、运输、反应及已存在的攻击脚锚具有各自所有权。

`encoded_support_check.json` 是对编码文件四分之一帧采样后的独立回读。当前平面前足支撑 RMS 最大约 `1.75e-6` 格／周期，数学膝中心间隙小于 `7e-14` model units。这个结果只证明平面候选、插值与几何合同，不代替真实地形、网络、GPU 网格或视觉认可。

实际 `stride_warp_orbit` 客户端记录已推翻把上述理论值推广为网络足滑的做法：支撑窗前足仍有约 0.27–1.23 格／tick 移动，动画 phase 与载具位置不是同一时间基准。后续源码复用 R33 已同步的 world 脚锚 Compound，按 R44 source 支撑窗放置／释放，并在 R44 地面待机／行走期间保持服务端移动所有者；不增加实体数据编号。此处新修改尚待新 native epoch 验证，不能计作真实足滑已修。

`stride_world_anchors` 为下一次真实独立网络批次：2125 个客户端样本、1037 个图像帧。连续支撑段的水平移动中位约 0.002–0.013 格／tick，但跑步支撑开始仍有约 4.16–4.59 格的跳变；右脚支撑只有少量有效配对，不能宣布整周期完成。source 右脚 run 窗口为周期的约 6.5%，左脚约 24%；没有为掩盖跳变扩大这些窗口。`support_trace.json` 将穿地分到实际动作状态：52 个低于地面 0.25 格的样本中，45 个在停步／刀结束过渡、7 个在 walk；rig2 最低 -1.7045 格在 age117 的停步过渡，其他极值出现在刀 phase=1 的结束后。

下一源码修订让 R33 接触在 gait 更新后执行，并同步八个同 tick 的位置／gait／run／move 快照；客户端在真实 renderer origin 对应的路径段采样同一 tuple，代替相位 50ms 与 vanilla 位置三 tick 插值的两种时间基准。服务器采脚仍依据它当前的 active 布尔，客户端使用位置匹配相位；这保留捕获新支撑时暂时放开该脚的逻辑。停步／收刀从上一帧完整脚位进入有限时间的 world 释放，最终 free／releasing 脚再走真实地面下界 IK，固定脚与全身根端保留。`FootWitness` 新增原生 active／plant 时间、source 窗口、快照、释放时间和地面修正前后 y；这些新修订等待下一 native epoch，不能由源码推出实际通过。

本批服务端位移／相位回读得到 run 有效步幅 67.3–68.0 格，与签名合同一致，实际周期约 1.39–1.92 秒。修前初号机速度约 3.146 格／tick，本批为 2.102；另外四机前后差约 0.3%。初号机独有的约 1.5 倍速度差原因尚未证明；当前候选没有因这个差异再次盲目增加 gain，也不能以周期数字替代画面判断。

第一批 day orbit 的相机至脚约 78–113 米，旧测试视距仅 6 chunk（96 米）；脚和远侧肢体在雾末端之外。浅白轮廓、圆形模糊地面不能当成巨大 root 高度错误。负责人将独立 QA 视距提高后重拍；普通游戏的相机设置没有由该诊断更改。`EvaFootWitnessR44` 分别保存最终 GeoBone FK 与真正 `skinVertices` 输出送入绘制的网格顶点，记录加载字节码／几何／网格 SHA，并新增全部 foot 顶点最低 y 与实际地面 ray。GPU 像素／后处理仍是独立层。

## 游戏必需资源身份

网络协议 45→46，登录后双向校验 body、五机 gameplay 索引、萨基尔 gameplay、finisher 及实际解析的物理 hull／恢复合同的 SHA，共九项。相同 `mod_version=0.1` 的不同动作文件会明确显示文件角色、服务器 SHA 与客户端 SHA，并断开；未确认资源的客户端十秒后断开。显式候选路径不再受旧 `regionalBuild` 条件吞掉，也不会悄悄退回缺失的旧路径。

同批清单只约束上述游戏必需动作文件；mesh／texture 可由客户端资源包覆盖。物理 hull 定义仍来自已有 `articulated_bodies_r35.json`，握手采用解析时冻结的 SHA，保持其可选缺失回退也能明确比较。R44 若提供 rig 合同，body 与 gameplay 的骨架列表必须完全一致。

## 查询和裁剪覆盖

| 对象／路径 | 当前查询与最终裁剪 | 原生范围／边界 |
|---|---|---|
| 五机普通拳、重拳、刀、B 踢 | 扩 origin 候选，真实姿态扫掠；旧区域动作使用 posed volume | FISTS 修前网络有效；本轮修后实际输入与命中待测 |
| 五机步枪、炮、UN 眼激光 | 统一最近 ray 接触点；entry plug 的嵌套驾驶员由机体遮蔽 | 射线上身、姿态空隙、墙阻与多个巨体挡射待测 |
| 徒步阳电子步枪 | 同一 ray 候选与接触流程 | 保留伤害／冷却，真实高位命中待测 |
| 跳击、落地、抓投 | 扩候选，身体裁剪；已锁定目标的抓投仍读真实接触面／可达性 | 受阻、坡地、远端与重登未通过本轮 |
| 萨基尔六种攻击 | 已有单一目标、同一 pose 的接触扫掠 | 当前资源继承；本轮多人／避让／倒地反应待测 |
| 夏姆榭尔三类鞭 | 每个时间子样本只作一次巨体候选查询，逐真实鞭段／墙面裁剪 | 不再仅拿 standing BBox 作为无力场身体 |
| 雷米尔光束／钻头／力场推开 | ray／posed volume／最近受支持身体点 | 原伤害值与露核规则不改；原生高位负例待测 |
| 力天使纸臂／眼光束 | posed volume／墙阻及最近 ray，光束停止在实际遇到的目标 | 纸臂可视动作仍为继承占位，不能说制作完毕 |
| 战略炮／N2 区域爆炸 | 扩候选，距最近真实身体点的原衰减曲线 | 半径、最大伤害与地形预算不改；多人／性能待测 |
| EVA／Angel 来源原生爆炸 | Mixin 扩候选；所有 Angel 与 EVA 距受支持身体最近点及对应冲量方向 | EVA／萨基尔用 posed hull；其他 Angel 当前为有支持 BBox，保持原生公式和 Forge 事件 |
| `source=null` 脚本、TNT、其他来源爆炸 | 原生流程 | 不在本次来源过滤内，不称“所有爆炸已修好” |
| 量产机仪式体、Ultraman、纯运输实体 | 未扩展此处专属动作／碰撞合同 | 不能由五机／使徒样本推断它们通过 |

战略爆炸改用最近身体点后，边缘／抬手的实际受击范围会改变；最大伤害与衰减公式保持。新刀／踢接触改成真实刃尖／脚部 3.2／4 格连续扫掠；旧宽 AABB 只是回退，不能把旧过宽范围视作刀刃质量。区域投影用真实私有 hull planes 与独立线性可行性 oracle 的 120 个旋转／位置案例交叉验证，零不一致。该数学检查不能代替原生 Mixin 启动与爆炸事件检查。

## 参考与制作依据

本轮实际查看已存在的 TV 第 2 话十五秒作画节选的接触图，来源为 [Sakugabooru 211172](https://www.sakugabooru.com/post/show/211172)。观察范围仅此节选：紧缩姿态、接近、左右手的不同支撑／抓核职责及近身压迫。节选包含倒转接近；本项目依负责人明确约束采用直接前扑，取消前空翻。参考图／视频只在私人分析目录，未加入 runtime 清单。

[Epic 的 IK Retargeting 文档](https://dev.epicgames.com/documentation/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine)支持以完整链和骨盆参考重定向、再保持手足接触。R44 将它落实到明确来源的躯干／肩平面、目标实际关节长度和接触目标，避免用旧机体 50 通道直接替代五种骨架。[Unity Two Bone IK 文档](https://docs.unity3d.com/Packages/com.unity.animation.rigging@1.2/manual/constraints/TwoBoneIKConstraint.html)把末端目标与弯曲方向分开；本轮用当前来源的解剖平面作为弯曲参考，完整链只作必要的 swing 修正。

真人来源仍是已登记、已哈希的 ACCAD、Haley Tuffles、Rokoko Eric Jacobus 刀动作及 G1 Moves K1 侧踢。原始动捕文件没有装进候选清单；来源、许可记录与 SHA 在生成报告中。当前六 tick 退出接续属于姿态连续混合，后续速度连续性可参考 [Daniel Holden 的惯性化过渡代价](https://theorangeduck.com/page/inertialization-transition-cost)，不能冒称本轮已经实现完整惯性化系统。

## 校验与待验

本轮自有修改清单与基线／候选哈希由 `tools/report_combat_r44.py` 写入 `combat/affected_files.json`。15 个既存用户文件回读仍全部匹配原 SHA。没有修改正式／施工世界、打包或提交。

负责人统一构建／GPU 队列执行：先以固定 bundle 开独立服务端及真实客户端，确认登录 SHA；依次普通两段、重拳、正／反手刀、B 踢、步行／跑步及走跑切换；F5 画面和最终骨／网格记录需与同批 SHA 对应。另测蹲／趴拳刀重刀（实际 Gecko 所有者）、坡地、墙阻、受击／倒地、跳击与落地、首战自然暴走／红眼／终局黑眼、取消与重登。

`CombatQueryNativeR44` 与 `review_combat_query_r44.py` 另提供独立 loopback 世界 `SEELE_R44_COMBAT_QUERY_QA`、专属实体 tag 的原生 API 验证。计划分母为五机×八种空间 ray＝40、17 生产接触／武器方法、九项资源不匹配服务器断连 handler＝66。阶段注入不验证真实输入／冷却／动作接触时序；原生 connected EmbeddedChannel 验证不冒充独立客户端九张拒绝界面。仅负责人统一队列可执行 `--run`，本代理未运行。

负责人实际首跑为 59／66。零号机五种 ray 的第一处失败来自远端冷区实体尚未进入可查询索引：同一 actor 的 `direct_body_hit=true`，但 `known_entity=false`、`feet_chunk_loaded=false`、`coarse_candidate=false`。测试世界预热自有 chunk 后，四项变为 true；徒步步枪 fixture 还移除了射手与目标之间的无用 EVA。生产查询／伤害没有放宽，五机最近巨体遮挡负例全部保留。第二次实际原分母为 **66／66**，结果 `combat/native_query_qa/20260930_153833/result.json`。这证明原生 API 与服务器拒绝 handler 的该分母，不证明真实玩家输入或最终可视动作。

低姿态进一步接入只有提供 `low_attack_revision_r44=1` 和完整十二个低动作时才启用，与当前签名 warp 包分开。两版隔离包 `low_attack_bundle`、`low_attack_v2` 均失败，禁止安装或将它们当作通过候选。第一版发现旧 prone 末端把足与胸放在 y≈0，但实际 shin rigid mesh 有约 -14.9 model units 的下穿；整体抬根会把原本落地的足胸抬浮，因此未采用。第二版纠正膝分支后仍有下穿、部分 UN 末端超达和最大 160°／frame 的 IK 分支跳变。低姿态源码时钟／实际接触接线已独立建立，但没有合入 signed warp，也没有冒称新增低姿态制作通过。

当前结构／数学通过、负责人构建通过与修前真实网络资料分别记录。本轮尚无新增用户认可。完整战斗、所有使徒新可视攻击、低姿态接触、两真实客户端、GPU 与最终视觉检查仍未关闭。
