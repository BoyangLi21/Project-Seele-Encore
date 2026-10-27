# R53：零距离取消回库的路线占用修复

2026-10-22。本记录只覆盖“出发起点取消后原位回库，机械收尾完成仍残留路线占用”的独立缺陷。候选 V16 已通过这条原生复现；背部导轨、普通非零行程和最终交付验收仍另行进行。

## 原因与修复

取消点位于出发路线第 0 段、进度 0 时，对应逆向路线的最终端点。旧 `reclaimCancelledContinuousR52` 无条件生成 `HOLD`，后续没有剩余行程推动它变为 `COMPLETE`；`FINISHING` 又忽略 `releaseCompletion` 返回值，公布 `PARKED` 后仍占用资源和原机、原栓、驾驶员。

修复仍执行原身份、完整路线占用及原生恢复几何检查；只有精确逆向最终端点生成 `COMPLETE`，保留全部租约直至真实机械收尾。中点仍为 `HOLD`，非法或舍入成端点的进度拒绝。零距离恢复按合法 `RETURNING → FINISHING` 转换保存；收尾必须持有完成凭据并成功释放，才可公布 `PARKED/DEPLOYED`。没有修改路线、几何门槛、机体 UUID 或平衡数值。

## 原生证据

私有证据目录：`F:/eva/artifacts/r53_repair_20261015/rear-rail1022/native-zero-v16-a/`。复现助手仅调用正常 `prepare/cancel/recover`，每 tick 观察真实状态；不直接写实体 NBT、时钟、存档，不创建障碍，不跳过几何。若未捕获零距离窗口则报告 `not_reproduced`。

| 证据 | 实际结果 |
|---|---|
| `03_observed_zero_distance.json` | tick 7005997；`Prepared=true`、第 0 段/进度 0；实际时钟距离 0、速度 0、Ticks 0。 |
| `04_cancel.json`、`05_after_cancel.json` | 正常取消受理；同 tick 进入 `CANCELLED`，EVA 与插入栓坐标与取消前完全相同；旧任务占用释放。 |
| `06_recover.json`、`07_after_recover.json` | 正常恢复受理；同 tick 进入 `FINISHING/COMPLETE`，逆向第 1 段/进度 1；仍保留 167 项资源和 3 个原演员占用。 |
| `08_parked_leases.json` | tick 7006734；`PARKED/COMPLETE`、`Finish=DONE`、FilledLayers 44、BridgeAmount 9；resources、actors、hardwareResources、quarantinedGround 均空。 |
| `09_second_prepare.json`、`10_after_second_prepare.json` | 下一次正常准备受理，新任务取得 167 项资源和 3 个演员占用；没有自动发射。 |

`result.json` 为 `passed`，总时长约 73.7 秒。76 条观察样本均保留原初号机 `66519c87-962b-4877-b553-f85cd3360a12`、原栓 `a5390e79-8d48-4edc-9076-81adef18f6cf`、原驾驶员 `76a86ddf-0aef-4b82-99e9-41d080e8ed30`；加载对象未替换，HP 始终 300。取消与恢复调用前后 EVA 坐标同为 `(30.5, -1062.0, 328.50000000000034)`；随后插入栓正常执行机械回收。

此窗口当时的等待原因是“同 tick 整组唯一最终提交未通过”。本次证明零距离回库与占用释放正确，**没有证明导致该等待的背轨首步提交已经修复**。

## 版本与剩余验证

当次实际客户端候选 JAR SHA-256：

`9fc1b5b76cf113156b79a7e5bbd09024a6c74bb2aa7e21dea0b60bfd72b7aa6e`

回读 `ready-client` JAR SHA-256 仍为：

`e9bf87c61168515f800ead71c41ee19479f9cbbfa9b34949713cc0c91762f2d3`

因此此时尚未晋升 ready 交付包。实际目录指纹为 `79b9660975694e39d19030f19a12e3165e39ded1d6d7c2030169965e6baa6c3b`。没有地图静态差量或导航缓存改动；正常指令产生了新任务 ID、准备和机械收尾进度，不能宣称玩家/实体/任务数据逐字节不变。

定向 `javac` 编译通过；`NervRouteCoreR52Test` 2,126 项、`NervRouteRuntimeStateR52Test` 52 项通过，覆盖中途取消、失败恢复、非法进度、精确端点、租约保留/释放、重复完成不释放新任务，以及 NBT 收尾状态往返。这些测试不代替原生几何或画面验收。

后续由整体工作补齐：普通非零出击/回库流程；本候选真实保存退出后的冷启动回读；背轨与完整路线的独立原生/画面检查；最终实际副本和 ready 包一致性。旧版本已写下的 `PARKED + HOLD` 历史记录没有被自动改写。
