# R45 直梯与 NERV 门禁验收接线

当前成果在 `artifacts/rebuild_r45/lifts_doors_lifecycle_sol_v2/HANDOFF.json`。本代理修改专属验收源码、滑门完整所有权维护与离线准备工具，未启动 Java、Gradle、Minecraft，未写任何世界、模型、动作、渲染或注册文件。root 编译及后续原生结果单独登记。

## 已接入的真实输入与失效点

| 源码 | 旧失效点 | 当前检查 | 结果边界 |
|---|---|---|---|
| `visual/LiftPassengerR20Review.java` | 固定历史 25 趟不能消费当前 90 个有向组合；真实 server 按键未附着到每趟 receipt | 接受显式 bound90 作业；每趟保留实际 server 外部呼叫及轿厢选择事件；按实际进入、运行、到层与完整承重退出才追加结果 | 未实测；原旧 25 趟路径仍可使用；90 趟局部窗口不计完整通过 |
| `visual/CandidateLiftTripCasesR45.java` | 只核对 90/7/24 数量不能证明全组合；同名假停层可掩盖缺失输入 | 7 个物理组与 24 个 controller/cabin 精确一一对应；集合必须等于各组所有 `from != to`；当前 native 注册菜单和运行时 stop 集合逐一相等；interface 真实路径和 SHA 固定 | 缺失、重复、不同列、未绑定、旧文件或 native phantom floor 均拒绝 |
| `client/visual/NervSecurityLifecycleR45.java` | 旧 `AccessR44Review` 只覆盖一个固定 reader，单点净空不能证明完整孔、最高卡或完整壁画回读 | 当前 5 个 reader 的原完整 NBT 及固定所有权字段；真实 client 视线/use、server事件、主副手、移卡取消；全宽/全高碰撞；真实九射线承重；普通120tick与最高200tick真实 deadline；占用过期安全；九格墙及原 Tree完整NBT闭合回读；书架原生 collision/outline | 独立 opt-in，不修改实际门控逻辑；679 个其他对象仍未验收；无卡室内救援、重载及双客户端仍未验证 |

90 组合分母为：地下都市2层、西观察2层、指挥后梯5层、司令梯2层、东梯8层、机库紧凑梯3层、地表梯2层；合计24停层、90有向组合。消费者不把 route 数量或静态导视当设备通过。

## 可执行准备工件

`security_job_v3/nerv_security_native_job.json` 是 5 reader /1261 action 的 **UNBOUND** 作业。`all5_reader_open_image_path_evidence.json` 用冻结 `R45_source_candidate_20261003_v4_01/world` 和其原生 collision 导出预检所有宽度通道及实际前后路线。准备过程只在内存中将明确9格 portal和完整原 Tree image设为打开映像，没有拆任何实际墙。每条宽度通道从固定读卡器重新刷卡再进入，避免七个独立通道的检查超过真实120tick普通授权窗；没有为QA延长生产权限。最高房内侧测试从外侧真实最高卡开门后步行进入，未以传送进入代替授权。

普通3个外门均覆盖原内部 release button；最高房内侧 reader 按用户要求仍需 tier3。实际注册只有 tier1 employee 与 tier3 highest 两种卡，tier2 标为 `NOT_INSTALLED`，没有生成伪卡或把数学权限表算原生结果。最高房无卡被困后的真实救援必须由另一名持最高卡的客户端从外侧授权，当前单客户端作业不能证明该项。

root 已将当前3个验收Java纳入v53统一编译，日志 `artifacts/rebuild_r45/motion/integrated_city_devices_encounters_v53_build.log` 为 `BUILD SUCCESSFUL in 49s`；精确源/class/log SHA在 `root_v53_compile_receipt.json`。这是编译通过，尚无设备原生通过。

后续源码编译由 root 执行：

```powershell
.\gradlew.bat compileJava --no-daemon
```

