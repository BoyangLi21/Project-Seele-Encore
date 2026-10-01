# R44 全身交锋重新制作：旧试片全部视觉 FAIL

2026-09-30 用户明确反馈当前 3D 试片「没有一个过关，差非常大」。此前 warp、native walk/run/knife、低姿态包全部不再是交付或动作样板。66/66 原生 API、骨架/偏移数学检查、网络 SHA 和时钟修订仅保留为诊断及功能证据，不能计动作成果。

## 当前失败如何落到制作问题

- 脚支撑虽被数学锁住，骨盆仍被末端可达性反复下拉；持续弯膝、骨盆过低的轮廓缺少清楚的承重／起蹬，是姿态问题，不能由更快换脚解决。
- 走跑像沿轨道搬动局部腿形；骨盆、胸肩、头和手没有共同的动作线。刹步时先丢脚锚再恢复 idle，也使整个身体突然重排。
- 拳／刀素材的手臂意图没有按 EVA 长肢、肩装甲及手的实际接触面重新组织；能见到曲线变化不等于力量沿脚、髋、胸肩到手的传递。
- 只有单机挥手而没有对手的迎击、接触承受、胸肩／头的后随与撤步，无法判断一个 exchange 的重量和力度。
- 88m QA 远镜头、缺少地面纹理及小手部像素使接触和指形难辨。它们影响判断，不能当成修动作的办法。

## 已实际观察的 TV 依据与边界

