# EVA 连续动作运行时（2026-09-05）

项目负责人授权重新处理动作和过渡，允许结合真人动捕与针对 EVA 的修改。
普通攻击仍采用已选 Group C（1.5×），正反手刀仍采用 Phase M 的两条真人动作。
本轮重点是让这些动作与走、跑、蹲起形成可持续操作的链条。

## 行为

- 正常游戏由 `EvaMotionEngineV2.applyGameplay` 选择基础步态或攻击；历史离线预览保持独立入口。
- 走跑共享相位，按实际移动距离推进；倒退反向播放步态，不把骨盆扭向身后。
- 下蹲、起身采用 ACCAD 的原始降身/起身时序与前倾变化；蹲行使用 CMU 的左右脚轨迹与摆臂变化。
- 腿部按 Tiger 的真实尺寸重新求解。深蹲调整膝部转动中心，静态轮廓适配既有 42 格姿态；站立和步行补偿脚底高度。
- 所有切换在 `EvaPoseGraph.commit` 内对最终合成姿态过渡，包括根部、手指和刀 socket。过渡结束后直接跟随目标，不持续低通滤波攻击。
- 保存并恢复未经后处理的 Gecko 输入，防止共享模型把上一实体、上一攻击的变换带到下一次求值。
- 拳、踹、刀的动作进度由服务端逐 tick 同步；客户端只插值相邻进度。低 TPS 下动画不会先于服务端 root motion 播完。
- 正反手刀可提前缓冲下一次输入；姿态或武器改变时取消未发生的刀接触与剩余刀位移。
- 攻击期间采用动作自身的 root motion；持续按住移动键会在动作结束后恢复移动。
- 本机驾驶员依据服务端同步相位预测同一根位移，避免原版车辆回报把服务端位移覆盖；碰撞与伤害仍由服务端结算。

## 数值与接触

伤害保持拳 20、踹 50、正手刀 60、反手刀 80。已选攻击速度与冷却不变。
正手刀仍完整播放，默认约 58 tick；反手冷却仍为 60 tick。

刀的伤害从按键接受时立即结算，移到首次刺入制动：正手源帧 44、反手源帧 24，
默认约第 15 / 8 tick（随后仍应用既有同步率加速）。命中区域中心按该帧刀尖位置换算，
范围和击退沿用原值。取消动作后不得补结算该接触。

协议从 23 升至 24，因为新增了侧踹活动标志、刀动作类型和服务端动作进度。
客户端与服务端需使用同一版本。

## 来源与重建

- 已选拳、踹、刀：现有 Group C / K1 / Phase M 资源及其来源记录。
- 下蹲：ACCAD `Male2_A7_Crouch.bvh`。
- 起身：ACCAD `Male2_D13_CrouchToReady.bvh`。
- 蹲行：CMU `136_09.bvh`，使用原始 BVH 的 Y-up 坐标和原生旋转通道顺序。
- 走跑：已接受的 Tiger/ACCAD 基础关节通道，重新采样到统一步态资源。

ACCAD / The Ohio State University Open Motion Project 的数据采用 CC BY 3.0：
https://accad.osu.edu/research/motion-lab/mocap-system-and-data

CMU Graphics Lab Motion Capture Database： https://mocap.cs.cmu.edu/

修改包括 EVA 比例适配、膝部转动中心调整、脚底支撑、循环接缝和动作时间映射。
生成资源的 provenance 保存原始 BVH 哈希与署名；本次不复制任何网格或贴图进入新资源。

`python tools/build_eva_connected_locomotion.py` 生成
`motion/eva_connected_locomotion_v1.json`（7 clips / 52 bones / 593 frames）。
重建需要本机已有的 Tiger pack 与上述原始 BVH；正常游戏只读取生成的 JSON。

## 验证与实际画面

`gradlew --offline build` 包含生产过渡内核测试：首末姿态、四元数短弧、
30/60/144 Hz 采样、过渡中再次切换、socket 位移及初始速度连续性。

实机回放只允许在 `SEELE_EVA_CONNECTED_REVIEW*` 存档副本中执行：

```text
gradlew --offline runClient -PstrictHighDetail=true -PquickPlayWorld=SEELE_EVA_CONNECTED_REVIEW_20260905 -PconnectedActionReview=true
```

它通过正常驾驶输入和服务器控制包执行走跑、蹲起、持续连击、侧踹、正反手刀、
刀中途下蹲取消、恢复移动及倒退；记录最终写骨结果和游戏帧缓冲，结束后退出。
`tools/export_eva_connected_review.py` 按服务器 tick 间隔生成 MP4，保留采样间隔，
不把低帧率截图误当作 60 FPS 播放。

初号机的完整实机链条与关键帧是本轮验证对象。其他型号、多人延迟、复杂地形足部接触
仍需实机覆盖；蹲姿和卧姿专用攻击仍走各自已有的 Gecko 路径。
构建和程序检查不代替项目负责人对最终观感的评价。

本轮交接录制：`20260905_122652`，完整执行 690 个服务器 tick，保留 476 份最终姿态
与 476 张真实游戏画面，覆盖全部上述状态。构建、生产过渡内核测试及桌面资源同步检查通过。

## 人工复测顺序

1. 用开发构建启动动作实验室，执行 `/seele dev motionlab reset`，再执行 `/seele dev motionlab enter unit01`。
2. 第三人称观察：走→跑→停；站立→蹲下→蹲行→起身。特别看停止蹲行后是否反弹到半站姿。
3. 空手按住前进和左键，连击中按 B，保持前进到侧踹结束。看身体是否连续、动作位移是否生效、移动是否自然恢复。
4. `/seele dev motionlab weapon unit01 knife` 后，左键出刀途中按右键，再在反手刀中按左键。看换握、刀 socket、肩胯与收势是否接续。
5. 刀起手后立即下蹲，再起身移动。看取消是否留有旧动作、跳姿或刀握点漂移。

最近的完整实机记录位于 `run/screenshots/projectseele_connected/`；可播放版本位于
`artifacts/motion_research/eva_connected_actions_20260905/eva_connected_actions.mp4`。
这些录制仅用于本机人工复测，不进入 Git 发布物。
