# R44 TV 湿舱机械候选

最新状态以本文末尾「v4 冻结与 I-girder 实施」为准。此前段落保留当时的候选及负例范围，不代表当前资源仍为 5e86 或壁面尚未安装。整座 TV 机库美术仍未通过。

负责人要求整座 TV 机库。当前原生全景仍为美术不通过，未获用户认可。`projectseele.r44TvCageReview` 默认关闭；原作图像仅在私有参考目录观察，没有进入模型或材质。Root 是唯一世界写入、构建、Minecraft 启动和打包者。

## 已安装候选与最新实机

`tools/build_tv_shoulder_shells_r44.py` 生成原创固定 gantry 坐标几何。实际三机原点 X 为 −11.5/30.5/72.5、Y=−442.96、Z=−239.5，前方 −Z。已安装 JSON SHA 为 `5e86fbef3adbb0d3df8ee4721f2789e3fb18542b41a29569e7dc3377375451d8`，含完整低位框架、肩外壳、承重座、斜台、圆轴和真实套筒前梁。02 右台独立缩至 3.30m，保留完整原东梯到达口。尺寸是实际场地和原片比例的工程改编，不是官方米数。

最新五张原生图在 `space_photos/tv_cage_locked_lens_vanilla_v2/20261001_022427`。真实三机均闭合，locked_cage 使用单独姿态归属；有效 FOV 已实测为 68/58。前廊改善，但肩外壳与实际身体的联系、整座壁面及机械层级仍需改进。−394 是工人维修廊，应看接触机构与控制器；−367 是观察层，应看 EVA 上半身。旧侧图不能把维修廊被承重梁挡住的头部视线算成上层失败，也不能据此拆承重。

旧六 pad 与修前 00/01 实际肩面相差约 0.10m，02 约 6mm；这不是闭合接触通过。完整失效的 legacy arm_guard/arm_rod 在 TV 候选启用时退役，不再保留悬离肩部的护臂。修后真实 20m arm/pylon 三角用于重新选择可接近的上外侧 facet。新六点、green clevis 与液压杆在私有 `hangar_shoulder_contact_v3` 和 `shoulder_contact_v3`，尚未覆盖安装的 pad 资源。

新完整 actualBody 三角已解除初号机后唇 UNKNOWN：301 个保守 bbox 重叠对应的真实 1240 胸三角 SAT 均为零。六壳与 2cm casting collider 的 121 状态扫掠均无真实身体穿插。`HangarMeshWitnessR44` 新增默认关闭的 `projectseele.r44HangarFullBodyTriangles`；启用时导出每个真正提交部件的所有三角，并核对三角数×3=顶点数。下一次实际采样后再完成肩面安装和全身扫掠。

## 物理与运行证据

`TvCageCollisionR44Mixin` 在具体 `Entity.collide` 调用点追加资源中的真实固定/动态形状。覆盖走路、跨步和落地；其他碰撞查询、原生方块 raycast、NPC 寻路与旧 nearestLift 缓存不自动包含设备。`TvCagePhysicalShapesR44` 已在实际三 gantry 上导出资源 SHA、UUID、closed 和世界 AABB；显式 QA 导入工具按三项身份变化失效。

最新原生 normalArmorStand 诊断三机均通过：无人释放允许、占用拒绝、清理后恢复、水平前梁阻挡，以及斜台落地/跨步。斜台期望值按实体完整 footprint 的最高支承计算，严格误差为零；原先按中心平面算出的约 0.067m 差值已确认是半体宽乘坡度，不是放宽阈值。它仍不是完整真实玩家、所有设备 phase、冷重登或多人通过。

旧 `actual_space_contract.json` 对方块的六处相交是保留人员廊下方的实际结构支座，须以原生成器的完整构件身份记录承重点；不能笼统报告世界零相交。新六 facet/外壳需重新检查完整 EVA、载台、插栓 121 状态、人员通路、控制器、支承与实际世界。冻结站立包络检查不代替运行状态。

## 前廊及镜头

