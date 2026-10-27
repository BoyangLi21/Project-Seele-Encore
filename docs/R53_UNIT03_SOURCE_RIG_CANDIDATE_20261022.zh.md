# 三号机：原比例独立骨架候选，2026-10-22

本批已经做出隔离候选，尚未安装、替换 UN01、启动客户端或修改存档。**候选目录为 `F:/eva/artifacts/r53_repair_20261015/model-precision1022/unit03-rig-v7/`。** v1–v6 是保留的迭代工件，不能作为安装版本。代码工具是 `tools/build_unit03_source_rig_r53.py`；没有修改任何共享 Java 类或 carrier/world 代码。

## 实际完成

- 从已验明 ZIP 的原 OBJ 生成 3,909 个唯一面。原文件 4,627 面中有 718 面完全重合的第二手臂别名；去掉的只是这份重复别名。没有减面、细分、RBF 塑形或背部开洞。
- 保留原比例，统一缩放到现有模型高 192。原手、原背甲、法线、逐角 UV、面序均可通过 `SOURCE_FACE_MAPPING.json` 反查。两张 512×512 图片并排成 1024×512 图集，UV 只做可逆仿射变换，原像素不重绘、不减清晰度。原材质 alpha 均为 255。
- 用源模型测量点建立 107 骨的 rig4。肩、肘、腕、髋、膝、踝位置跟随三号机；命名和主要父子层次沿用初号机。新增真实肘、膝 socket 标记，取消初号机用于补偿错位铰点的 lower-bone 平移。
- 原卷曲手采用独立 30 指节。指根平面和纵向由原模型的指根/腕测量点确定，局部弯曲轴按各段方向重建；原始卷曲姿态是零位。初号机动作意图转为受限增量，不再把其绝对屈曲角直接叠上去。手部面数 522，仍为原始表面。
- 15 个物理体的中心、绑定、关节、凸包、面方程和尺寸从三号机重新计算；肘膝屈曲零点由其段向量推导。只保留原质量及锥角政策，没有复制 rig1 的绑定、关节位置或恢复动作。脚底支撑和 rig_support 同源生成。
- 对 idle、walk、run、rifle_stance、r32_jab 做了有限重定向候选。身体运动按肢段基准变换转角增量；站立、站姿基础、出拳检查中的双脚用各自完整足面求接触目标和双段 IK。它们是审查素材，**不代表五个动作库已经游戏验收**。
- 输出资源包 `unit03-source-keypose-resources.zip`、运行数据覆盖层、明确的 `NATIVE_KEYPOSE_SELECTION.json`，以及小型 CPU 检视图 `KEYPOSES.png`、`SOURCE_AND_HANDS.png`。已经实际看过站姿、抬臂出拳、正背侧及原手/有限握拳/有限张手图。没有运行 Blender 大渲染。

## 离线回读证据

`OFFLINE_GATES.json` 记录了导出 JSON 回读，而非只检查写出前数组：

| 检查 | 结果及边界 |
|---|---|
| 原面覆盖 | 3,909 面，每个源面恰好映射一次 |
| 位置回读 | 最大误差约 3.55e-15 模型像素 |
| UV 反算 / 法线 | 1.11e-16 / 0 |
| DQS 源站姿恢复 | 最大误差 3.55e-15 native 单位 |
| 八种抽查姿势的焊接缝 | 最大约 1.78e-15 native 单位 |
| 物理关节与新 rig 枢轴 | 误差 0；旧 rig1 关节复制负例最大错位 0.0980 物理单位 |
| idle / rifle_stance / jab 双足 | 302 / 362 / 242 个足接触求解，均可达；最大足面误差约 7.45e-13 native |
| 通用保留检查负例 | 实际篡改一个顶点、删除一面、修改一个 UV，三份内存副本均被同一检测函数拒绝 |

足接触的通过仅证明给定帧的足面接触高度和端点可达，不证明滑步、全身体碰撞、低姿势膝盖地面接触或关节角美术合格。首轮只全局抬升导致另一只脚悬空，已经在 v3 之后改成双足独立目标；这个事实保留在迭代工件中。

