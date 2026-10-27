# 三号机独立骨架的原生审查入口

本批是隔离审查工具，未安装实际 UN01，未启动客户端，未修改世界或原机身份。最终构建与原生画面由主代理统一进行。原始表面与离线候选见 [源骨架记录](R53_UNIT03_SOURCE_RIG_CANDIDATE_20261022.zh.md)。

有效候选目录为 `F:/eva/artifacts/r53_repair_20261015/model-precision1022/unit03-native-review-v2/`。v1 已被 v2 取代，保留作差异诊断。底层完整源候选仍是 `unit03-rig-v7`。

## 允许的范围

只接受 `unit03_review_contract.json` 中唯一 UUID、UNSerial 1、EMPTY 冻结姿态的临时演员，且命令仅能在该合同的独立世界绝对路径运行。新 `unit03_source_review_r53` 标记必须与完整源网格、108 骨骨架、30 个手指关节、rig4 动作骨架、15 个实测物理体和全部文件哈希一致。原有共享标记本身不能开启 rig4 手部，也不会回退到 rig1 手合同。

开放六个固定姿势：`source_rest`、`hand_fist`、`hand_open`、`idle`、`rifle_stance`、`r32_jab`。三个动作姿势分别取已检查的 idle 第 0 帧、rifle_stance 第 0 帧和 jab 中间帧。手型 fist/open 单独检查；jab 使用源静止手型，避免把未验收拳型与身体动作组合后冒充已验收。步枪姿势只有基础站姿，没有枪、握枪 IK 或开火许可。

原生工具不构造地面、不传送或修改玩家、不删除无关实体、不寻找或替换原 UN01，不启动客户端。创建位置必须已经加载，维度限隔离主世界，避开 GeoFront 的 UN 设施和插入栓自动导演。右键进入该演员被阻止；演员无 AI、无重力、不可受伤，冻结姿势由既有 R30 同步通道发送。`finish` 只删除合同 UUID 且带本工具标签的演员，发现乘客会拒绝删除。

## 精确增量

修改四个源文件：

- `entity/EvaAnatomicalHandsR45.java`：按实际演员选择手合同；普通 0/1/2 保持原路由；rig4 须完整合同和唯一冻结演员。
- `client/render/EvaPoseGraph.java`：手骨所有权采用同一实际手合同。
- `client/render/EvaCannonContactRigR45.java`：采用同一路由，合同不存在时返回。
- `entity/CombatMotionResourcesR44.java`：只有显式审查模式加入 rig4 手合同和审查总指纹。

新增 `entity/Unit03ReviewContractR53.java` 与 `visual/Unit03SourceNativeReviewR53.java`。没有修改普通蹲起时钟/支撑、运输架或世界生成类。

包中内容：

- `runtime/` 是实际战斗库完整 28 项及清单；25 项原字节保留。仅更新 `eva_body_r44.json` 的 rig4 相关分支、`eva_gameplay_r44_4.json`、`articulated_bodies_r35.json` 的 models.4；身体其他分支及物理 0/1/2/3/萨基尔均回读不变。
- `hands/unit00`、`unit01`、`unit02` 的 `hand_rig_contract.json` 与当前实际 JAR 原字节一致；独立新增 `unit04/hand_rig_contract.json`。
- `captured/` 独立保存其他已启用捕获资源；当前实际客户端未启用该目录，因此此目录为空。明确禁止旧 rig4 捕获动作进入新骨架。
- `unit03-review-resources.zip` 共 9 项：pack.mcmeta；eva_un01 的 body mesh、独立 hand mesh、geo、animation、base texture、eyes texture；unit04 手合同；source_surface_r53.json。体表 3909 面、独立手表面 522 面，不删面、不变形塞入 rig1、不重画源纹理。
- `keyposes.json`、`unit03_review_contract.json`、`REVIEW_JVM_ARGS.txt` 给出冻结姿势、完整文件指纹、唯一演员 UUID、独立世界绝对路径以及所需 JVM 参数。

## 原生使用边界

需要主代理先统一 build，并准备合同指向的独立客户端/空白审查世界。目录与参数须原样成组使用，不能只把 9 项资源包或 v7 的 partial overlay 当成完整战斗库。不能给实际 `SEELE_R53_WORLD` 加这些 JVM 参数。

在合同规定的独立世界中，选择已加载的空旷位置后执行：

```
/seele unit03_review spawn source_rest <x> <y> <z>
/seele unit03_review pose idle
/seele unit03_review pose rifle_stance
/seele unit03_review pose r32_jab
/seele unit03_review pose hand_fist
/seele unit03_review pose hand_open
/seele unit03_review finish
```

工具不会自动切换视角。先检查前、后、侧面的源比例、背甲、手面完整性，再看有限姿势。实际渲染资源选择、手表面/关节接缝和光照需要原生画面证明；离线合同通过不能代替这一环。

## 已执行的验证

使用 JDK 17 独立编译上述六个生产类和合同检测器，输出到 `.Codex/unit03-review-compile`；通过，只有既有 ResourceLocation 弃用警告。未运行 Gradle，未覆盖 build/classes。

`CONTRACT_GATES_FINAL.json`：真实 v2 合同接受；以下 9 类独立修改的真实副本全部被同一个生产检测器拒绝：不完整运行库、实际世界路径、冲突的单文件 body override、geo/body 骨架不一致、混入旧 rig4 捕获步态、手合同字节被改、缺少手合同指纹、额外动作姿势、将 gameplay_admitted 改为 true。负例测试后副本恢复并再次通过。

`POSE_AND_PRESERVATION_GATES.json`：导出六姿势的完整 DQS 网格与 v7 检查网格最大误差 `1.25e-14` native units；非 rig4 的身体分支、0/1/2/3/萨基尔物理体及零/初/二号手合同保持不变。

v1 对接时发现原 NATIVE_KEYPOSE_SELECTION 将 jab 指定为 fist，但 v7 实际检查图的 jab 是源静止手型，导致局部手面偏差 0.637 native units。v2 把 jab 明确保持源静止手型，并独立提供 fist；该差异没有送入原生或实际存档。

## 未关闭事项

尚未原生看图；bounded-fist 仍偏弯指爪，不能标为拳击或握枪通过。完整走跑步态/接触、武器握持、背部插入栓功能、倒地恢复和处决仍需单独接入、验证。本批禁止据此宣称三号机已完成或安装。

可复现工具为 `tools/stage_unit03_keypose_review_r53.py`、`tools/audit_unit03_keypose_review_r53.py`、`tools/java/AuditUnit03ReviewContractR53.java`。所有测试输出、候选和负例都独立于实际世界。