City QA正常保存关闭后，root需命名冷checkpoint，回读最新24接口，编译并冻结当前3个验收class与当前滑门Director，制作新的完整冷lease。`CityAtomicCandidateBindingR45`保持原字节；不得将热存档重新哈希后补签冷启动通过。lease的source_epoch必须纳入这4个Java源码及对应实际加载class。

新绑定与启动参数由以下工具准备；它不启动进程、不读region、不改世界：

```powershell
python tools/bind_lift_security_jobs_r45.py --binding NEW_COLD_BINDING.json --base-launch NEW_FROZEN_LAUNCH.json --interfaces NEW_24_INTERFACES.json --out artifacts/rebuild_r45/lifts_doors_lifecycle_sol_v2/NEW_BOUND_RUN
```

输出 `lifts90.launch.json` 和 `security5.launch.json` 为**两种备选**。每个冷lease只运行其中一个；保存关闭以后，下一批必须重建checkpoint/lease/admission输出，不能用同一旧receipt顺序启动两个任务。

避免自然autosave每次重做checkpoint的具体候选已在 `same_jvm_device_sequence_root.patch`，`git apply --check`通过，**尚未应用、编译或实测**。它只挂接专属消费者与新增 `DeviceBatchSequenceR45`：可选先等待本JVM新写出的City96/IDLE/声明depth完整PASS，再跑90梯；梯全部90/24真实receipt通过以后，保留同世界、释放按键并启动5个读卡器，最后正常退出。City quality作业必须 `stop_server_when_done=false`。同次原 pre-world admission记录保持一次，正常运行及autosave是该会话的实际新状态，不重新伪造cold epoch；独立JVM重启仍需新冷lease。

root应用并编译、冻结这份串接补丁后，可给绑定工具追加 `--sequence-devices`。若同时包含City predecessor，再追加 `--after-city-quality NEW_CITY_QUALITY.json --city-control NEW_CITY_CONTROL.json`；两作业必须绑定同一新cold lease，quality endpoint必须明确且不自动停服。输出 `city_optional_lifts90_security5.sequence.launch.json`。此spec需保留其原mode，旧 `run_bound_native_candidate_r45.py` 会强制改成city mode，不能直接用来启动该combined spec。

直梯模式仍为 `regionalBuild=r44-lifts`，增加 `r45LiftTripCases`、`r44LiftInterfaces`、`r45LiftOutput`；门禁模式为 `r45NervSecurityReview=true`、`r45NervSecurityCases`、`r45NervSecurityOutput`。全部带3个原 pre-world admission 参数。receipt必须是世界外的新文件，拒绝覆盖旧失败或成功记录。

## 生命周期与制作边界

当前单次功能消费者不宣称同JVM重载、冷重载、保存中断、断线或双客户端已通过。后续需真实开门期间中断/重登，在世界继续保持原UUID和完整门控/壁画NBT的条件下分别检查：移卡与离线在tick6之前拒绝；200tick到期占用保持安全；清空门洞后恢复全部10个image；内外最高卡均可重新开门；无卡室内人由外部授权同伴救援；外国完整NBT触发HOLD并保留修改。现consumer完成后会正常退出Minecraft，不能据此冒称同JVM复验已接入。

17组 command滑门、647个原下半门、15个root机械门继续保留原对象队列。普通下半门中632是MTR平台门、12是桥梁安全门、3是既有室内手动门；不得把632平台门换成通用门，也不得根据no-save实体文件数量漏掉运行时设备。root负责模型/动力扫掠与实际画面。

## 17组滑门固定输入候选（接续）

最新离线候选为 `command_controls_v3`，取代不完整的 v1/v2 候选。17个原owner及102格完整3×2孔全部保留，ID5/14两个原梯井手动门继续退出滑门所有权。共34个双法向侧主输入，并保留3个实际有效原登记按钮作为alias；静态差量为18格空气→石按钮，没有墙、背衬、楼面、台阶、门孔或既有按钮拆除。marker前后完整字节、逐格完整旧state/NBT、正逆18格和精确positive mask均在同目录；`complete_door_preimages.json`保留17组全孔及原登记输入映像。