## 原生临时演员前必须处理的隔离点

1. **独立手合同路由。** 目前 `EvaAnatomicalHandsR45` 的多个实体入口仍取 `e.getUnitVariant()`。UN01 的这个值会选 rig1，而 body 的独立键是 rig4。应集中新增实体手合同键，只对 `usesUnit01SkeletonR53(e)` 的 UNSerial=1 取 `EvaBodyPose.rigKey(e)`；其他机型保持原合同。候选手合同在 `assets/projectseele/hand_rigs/unit04/hand_rig_contract.json`。不能覆盖 unit01 的手合同来绕过。
2. 同批核对 `EvaPoseGraph` 的手骨 owner 列表、`EvaCannonContactRigR45`、`EvaAnatomicalHandsR45` 内自然携带/腕对齐/选姿/接触矩阵等读取路径，以及 `CombatMotionResourcesR44` 手合同指纹集合。后者当前只纳入 0–2，需要明确纳入被选中的 4。资源包不等于类路径合同；原生审查需配置独立合同路径或使用受控候选运行目录。
3. **捕获 rig 身份仍严格匹配。** 现有 rig4 的 `eva_locomotion_capture_r44_4.json` 属于旧 UN01。`EvaCapturedLocomotionR44.validateRig` 会因新骨架而拒绝，不能放宽检查或把其 rig_contract 改名蒙混。临时演员阶段使用独立捕获目录，保留其他键的原文件、暂不纳入旧键 4；完整步态另做真重定向。
4. 资源 body/geo/动画/贴图可使用现有 `LocalVisualAssetFingerprint.matchesSourceSurfaceR53` 的严格哈希入口。候选已带 `eva/source_surface_r53.json`，无需放宽高精模型校验。
5. `projectseele-local-maps/` **只是三个文件的候选覆盖层**，不是完整 combatBundleDirectory。对冷冻结的完整审查实例做受控覆盖并重写统一 manifest 后再使用；保留其他机型和萨基尔原文件。严禁把这个不完整目录直接设成完整运行目录。
6. 先只用临时 UNSerial=1 演员审查源站姿、idle 第 0 帧、rifle_stance 第 0 帧基础姿势、jab 中帧和手近景。`NATIVE_KEYPOSE_SELECTION.json` 指定了帧，不是任意阶段截图。武器 IK 没有在离线图中叠加；图中的 rifle_stance 是基础站姿，不能叫作最终举枪姿势。

## 尚未关闭

- walk/run 当前 donor 中含 `r48_upper_body_only` 片段，所查帧 `foot_contact` 全 false；零足接触检查不是“通过”，完整步态、步长和落足时序仍需重定向。候选中明确移除了 rig4 旧 locomotion stride 合同。
- 三号机全部战斗、处决、失衡恢复、爬行和武器握持尚未验收。物理恢复字段刻意不复制 rig1；临时演员不得触发其恢复流程。
- 原背部保持完整外观；插入栓通道、背盖铰链和供电口还需在本体上另量。旧 v11 通用圆洞/盖板继续拒收。
- 手源拓扑本身为低面模型，522 面不能靠绑定变成高精雕刻。现有独立局部轴和受限控制可以审查，完整张手、拳头接触及精确握枪尚未承诺。
- 未接触实际世界、UN00、已交付步枪/Ramiel，也未重新构建游戏。实际 UN01 仍是原 Tripo 槽，三号机替换交付状态不能关闭。

复现（在源 checkout 执行；`--out` 必须是新的目录）：

```text
python tools/build_unit03_source_rig_r53.py --source F:/eva/artifacts/r53_repair_20261015/model-precision1022/v1/unit03-source-preserved --old F:/eva/artifacts/r53_repair_20261015/models1020/unit03 --client F:/eva/artifacts/r53_repair_20261015/client --out <fresh-output>
```

依赖沿用现有 NumPy、SciPy、Pillow；本次没有下载或安装新包。私有模型、原贴图、生成资源包仅留本地工件，源仓库只增加工具与说明。
