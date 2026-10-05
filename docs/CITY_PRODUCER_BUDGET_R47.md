# R47 城市 producer 剩余成本与只读预算修补

城市总体性能继续开放；本次只改源码，没有新增 JVM、原生行程、碰撞 probe、SHA 套件或区块扫描。联合编译和是否需要新行程由主代理统一安排。

## 已有行程与可证明的成本

实际行程记录为 `artifacts/rebuild_r47/native_qa/actual_release_session_before_fix.json`，归档日志为 `artifacts/rebuild_r47/native_qa/faults_before_final_release/release_before_precise_navigation.log` 的 endpoint/WAL 两行：312→0，96 对象，1,534,193 次完整 NBT 世界写入，171.684 秒；durableIO 8430.233ms，ledgerIO 1017.8263ms，reload=0。这些记录没有逐阶段完整计时，不能据此声称已测出耗时最长的阶段，也不能将峰值 816.1598ms 唯一归给 SPAWN 或内存。

本次仅只读实际安装拓扑的一份元数据文件：`artifacts/rebuild_r47/native_qa/game/saves/SEELE_R47_RELEASE/dimensions/projectseele/geofront/data/projectseele_city_rigid_topology_r45_8246338109520.dat`。由全部 96 个原生塔的 footprint、高度与端点坐标得到：

- 完整 body 棱柱总计 2,066,787 格；PREPARE 源、目标双读总计 4,133,574 格。
- 街面 footprint 总计 34,881 格；另有实际初始图像逐格复核，这些工作未包含在上述双读数中。
- 最大真实端点距离为 181 格（塔 15、43），原 `.25` 策略需要 724 tick；20TPS 时为 36.2 秒。状态端点标签 312 不能当作每塔物理距离。
- 原 4096 扫描/tick 的硬顶，仅 body 双读就至少需要 `ceil(4,133,574 / 4096) = 1010` tick，20TPS 时为 50.5 秒。逐塔边界、等待 Fold/WAL、街面与初始图像复核、8ms 限制和实际服务器超时均会增加耗时。这是源码与当前拓扑共同证明的调度下限，不是新增运行测量。

因此只读生产扫描的固定 tick 上限是明确的大项；8.43 秒耐久 I/O 和零 reload 不支持把剩余慢速主要归因于反复读取恢复文件。仍不能用下限替代实际逐阶段排名。

## 本次源码差量

`CityCreateDistrictR45` 为 PREPARE 单独设置 `PREPARE_READ_LIMIT=16384`，原 8ms 时间预算继续在每次迭代前检查。源、目标、街面、真实初始图像均仍逐格读取实际世界、校验完整 NBT，原后台 Fold 与全 96 耐久逆向屏障保留；只读格数不再与世界写入的 4096 操作上限绑定。OPEN/DETACH/PLACE/COVER 与 RECONCILE 的 4096 上限、机械速度、身份、设备/地形碰撞和 endpoint 保存屏障未改。

`Plan.validateOperationSequence()` 的完整初始图像摘要复用每塔一条 Data/Digest 输出流及每塔 BlockState→NBT 标签缓存，沿原 LinkedHashMap 顺序逐格编码位置、状态和完整 BE；摘要内容与校验仍保留。它消除与此前实际初始摘要相同的每格流/状态树重复创建，不改变 WAL 字段或格式。

静态差量已回读；本次尚未联合编译及原生复验，不能宣称实测加速。只读 body 双读的格数硬顶下限变为 253 tick，但当 8ms 时间限制先触发时，仍按真实工作时间 yield；该数值不是预测行程耗时。