私人参考是 TV 第 2 话初号机反攻萨基尔片段的接触图，来源登记为 [Sakugabooru 211172](https://www.sakugabooru.com/post/show/211172)。实际观察位置：首排前部的脚掌压地／脚跟离地，中排迎击后压上对手身体，底排一手支撑／一手抓核的职责。参考图只在私人分析目录，绝不装入 runtime。

这些镜头支持紧缩预备、明确足部承重、身体与双手不同职责，以及近身压迫。参考中的倒转接近仍按用户要求取消。新普通拳 exchange 是原创重编排；不伪称这些完整拳段在上述 TV 片段逐镜头存在。当前先做不杀死使徒的一次完整逼近与反击，暴走／抓核／死亡收尾在此基础上另作完整段。

## 第一版 B 已再次失败

已实际生成第一版 8.1 秒 B 与可编辑 `.blend`。负责人抽看 1／3／5／7 秒四帧后明确仍为视觉 FAIL：初号机几乎始终直立、髋胸力量线不清、伸手慢推、后段长停顿，使徒两臂僵尸式前举，手指也没有形成拳掌剪影。此段保留为制作负例，不再晋级。

## 第二路：实际视频搏击数据已导入

实际尝试了 [FreeMoCap 作者公开样本](https://figshare.com/articles/dataset/FreeMoCap_Sample_Data_-_2022-09-19_16_16_50_in_class_jsm/22680424)。1108 帧关键身体点只有 16 帧全有限，两手与身体同时全有限只有 2 个单帧；它不是 fight 段，只能记录绑定／缺失负例，不能当本段战斗素材。

后续实际取得 [SMPLOlympics 官方视频 Boxing 样本](https://github.com/SMPLOlympics/SMPLOlympics/blob/master/download_data.sh)。作者 [HumanoidOlympics 页面](https://humanoidolympics.github.io/)把它列为视频估计后经运动模仿细化的数据。下载件 `video_boxing_afterproc_upright.pkl` 为 1455828 字节，SHA256 `aec7669699a69a2fafd4442c08b007b6fd946847a62f47ab06cf5ee9e5496096`，解出 8 段 30 fps、24 关节的完整数值动作。使用仅接收数值 NumPy／CPU tensor storage 的读取器，拒绝任意 pickle 全局和 object array。不是 Move／DeepMotion 付费服务任务。

用作者发布的 neutral boxing MJCF 还原实际 FK，验证局部／全局旋转链（最大误差 7.88e-8）；八段所有重建点有限。选出的 `data6` 右手反击是原生 89 帧：实际导入 Blender，真实导出 FBX 和 BVH，再导入 FBX 全帧核对，关节世界误差最大 1.23e-6m。原始 `.blend`／FBX／BVH／数值／回读报告都在 `combat/tv_exchange/video_source/boxing`。该源没有手指、实测 COM 和接触冲量，不能冒称完整手捕或物理力量保证。

## 新连续 exchange 制作

新世界目标段长 3.6 秒：受控进入 → 使徒主动右手迎击 → EVA 左手拨挡 → 足后跟起蹬、髋胸旋转蓄力 → 右手短促反击 → 使徒胸肩压缩与头部延迟、撤两次重新承重 → EVA 后足随步回收、恢复守势。源的约 5 帧快速上冲保留其短促节奏；不再用 8 秒慢推和长停顿填长度。

源 body FK 提供预备／反击时机和上下肢的实际空间方向；EVA／使徒的肩髋 socket、各段长度、掌／脚表面独立重建世界目标，再用原生 IK 求解。躯干目标按自己的骨架比例重新定义，共同接触目标使两个角色的手／实际使徒胸部表面一致；未逐骨复制 BVH 旋转。手指由本机实际掌长／掌宽／掌法线和相连指节制作完整握拳，源本身未包含手指。

先制作世界 root／骨盆／胸与头的动作线、真实脚掌和手接触目标；控制点按实际关节长度和模型表面建立。根端和 COM 在预备／接触／恢复中的路径有明确职责，不能再为 IK 随帧降低骨盆。接触前的加速、接触短停与接触后的恢复分开制作；使徒反应与攻方用一个共享时间轴。

实际使用已安装 Blender 5.1 的原生 armature／两骨 IK／目标和 pole，禁用 stretch。真正的 elbow／knee socket 作为骨头起点，不把 Gecko 的 forearm／shin 渲染 pivot 冒充关节。可编辑的世界 toe／palm／COM 控制曲线留在 .blend；求解后的 deformer 矩阵再转换为游戏骨架的局部 rotation 和同心 offset。整个过程只用当前原始 mesh／rig 的比例和绑定校准，不复制 BVH 逐骨旋转。

脚接触窗口由这段的世界足轨迹、低速支撑和手工逐帧标签建立；Heel 可围绕 toe 滚转。手目标取实际掌／拳面，使徒胸部目标取保存后实际 DQ skin 表面点。导出后重开 .blend 验证 evaluator、再以输出文件重新构造 pose／mesh；几何可达、关节连接、接触距离和按当前物理 profile 估算的 COM 仅是制作门槛，不等于实测 COM 或力量仿真，A／B 实片仍由用户判断。

`counter_v2` 的实际整张皮肤 QA 暴露了源绑定的第一处偏差：萨基尔脚底后跟顶点约各 0.498 权重给 shin／foot，刚体脚最低约 -0.002m 时，真实 skin 最低竟为 -1.8853m。停止其无效全片渲染并留 `skin_first_offset.json` 原负例。`counter_v3` 仅生成私有新 mesh 候选，足底／踝下由 foot 承载，踝上平滑过渡；1726／31392 顶点权重变化，UV／拓扑／骨索引不变，原始 mesh SHA `c7a84d505921b787bae4ab86897f9812782a906f4232b55fe779b028791ef0f9` 未写。新 mesh SHA `23c4930fa0f84ac9ed4c6d20b31801c1d819acbda0baf38f6b9d11f9cac159d0`。相同世界动作的 actual skin／whole-mesh 最低 -0.00205m，仍只作候选几何证据。没有整体抬根或让脚跟随 root 浮起。

Blender 的 [IK constraint 文档](https://docs.staging.blender.org/manual/en/latest/animation/constraints/tracking/ik_solver.html)是本段实际约束接入依据。[Disney 的动画制作说明](https://disneyanimation.com/process/animation/)支持以预备、时机、动作后随和清楚的 staging 制作表现。Daniel Holden 的[原始脚锁定说明与实现](https://theorangeduck.com/page/inverse-kinematics-foot-locking)指出输入运动应尽量保留、接触不能只靠高度、下拉骨盆会破坏腿的轮廓；此处用于重新定义 toe 目标和手工接触标签，不能因为引用就声称 AAA 品质。

## 2026-09-30 晚：独立复核及首次实际皮肤不一致

接手后独立查看 `counter_v9` 的开场、蓄力、接触与复步，仍为视觉自审失败：双臂前伸、击后直臂停留以及复步腿线拥挤。当前 v9 起的实际制作脚本已经改用 `data7`（148 帧，EVA 取 72→132）与 `data3`（119 帧，使徒取 45→100）。此前 `data6` 的 89 帧导入／FBX／BVH 回读是真实早期试验，不能作为当前两角色动作来源。data7 已有独立原始 `.blend`／FBX／BVH，FBX 重导入关节误差最大 1.2503e-6m；两源均没有手指捕捉。

v10、v11、v12 保留为不同缺陷的失败候选。v10 的守势与立即收拳修订不等于 EVA 艺术通过；v11 实际左脚复步末端 hip→ankle 为 26.1305 格，而实际两段腿长总和为 25.2448 格，目标超达 0.8885 格。v12 缩短复步后，开场后脚仍因忽略约 4.4 格的 toe→ankle 偏移超达 0.4761 格。v13 重新布置初始后脚和复步落点，固定根部制作曲线，没有以逐帧下拉骨盆补可达性。其完整 109 帧 actual skin／骨架门槛与正常速度连续片分别保存；当前所有版本仍无视觉或用户通过。

`export_tv_exchange_r44.py` 将共同世界阶段 root／yaw 从局部 pose 中只移除一次，导出原生 quaternion／offset 格式后，以既有 `validate_combat_bundle_r44.Pose` 独立重载。v13 骨矩阵误差最大约 1.02e-5 model units；该私有 109 帧文件不是 691 帧的 FirstBattleClip，未装入任何 runtime loader。髋膝踝、手指的连续性单列，不因骨矩阵一致就推断皮肤或动作通过。

全顶点比较找到三种蒙皮求值差异，但必须区分实际 dispatch：同一 v13 骨姿态，Blender preserve-volume skin 与 `LocalTriangleMeshLayer.skinAuthored` 的 dominant-influence DQ 规则最大相差 **2.7029 格**。此比较不是萨基尔实际 renderer；原负例另存 `counter_v13/dominant_first_mismatch.json`。萨基尔注册实际经过 `ClientEvents → HybridAddonRenderer → RiggedAngelLayer`，weighted skin 加载成功后屏蔽 LocalTriangle 回退。`RiggedAngelLayer` 以首 slot 为 quaternion reference，且原始 31392 顶点没有一个首 slot 为最大权重，12 个首 slot 为零；sole 候选保留索引次序后有 1522 个首 slot 为零。离线重放该首 slot 规则与 DCC 最大相差 **9.1985 格**。三算法、vertex 15592／4184、权重与坐标分别保存在 `export_skin_readback.json`／`influence_order_audit.json`。这些是离线规则比较，仍不能冒称 v13 原生实际绘制的第一处偏差。

Blender 5.1 的 [add_weighted_dq_dq 实现](https://raw.githubusercontent.com/blender/blender/v5.1.0/source/blender/blenlib/intern/math_rotation_c.cc)按累积 quaternion 选择半球。独立重放这一规则与实际 DCC mesh 误差约 3.61e-5 格。EVA authored seam 的 dominant 规则与使徒首 slot 规则分开记录，不预设它们应该统一，不改生产求值来让离线指标通过。还须按实际资源 ID／解析 SHA、实体状态、wrap 与 grounded 分支实测真正 renderer 输出。

本轮保持生产求值，`replay_exchange_native_skin_r44.py` 在私有预览对所有 109 帧重放导出姿态与使徒首 slot DQ 算法，保存 `first_slot_skin_preview.blend`；dominant 比较另存 `dominant_skin_comparison.blend`，历史命名 `native_skin_preview.blend` 也只是 dominant 比较，不能称原生对应预览。三者保留完整 mesh 检查及未剪片。原始 mesh、绑定和 Java 不因该试验改写。算法重放仍不是运行中的 Java／原生 GPU 证据；EVA 当前 DCC 为 rigid 部件，晚期真实接缝未在此宣称修复。预览合同还须覆盖全部 weighted 角色、inner proxy、倒地及大幅扭转。完整初号机／萨基尔自由攻防、五机全状态与真实客户端最终顶点仍未关闭。

## A／B 与当前所有权

A 保留用户否决的冻结原片，同时增加实际 video source 原始 armature 回放；它们分别标明来源，不能混为同一原生最终像素。B 为重新制作的完整二人 exchange。首轮固定三分之四全身机位，不用剪辑／摄影／粒子掩盖问题；另输出侧面接触及手部近景。

施工仅在 `artifacts/rebuild_r44/combat/tv_exchange`；源码工具和原始 .blend／控制曲线／导出矩阵／回读报告都留可检查。Java、世界、打包和提交仍由负责人统一队列；旧签名资源不覆盖。当前只有方向和制作源，尚无新的 B 片通过，低姿态与五机／使徒／地形推广仍未完成。
