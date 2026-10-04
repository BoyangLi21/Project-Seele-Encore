# R45 金字塔与观察廊完整组件复核

本轮只读冻结 `R45_source_candidate_20261003_v4_01/world`，未启动Java、Gradle或Minecraft，未写世界。最终离线成果为 `artifacts/rebuild_r45/pyramid_components_sol_v1/frozen_audit_v7`，不是已安装或原生通过。完整1736文件以前后两次inventory/SHA对照City `qa_copy_revision_v1/copy_plan_v2/copy_plan.json`，全部保持原字节。

527个null节点已逐个回读并按来源分类：255为完整退休前横廊的旧导航行，162为退休前勤务架/旧插栓孔框的旧行；75为闭门的最高密室正常楼面；29为完整密室边墙旧行，1为原内侧读卡器，1为已知原生书柜实体障碍；2为真实电梯外呼按钮固定背衬，2为上观察廊实际MTR双格出口阻挡。退休导航行不会变成填地许可，密室墙、读卡器、书柜与固定按钮背衬均保留。书柜四朝向原生shape由旧 `fresh_chamber_book_v4` 真实native2599捕获；City核实旧/当前v56 `DeadSeaArchiveBlockR45.class` 字节SHA相等，本工具也回读当前class与该旧库4key/north6AABB。旧world库未合入4key，新派生shape/导航由City单独出新epoch；该点不能填地。root的FreshProbe新geometry补丁已应用并compile v56，新probe未执行，旧geometry有效继承和新probe执行状态分别登记。

50个原登记房间覆盖8个实际层高，共38724个完整脚印坐标、29697个实际承重点；这些承重点全部有指向本层真实电梯的派生行，未借另层电梯作为本层根。扩展连接廊后逐格复核50738节点及全部邻边：50668为当前静态承重，65为原实际台阶、3为闭合滑门孔、2为固定call背衬。原两扇手动门形成两条真实薄隔挡，派生next均没有穿过它们。原生形状正确顶面处理后没有未分类临空口；这不代替实际玩家台阶、门、设备、边缘推动或生命周期通过。

三处旧投诉使用同坐标回读：X105旧扶梯伴随墙体区域当前完整为空气；X86/Z-270和-269的双格出口全高均开；95/-442/-44的原南边界现被连续本层新楼面跨过，没有按旧照片在通路中重放栏杆。完整旧状态见 `three_reported_regressions_actual.json`。

## 已确认的6格候选与复发源

通用检测检查12条登记步道的实际双格原生flat MTR单元，在原冻结图只检出X98/99、Y-368、Z-213上方的两个实际阻挡。六格Y-367..-365墙板由已验证的 `hangar_upper_enclosure_v2/common_upper_pressure_envelope/applied_20260930_182259_771171` 原收据及原ops证明为本生成器air→shaft_panel所有权；当前完整state/NBT与其源owner一致。

精确候选仅把这两格完整3米出口的6块墙板还原为空气，保留Y-364以上头梁、压力围护、原MTR全state、地板/结构层、全部BE及人物/设备状态。`forward.jsonl.gz`、`inverse.jsonl.gz`与positive mask逐格配对。相同检测器对纯内存候选由2个阻挡变0；原MTR与普通地板之间的1/16米实际高差仍需原生玩家验证。

生成修复同时接入 `tools/plan_hangar_upper_enclosure_r44.py` 与 `tools/plan_factory_r20.py`：共享实际native九点bearing判据，区分flat MTR/既有moving_walk的.9375顶面与普通完整楼板，不只按普通地板名字保护。保存整列楼面和3米头部空间；shape未知时HOLD。原R20模板对现有R29/readonly世界的退休guard保留，未执行整R20生成或apply。旧类型过滤在原冻结图跳过两格实际MTR，新保护覆盖六格，当前冻结源码证明在 `source_recurrence_regression_v2/regression.json`。

## 旧原生图的右侧控制台间隙

root的新图 `space_photos/platform_identity_v57/20261003_124055/personnel_draft12_observation_relation.png` 来自旧run R45 review，相机脚位90.5/-367/-271.5。对应当前候选完整实读为 `observer_old_photo_current_readback_v2`：12186个观察/控制/东脊/原-369过渡列，北侧控制带1778列；不是只检查左侧通道。

两处台间隙X-1..19、X41..61，Z-284..-274各231列，共462列，在Y-368有完整原生碰撞楼板，在Y-369有连续结构层，全部九点承重。控制带1542个实际可站点能从真实西梯-29/-367/-285接近。完整5×125列前廊与125列真实半米观景台均保留。15个边缘候选全部是两处实际原电梯保留域，原低-369房间窗框/墙顶不当作-367公共楼面；未针对旧图提出楼板或栏杆重复施工。

root合入必须在真实目标关闭并有新的checkpoint/lease时重新比对全部旧完整state/NBT。最终交付副本需回读同批派生shape/导航及设备数据，再实走全宽、台阶、门洞和边缘。当前所有功能、视觉及用户认可仍未关闭。