原通用检测器在冻结原图 `other679_frozen_v4` 复现16个登记坐标不是按钮、16组缺双侧有效输入、4个登记输入缺完整承重操作点；同一个检测器对仅内存套用候选的 `other679_candidate_v2` 再检，这三类缺陷归零。`command_controls_v3_verify/verification.json`以前后两次1736文件完整inventory与SHA对照权威 `city_atomic_integration_r45/qa_copy_revision_v1/copy_plan_v2/copy_plan.json`，并验证37个完整输入/固定背衬、操作点及逆向回原映像。冻结源没有变化。

ID15的北侧接原梯段，脚位-414、门脚位-413；原楼梯与两侧柱体不是可填空气。当前平面三线检测仍将这个实际台阶接口列为未验证，须由原生玩家沿原梯段实际跨越、检查整个身体和占用闭合，不能用新栏杆、填平或仅静态数量宣称通过。632 APG的客户端叶片生命周期、12格栅安全门的实际承重、原梯井手动门、15机械门仍各自待验证。

`CommandRoomSlidingDoorDirector`增加完整6格state/NBT前检、marker拥有ID才可写、退役/重复/全孔metadata拒绝和20tick markerhash缓存；新marker还核对每个实际按钮与固定背衬完整state/无BE，按钮正常powered切换仍允许。新marker的红石开启只接受该门已验证输入，防止旁路把外国替换或邻近电路冒称原输入。旧marker兼容保留；新的37输入及当前源码尚待root编译和原生实际用键，不能把v53对旧三消费者的编译回填为此Director编译通过。

启动准备工具现在要求冷lease同时包含当前Director源码及实际加载class；已写出的preworld admission输出一律拒绝复用。City的新checkpoint/lease完成后才可绑定。root独占世界合入；静态18格和marker差量只能安装到与全部完整旧state/NBT相等的明确候选，并重新制作checkpoint/lease，不得将这些工件当已安装。

原生书柜geometry补丁为 `dead_sea_native_geometry_probe_v1/root_native_geometry_capture.patch`；root已应用并compile v56，新probe未执行。它调用注册north state的实际collision/outline API并导出toAabbs，不推测box；上下文明确为EmptyBlockGetter/empty collision context，不冒称实际房内回读。与此同时，root已发现旧 `native_shapes/fresh_chamber_book_v4` 真实native2599库包含4facing，City核实旧/当前v56 `DeadSeaArchiveBlockR45.class` 字节SHA全等；north6AABB最高1.31为有效继承。旧候选2565库遗漏4key，新派生shape/导航由City另出epoch，该点为已知实体障碍，不能填楼面。5reader作业的actual-context archive assertion与权限/完整生命周期仍未运行，不能把旧shape继承写成新probe或5reader已通过。

金字塔/观察廊的全房间、全宽、边缘与生成器接续见 `docs/PYRAMID_COMPONENTS_R45.md` 及 `artifacts/rebuild_r45/pyramid_components_sol_v1/ROOT_HANDOFF.json`。额外静态候选仅6格原生成器墙板，不改任何门孔、楼面或原设备。City实际窗口 `native_city_checkpoint_run_v6/native.log` 的12:17:14 unsafe damaged compact-cabin负例继续保留；City可启动不等于90pair轿厢可用，须窗口结束后由root按原冷controller/cabin证据调查。

TV制作依据保留在 `tv_appearance_handoff.json`。既有TV12封闭工具轿厢、TV22人员轿厢墙面与腰带、TV11 R07服务压力门分别限定用途；被误称为电梯的斜向连续踏阶图已排除。官方说明确认2015设置集包含TV制作资料，也夹含少量1997剧场版资料，不能将全册视为纯TV来源。[官方设置集公告](https://www.evangelion.jp/sp/news/det_11377.html)

前代理记录的静帧观察是有效继承，当前未重新观看完整TV片段；静帧不证明垂直速度、绳机、canon尺寸或门驱动。具体尺寸、native硬件与权限来自当前Minecraft设备，饰面与收纳结构由root原创制作，官方图像不写入项目资产。
