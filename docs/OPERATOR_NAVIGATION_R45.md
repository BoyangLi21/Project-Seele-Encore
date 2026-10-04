# R45 登记人员区分数脚位导航接入

冻结候选为 `artifacts/rebuild_r45/pyramid_components_sol_v1/operator_navigation_integration_v2`。只读当前 sourcecandidate 与其完整1736文件基线；前后文件集和SHA均相等。当前图未绑定、注册patch未应用、native未运行；没有写world或启动Java/Gradle/MC。1格compact轿厢、6格MTR出口、18按钮仍安装false。

现 `NervWayfindingR24` 把节点、next和landing读取为`getAsInt()`/`BlockPos`，因此无法保留格栅分数脚位。其单步门/踏面提示也没有本登记操作区的完整owner、成对安全门、实际支架与机械状态契约。新 `OperatorNavigationR45` 独占review provider保持`Vec3`，不更改公共`Guide`类型或原143080图。root审核后明确不合入临时QA目标patch，避免玩家看到永远UNBOUND的目标；受控review使用直接diagnostic API。生产加载与动态目标候选另见 `docs/OPERATOR_NAVIGATION_PRODUCTION_R45.md`。

producer从当前登记元数据的202格栅建立节点，不从旧整数图筛选可接受坐标。六个scope包含202个完整0.6米脚印对应的实际native最高接触datum、291条原格栅邻边、12个门片车道连接及原本层公共接近。门外部分MTR承面是-394.0625，生成器按实读形状取值。所有202个节点的返回表均到原西侧本层层门(-28.5,-394,-284.5)；公共返回从不进入私有lane。原compact公共路径保留在scope，默认目标使用西侧层门，不能用接近路径证明已损坏compact轿厢正常。417旧空气/边界坐标的XZ与当前202格栅重叠0，全部未登记成私有或公共新节点。

`same202_old_failure_and_new_precision_regression.json`保留同一组202旧失败：旧图172个实际datum缺失；新浮点JSON往返精度损失0。各scope所有节点的有限返回链与公共边界已离线验证。静态全身扫掠采用较高endpoint datum，仍不等于真实玩家沿ramp/STAIR跨格移动成功；所有291边、12门车道及两宽度车道仍需root原生动作。新诊断永远注明`native_walk_proven=false`。

loader默认UNBOUND。绑定必须使用尚未消耗的root冷lease，包含当前provider与NervWayfinding源码及全部对应class、准确世界path/UUID/seed、当前元数据/形状/原公共图SHA。图放外部artifact，以独立path和SHA JVM属性载入，不新增world文件。已实际运行旧`native_ready_v2`绑定负例，因preworld receipt已经存在而拒绝，拒绝前后没有创建候选输出。运行中不重哈希region、实体文件或热world；共享已有preworld admission证明UUID，避免调用会创建/保存身份的SavedData factory。

运行时每次指引核实际脚底承重、精确下一节点shape高度、loaded chunk及entity section、下一段完整0.6×1.77米身体扫掠、其他人员和设备占用。操作区还核本机完整427-owner子集state/NBT、review/provider flags、实际唯一gantry、PARKED阶段、motion clock两端、四半门一致与OPEN。关闭门返回`GATE_CLOSED`且next为null；占用/运动/未知状态暂停可走提示。provider不调用会请求chunk ticket的prepareFault，不开门、不写块、不移动actor；原联锁允许真实worker从内部紧急退出的规则保持独立。资源身份按当前JVM/classloader缓存；图/metadata按server、ServerLevel、绝对root、声明path/SHA每40tick复核；停止server清除导航缓存和选择。

绿色inspection apron依赖`TvCageCollisionR44`真实no-save gantry/provider，保存PARKED或模型声明waypoint不能代替实际碰撞与返回路线。因此flags关闭明确`FLAGS_DISABLED`；即使flags启用且固定图已绑定，inspection仍为`DYNAMIC_ROUTE_UNBOUND`。没有把模型apr​​on投影转换成world地板或复活417旧点。

review接续：不应用`root_operator_dispatch.patch`，实际编译当前provider；新冷checkpoint/lease列入provider及原未变更NervWayfinding源码与所有其class，用于保持公共消费者身份。再运行：

```
python tools/prepare_operator_navigation_r45.py bind --graph artifacts/rebuild_r45/pyramid_components_sol_v1/operator_navigation_integration_v2/operator_return_graph.UNBOUND.json --binding <新冷lease文件> --out <全新外部工件目录>
```

输出`root_properties.json`提供同一次preworld lease的五个身份/图属性及两个真实provider flags。不能在已尝试或已热运行的旧lease上重绑定。新native同一组入口是`runtime_negative_cases.UNBOUND.json`，涵盖同202脚位、全部边及closed/split门、占用、运动、无/重复gantry、未知加载、形状变化、跨world/server、417空气及inspection flags/未绑定拒绝。root用`OperatorNavigationR45.diagnostic(player,false/true)`读取原生结果；临时公共目标注册不是review绑定前提，没有伪执行或完成receipt。
