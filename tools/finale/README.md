# 初号机动作离线制作工具

`src/main/resources/assets/projectseele/motion/first_battle_r59.json` 由本目录生成，内容为原创手 K 动作（MIT），不含任何动捕或官方素材。

## 文件

| 文件 | 作用 |
|---|---|
| `rig.py` | 复现 GeckoLib 4 烘焙空间的骨骼数学（枢轴 X 取反、旋转 (-x,-y,+z)、Rz·Ry·Rx），带软件光栅预览渲染 |
| `scene.py` | 读取私有模型（EVA 刚性分段网格 + 萨基尔蒙皮网格），路径由环境变量 `SEELE_PRIVATE` 指定 |
| `body.py` | 姿势求解：骨盆/胸/头 + 解析两段式肢体（绕游戏真实膝/肘铰链中心，极向量决定朝向，不会前后翻转）+ 脚底不入地约束 |
| `anim.py` | 关键帧通道（单调 Hermite；`flat` 缓入缓出、`fast` 发力、`linear`） |
| `chor.py` | **编排本体**：各段关键姿势与双方接触（抓前臂、砸核心、推肩、抱背） |
| `film.py` | 电影镜头（位置/目标/FOV/切镜） |
| `export.py` | 导出游戏用 clip（30fps、460 tick、曲线、镜头、事件重映射、手型时间表） |
| `qa.py` | 物理质检：穿地、落地脚滑动、关节单帧突变、够不到、极向量退化 |
| `review.py` / `video.py` | 多视角接触表 / MP4 预览（需 `imageio-ffmpeg`） |
| `idle.py` | 原创站立待机（`eva_idle_r59.json`） |
| `rifle_stance.py` | 持枪跪姿到趴下的骨盆和双腿（`eva_rifle_legs_r59.json`，运行时覆盖到捕捉片段上） |
| `dash_stride.py` | 冲刺的上身和双腿（`eva_dash_r59.json`，运行时覆盖到捕捉片段上） |
| `replay.py` | 把复审客户端的 `poses.jsonl` 重放进离线骨架，分段统计穿地、滑步、关节速度、铰链缝隙、脚踝和手腕弯折 |
| `gait_clip.py` / `hipcurve.py` | 量步态片段本身 / 实机骨盆曲线 |
| `skin_compare.py` / `bend_test.py` / `fix_eva_plates.py` | 蒙皮对比、弯折测试、肘部装甲板归属修正 |

## 流程

```
python qa.py                                  # 先过质检
python review.py out.png side,front34 8.0 9.2 # 关键帧多视角
python video.py film.mp4 film                 # 电影镜头预览
python export.py ../../src/main/resources/assets/projectseele/motion/first_battle_r59.json
```

实机复审后用 `python replay.py <截图批次目录>` 看各段数值，再看接触表，确认无误才交付。

坐标：舞台系 x 侧向（初号机左手为 +x）、y 向上、z 向前（初号机初始朝 +z，萨基尔朝 -z）。AT 力场面板在 z=21、中心高 40（`FirstBattleEffects`）。