`EvaHangarBuilder` 前横廊模板已从 −24 改至 −27，保留三排实际公共通路、MTR、完整 02 到达口及原功能身份。Root 已严格应用 v2 的 507 格正差量，当前 BE1 与 1124 依赖保留；收据在 `replay_tv_front_crossway_v2/exact_front_crossway_v2/applied_20261001_021207_244121`。18 条三列双向 native FakePlayer.move 在 `native_walks/tv_front_crossway_v2/20261001_021709` 全部通过。实际 client/MTR/所有控制和设备状态仍另行验收，不再用已施工前的旧 false contract 把候选循环扣住。

前镜头 position `[cx,-383.52266266158,-273.6]`、yaw 0、pitch 28.85533978、FOV 68；背颈 `[44.5,-377.72,-220.5]`、yaw 135.49587477、pitch 32.21036851、FOV 58；旧维修侧镜头 `[48.5,-394,-251.5]`、yaw 56.30993247、pitch −8.88013090、FOV 58。相机都避开实测实体方块。TV 有效画幅 X94..650/Y0..422；归一化投影仍有约 6.3% 残差，不能称同镜头比例通过，也不移动 actor 迎合照片。

当前橙红 LCL 材质由 root 负责。旧水位分析把 −399 方块层直接当作实际液面，尚缺 FluidState 高度实测，不应据旧自由高度数字抬水；紫红参考仅用于几何。前梁、肩台、身体露出与插栓净空须在同一实际镜头和真实液面下复核。

## 整座壁面候选

`tools/build_tv_wet_bay_lining_r44.py` 在完整实有压力墙上生成原创分层板、细缝、紧固件与小管束。私有 `tv_wet_bay_lining_v1` 有 537 块板/6 parts/15188 实测墙依赖；183 面遇到窗口、门、楼面或已有附属件而留空。−394 与 −367 人员层均避开。最大实际凸出 0.161m，扣 0.01m 检查余量后最窄原人员 footprint 尚余约 0.029m。

这些是未安装的侧墙候选，不能代替屋面、后门、观察窗、机械围护和完整岗位视线设计。JSON/GLB 与真深度 CPU 预览同源；完整设备开合/载台/人员/世界净空与原生全景仍待验证。整座机库的美术、完整生命周期、性能、重登、多人及最终交付副本回读仍未通过。


## 2026-10-01 最新闭环与待实机整景

上观察层 4436 格完整迁移已由 root 严格施工：原前界 Z−275→−267，连续五排同层通路加半米看台，保原观测梯、读卡器与 333 核心承梁。24 条全宽/梯返程原生路径通过，76 完整 chunks BE 在运行后不变；`tv_upper_observation_after_v1/20261001_064916` 六张实机图已证实三机头、胸与 pylons 可观察。仅这个观测目标通过，整座 TV 美术仍未通过。

这些图片里的巨大苍白双壁来自 R26 下移9m的旧纵向吊车梁，和后建的正确低轨同时存在。完整原 owner 1008 格分类为 912 EDGE、18 后继蓝色压力面及78已AIR；root已严格应用930格，18压力面恢复邻接透明窗，完整前后承梁、918实际低轨及屋顶吊挂保留。Java真实 top/web48tri 每bay对旧梁216相交、正确低轨零相交，退休后上梁零相交；121正常插栓/吊机四轮路径前余26.5m、后余1.7258m连续承重。

完整载台又检出两个真实负例，均已保留：旧底横梁对 deck 有102tri交叉；下沉后 carrier_clamp 在rise约.942..967仍穿前横梁。最终前座改左右outriggers和12.8m中央升降槽，后座/四柱保持连接，clamp±6.1m有.3m侧间隙。24个完整carrier来源的121rise复验均零交叉；人员、插栓121、真实世界和02原口零不当相交，六个原 cantilever 承点另列。

