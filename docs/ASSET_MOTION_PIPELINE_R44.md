# 本轮资产与动作工具核对

2026-09-30，负责人提供 Gemini 调研后核对官方资料。工具排名、“影视级”或“最强”均不是本项目验收结果。当前所有旧动作试片仍按负责人判定为视觉不通过。

| 环节 | 可实际进入本项目的路径 | 已核实的限制与采用方式 |
|---|---|---|
| 几何与外形 | 已装 Lux3D CLI 或其他生成器的 GLB/OBJ → Blender → 独立装甲、关节内体与手指 → 现有网格导出器 | 不把高面数或生成成功当形体正确。先比设定图与五个视角，再检查肩、髋、膝、手指和后颈的完整结构 |
| 重拓扑、UV、贴图 | Blender 编辑源保留四边面与关节环线，烘焙后生成运行时三角网格 | 四边面是制作工具，不要求最终渲染网格全部四边面。硬装甲和柔性内体分别处理；重拓扑后重新检查蒙皮和绑定 |
| 视频动捕 | Move/DeepMotion/Flow Studio 的原始 FBX/BVH → Blender 原始骨架 → 身体尺度校准 → 本项目世界手脚目标、支撑与 COM | 不直接复制逐骨旋转；手指、接触、武器和双方响应必须独立验证。官方产品、选项与套餐边界分别记录 |
| 制作与运行 | 可编辑 Blender 场景／IK约束 → 烘焙矩阵 → 重导入 → 现有五机／使徒骨架与实际网格 → Forge/Gecko | 不以在另一套人形骨架上播放漂亮的预览代替游戏效果。角色间接触、碰撞、切换、脚步和声音最终在游戏里核对 |

Meshy 的官方 API 限定清晰肢体的标准双足人形，输入面数超过 300,000 不支持直接绑定，外链 GLB 须面向 +Z。EVA 的长肢、肩塔与装甲遮挡需要自己的绑定验证，不能承诺自动绑定直接可用。[官方 Rigging API](https://docs.meshy.ai/en/api/rigging)

Tripo 官方说明，四边面转换、减面、分件与重新合并会丢失既有骨骼绑定和动画。因此先完成几何／分件，再绑定和重定向，不能把重拓扑后的资产继续当原绑定完整。[官方绑定顺序说明](https://docs.tripo3d.ai/animation/rig-v1-0-20240301.html)

DeepMotion 的 Foot Locking 有不同模式，是脚部处理选项，不是对身体重心、惯性或双方碰撞的真实性保证。Move 的 Genesis 文档提供可选手指追踪及 raw／retargeted 的 FBX、BVH、GLB、USDZ、Blender、JSON 导出；不能把 Genesis 的能力推广到其所有产品。[DeepMotion 官方说明](https://www.deepmotion.com/article/foot-locking)、[Move 官方导出说明](https://docs.move.ai/knowledge/genesis-processing-an-action-take)

Flow Studio 可导出 FBX／USD 进入 Blender 等流程，具体能力受产品与套餐限制。先保留原始采集骨架，再做本项目重定向。[官方功能](https://www.autodesk.com/products/flow-studio/product-details)

本机实测为 RTX 3070 Ti Laptop、8 GB 显存。TRELLIS.2 官方主线仅在 Linux 测试，要求至少 24 GB 显存，不是本机开箱方案；不能直接安装大模型后占满显存。Hunyuan3D-2 官方支持 Windows，说明形状约需 6 GB、形状加纹理约需 16 GB，形状和贴图也需分阶段评估，第三方低显存改版另列验证。[微软官方仓库](https://github.com/microsoft/TRELLIS.2)、[腾讯官方仓库](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)

已检索当前插件目录：精确 DeepMotion 搜索没有结果；综合 Meshy／Tripo／Move 等搜索没有返回相关连接。目录结果不穷尽全部软件。当前可用本地 Blender 与已安装 Lux3D CLI，未宣称新服务已连接；没有发起新的付费动捕／模型任务，也没有把旧 Lux3D 累计 10 积分授权当作其他服务预算。

动作制作现已实际进入 Blender 的原生双骨 IK、两角色共同世界目标和实际网格接触检查。正在做完整交锋而非调增益；原片引用、原创编排、原始动捕与生成动作分开记录，最终质量仍需真实游戏画面与操控验证。

## 晚间外部工具接入

再次精确检索当前插件目录，Blender、DeepMotion、Rokoko、Meshy／Tripo／Rodin 没有返回相关连接；宽泛的 Move AI 检索返回了无关文档类插件，未采用。这个结果不代表互联网上不存在相应软件。

已从 [Rokoko 官方仓库 v1.4.3](https://github.com/Rokoko/rokoko-studio-live-blender/releases/tag/v1-4-3) 固定下载对象 `b031e5a0…`，保留来源、压缩包 SHA 和 LGPL 原许可。原插件的登录、接收器、更新及云依赖不参与本地动作处理。`tools/blender_rokoko_offline_r44.py` 以隔离适配器加载原重定向／骨识别／求值辅助代码，已在实际 Blender 5.1.2 注册 `rsl.build_bone_list` 和 `rsl.retarget_animation`。没有连接云账户或上传资产，也没有改正式动作包。

这只通过环境接入。下一门槛是复制真实源和目标骨架、校准中立姿态、显式对应骨骼、实际重定向、导出后重载，再与现有世界目标制作法比较全身动作与网格。T／A 姿态差、足跟／足尖轴、体形比例和手指仍需本项目校准；不能把注册成功计为动作改善。

进一步核对发现，离线蒙皮规则也必须按实际渲染层区分：萨基尔的加权主路径是 `RiggedAngelLayer`，加载失败才走另一层；它的首槽四元数参考与 `LocalTriangleMeshLayer` 的主权重参考不同，Blender 又采用累积参考规则。当前差异重放属于离线证据。实际加载是否成功、解码后的权重顺序、最终网格及正常速度画面，必须由原生记录确认，不能把某一规则的差异直接冒称游戏已复现。