下一次可装整体资源在私有 `tv_cage_whole_candidate_v3`：cage SHA `af2f2657dd6d288be75b30dd58a74c2801a8438d80b8f16a3d852b29e41c94fe`，须配 pad SHA `a2e2fb6e12b48e3b5f4f702a30dec0576fd780e52b133d9292c2e2b9ab05e465`。包括真实肩接触、casting collider、U-base、壁面与细管束的35part/35component。`assemble_tv_cage_whole_r44.py` 会核对物理报告哈希后重组同一资源，不安装源资源、不写世界。墙面的15188实际依赖、C壳全部状态、完整crew、世界native形状和载台上下包络都已复验零冲突。

`TvCageCollisionR44` 已缓存part bounds，先localQuery拒绝，再只对命中的细箱生成世界形状；互锁先粗选真实占用者，无人时不分配全细sweep。原生出口记录实际候选箱数与平均/最近4096精确p95/最大耗时，body与全景snapshot查询分开。未用 Python 时间冒充原生性能。

新整体资产仍是未获得整景美术认可的候选。Root下一次统一安装、原生真实触点/占用/完整工厂生命周期、six上层/three维修岗位图片、冷重登和多人检查是必须后续；193400tri、8795已合并物理箱是否满足宿主性能也需真实计时，不能因功能计数而晋级正式包。

## v4 冻结与 I-girder 实施

上一版 af2f cage / a2e2 pad 已安装并取得 17 张实际图和原生运行证据，归档于 `space_photos/whole_tv_cage_and_native_maps_v1/20261001_075014`。原创壁面已可见，但苍白完整低轨抢主体，00/01 旧前维修视角被宽斜台遮住，整景仍为 FAIL。

v4 完整资源在 `hangar_machinery/tv_cage_whole_candidate_v4/tv_shoulder_shells_r44.json`，SHA `de2d938af77077807cc6cc75c6765bd31c969b98e04d48b33db6660e51426f32`，必须配原 a2e2 pad。35 parts / 35 components、193592 个三角和 8811 个存储碰撞箱包含不同机型，不能当作每次实体移动的工作量。已发布 v4 不再修改，后续几何变更必须另立 v5。

`v4/validation` 内冻结 23 份报告和源码，`hashes.json` SHA `a02958c0813c62a5f49be090d5ee0f86e929e3e48a1d5ce2cb9fc06484f6d94a`。包含完整接口、pad/fullbody、实际身体 SAT manifest、湿墙净空与 15188 依赖、六检修相机/路线，以及准确生产器副本。只重建六个完整固定件，普通斜台由 7.55m 收为 5.30m，接收筒、轴、栏杆和肋板同步，02 独立右台保持 3.30m。台底桥连接实有承柱，承重座改为完整翼缘/腹板/加劲肋。动件顶点与碰撞逐值未变，`revision_equality.json` 记录此关系，旧动件 SAT 报告不冒称新烘焙。

正确低轨 918 格完整 owner 已换成注册的六种 `nerv_crane_girder_r44`，Root 在 08:41 严格应用。完整现有 BE 与支承依赖保留。原生六态 collision/outline 已逐联合体核对，均为旧 fullcube 的子集；轮面仍为 Y−373，基座 Y−376，轨距、全长和实际四轮支承不变。六条原生绕行路线通过。换梁后的吊机/插栓完整生命周期和画面仍须实测，不能由精确子集证明全部功能。

六个实际检修岗位在原两排侧廊 Z−237.5、各 bay X±18m、feet Y−394，FOV 为整数 58。九足点、原操作点至岗位的完整往返路线均已冻结，未新增悬空控制台、未搬迁原操作点。旧 Z−251.5 是前通行角度；新岗位是否看清接触壳、ram 和实际安装关系，仍以原生图片复核，不能因 facet 被覆盖判通过。

af2 原生 server_body provider 354 次查询平均 35.019μs、最近 p95 53.7μs、最大 3274.1μs，12780 个候选细箱，平均约 36 个/次。该数只覆盖 provider 工作，不是完整 Entity.move 或全游戏性能。54 次缺 gantry 查询仅为诊断计数，未证明人员穿透；必须以明确应有平台的原生负例区分实体未加载、启动时序和无关查询，再决定局部处理，不给整个 bay 添加虚拟阻挡。

Root 已完成 variant0 真实 prepare→launch→recover→reboard→cancel，最终 PARKED 且 UUID 不变；该次采用 af2，发生于新 I-girder 施工前，只记录这段实际范围。v4、三机全状态、完整载台/插栓/吊机、真实玩家、冷重登、多人、整景美术和最终交付副本回读仍未全部通过。

此前显式未核的 carrier_ram_unit 安装变换已另行补齐，冻结在 `mounted_carrier_rams_v4_review`，contract SHA `79c0f3edc8099bee890123f73d35902036bcbeb86a276afff9a0b42e762cbb22`。按实际 renderer 的六 mount 公共 stroke 上限、64m rise 与杆长缩放，3×6×242 状态实际三角 SAT 为零；再用每顶点坐标单调性构造 54 个端点联合包络，各包络与所有固定构件均零相交，证明完整连续路径。对应 renderer、director 与审核生产器已复制冻结。这是实际源码变换的工程证明，不替代原生提交杆 witness 或完整运行。

## 生产器入口与准确复现

live `build_tv_shoulder_shells_r44.py` 不再有旧 v2 contact/body 或已安装 src 资源默认值。必须显式给出 `--contacts`、`--body`、`--out`；输出只接受 `artifacts/rebuild_r44/hangar_machinery` 直接下属、尚不存在的独立新版本目录，不能嵌入已发布版本。六个安装点必须含实际 clevis 和零 skin SAT 冲突，身体必须有三机全部原生提交部件的完整三角。可选 `--resource` 只能指定新目录内固定文件名，不允许逃逸到 src。`--check-inputs-only` 验证输入及目标但不创建目录、不烘焙。

live `refine_tv_aprons_r44.py` 也必须显式指定 `--source` 与新 `--out`，不能无参覆盖已发布 v4。这些 CLI 保护不修改冻结 v4 的旧生产器副本；它们是后来对入口的源代码修正，不冒称当时的生产源码。

准确 v4 配方使用冻结的完整 v3 af2f 输入和冻结的增量 refine/author 源码。`v4_reproduction_inputs_de2d938` 内 17 份文件逐项哈希，manifest SHA `4827da3c2a791c6dc33ad7aabf22754b2eb3c5dd8918a1835ccf2cbf90deaefe`；也冻结 parent 的 contact 0ee20f28、完整 body f6c5ee61 和 paired pad a2e2。增量配方不把这些 parent 测量假称为重新采样。

在 `D:/eva` 执行以下命令，目标目录必须尚不存在：

```powershell
python tools/reproduce_tv_cage_v4_r44.py --out artifacts/rebuild_r44/hangar_machinery/v4_reproduction_new_private
```

工具在新目录内建立独立工作区，运行冻结源码，检查 cage SHA 必须为 de2d938…，再复制准确 a2e2 pad。实际已在 `v4_recipe_native_epoch_check_v1` 执行，得到两项完全相同的 SHA；未改 installed src、Java、世界或 frozen validation。

后续新几何烘焙可以先仅预检冻结输入：

```powershell
python tools/build_tv_shoulder_shells_r44.py --contacts artifacts/rebuild_r44/hangar_machinery/v4_reproduction_inputs_de2d938/inputs/contacts_0ee20f28.json --body artifacts/rebuild_r44/hangar_machinery/v4_reproduction_inputs_de2d938/inputs/body_f6c5ee61.json --out artifacts/rebuild_r44/hangar_machinery/tv_cage_next_private_revision --check-inputs-only
```

移除最后一个 flag 才执行完整机械烘焙。这个产物仍需对应实际 pose/source epoch、壁面组装、完整净空、原生功能及美术复核，不自动覆盖或晋级任何旧候选。CLI 的 10 项负例/正例在 `generator_cli_safeguard_v1/receipt.json`，包括无参、src 目录、已发布 v4、src resource override、旧 contact、不完整 body、当前输入，以及 generator/recipe 嵌入已发布目录的负例。它们已对最终 live 源码重跑，每项记录对应 script SHA；所有负例未创建目标目录，installed de2/a2 与 frozen validation 完全不变。
