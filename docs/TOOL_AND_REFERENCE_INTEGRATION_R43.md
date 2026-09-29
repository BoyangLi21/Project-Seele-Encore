# R43 参考资料与工具接入记录

这些记录描述已经做过的接入及当前制作依据，不表示作品质量达标。TV、电影制作方法、真人动捕和现实车站分别记录。

| 来源／工具 | 本轮实际使用 | 进入现有管线的方式 | 限制与结论 |
|---|---|---|---|
| 本地 TV 第 2 话参考片段（R42 参考目录） | 已查看的短片与抽帧用于核对直接前扑、核心上方攻击及最终自爆顺序 | 编排到共用 23 秒时间轴；保留最后爆炸，移除中途十字架和前空翻 | 观看范围是保存的短片，不能写成已看完整剧集；新增衔接属于游戏演出推演 |
| 已登记的 Tuffles 真人动捕 | 真实源 BVH、SHA-256、镜像与标定信息保留 | 源帧→解剖参考轴→完整骨架→脚底约束→现有私有 JSON；原生测试通过明确的目录参数选择候选 | 人体比例与 EVA 不同，需要重新校准；本轮普通攻击候选未获视觉认可，不能直接替换全部动作 |
| Blender 5.1.2 | 真实 EVA／萨基尔骨架、Armature 修改器、保存和重读；配对场景 48 个样本 | 导出实际骨骼／网格／矩阵，重读真实求值顶点，误差记录在 `blender_interop` | EVA 测的是刚性分件，不包含原生 DQ 接缝；萨基尔不包含后段 ARAP 包覆缓存；这不是最终游戏画面 |
| [Epic Fight 官方 Blender 插件](https://github.com/Antikythera-Studios/blender-json-addon) | 固定提交 b9c6844，实际导出 72／17 骨与 691 帧 | 单角色临时场景→MAT JSON→父级累计、逆绑定、时间原点及对象位移适配→SEELE 采样格式；24 个实测姿态重读 | 没有注册插件更新器、上传资源或替换游戏战斗引擎；完整动画插值和运行时接缝仍需测 |
| [Epic Pose Warping 文档](https://dev.epicgames.com/documentation/unreal-engine/pose-warping-in-unreal-engine) | 研究步幅／足部 IK 与移动速度的职责划分 | 用于区分源运动方向、根运动、支撑约束的检查项目 | 未在本项目安装 Unreal；不能把文档阅读称为完成 Motion Matching |
| [Naughty Dog 的动作捕捉管线讲座页面](https://www.gdcvault.com/play/1021854/Capturing-The-Last-of-Us) | 读取公开介绍，确认整理原始捕捉、曲线和重定向是独立步骤 | 本轮保留逐阶段姿态而不是只检查最后腕点 | 没有观看完整受限演讲；TLOU2 PDF 获取返回 403，未使用其不可见内容 |
| [Rokoko 官方 Blender 插件](https://github.com/Rokoko/rokoko-studio-live-blender) | 官方资料调查 | 可进入同一 Blender 骨架映射／烘焙出口 | 尚未在 Blender 5.1 完成实际试验，不能计作可用接入 |
| [Cascadeur 官方方案](https://cascadeur.com/plans) | 核对导出／重定向的方案限制 | 可作为后续关键姿态与重心修订源，再进入当前 Blender 出口 | 尚未购买、注册或上传；不是本轮已完成工具 |
| [WorldEdit 7.2.15](https://modrinth.com/plugin/worldedit/version/7.2.15) | 核对与 1.20.1 的对应版本 | 可处理将来的明确设施组件，仍须完整 NBT、精确差量与逆向补丁 | 未安装试用，不能替代本轮语义目录或按方块类型删除全图 |
| [JR 东日本大森站实景动线](https://media.jreast.co.jp/articles/5662) | 已在浏览器实际查看站厅、出入口和门后转弯的照片 | 制作规则：门槛连续、候梯与主通道分开、目标标识在决策点之前、墙柱收口完整 | 这是当代真实设施，非 1995 年照片；只用于空间逻辑和细部，不照搬现代品牌／商业内装 |
| [JR 车站改造资料](https://www.jreast.co.jp/e/press/20110904/img/Attatchment02.pdf) | 读取公开 PDF 文本 | 用于区别站厅与站台、高架桥下柱网、换乘高程的检查对象 | 截图两次获取失败，未声称看到了里面的图像 |
| [官方《设定资料》讲座报道](https://www.eva-info.jp/8080) | 阅读布景、布局与关联视点的方法说明 | 重要空间采用整体／局部共用地标和一致坐标，不用互不相干的美图替代地图 | 报道讨论新剧场版制作方法，不作为 TV 建筑造型的直接证据 |

下一步的美术样板须同时包含入口、普通视线、斜视剖面、灯光开关及真实运行设备。现有照片仍显示石砖通道、大色带和不够清晰的前室组织，不能把补栏杆说成完成美术统一。样板形成后，按设施类别推广全部实例，并保持未审查清单。

补充：ACCAD / Ohio State 的 [Open Motion Project](https://accad.osu.edu/research/motion-lab/mocap-system-and-data) 页面核实为 CC BY 3.0。已将 Male2 的真实站姿、步行和跑步经相同参考帧进入私有姿态格式，步幅和脚底触地相位随动作一同导出。素材没有完整手指轨道，指节另行制作，不能称为真人手指动捕。首个零旋转参考错误已在失败记录中公开保留。

另读了 Naughty Dog [官方制作访谈](https://www.naughtydog.com/podcasts/thelastofus/en/ep-05) 中动作捕捉后人工调整、完整身体动作及运动匹配的讨论。对应本项目的实际决定是保留完整身体的来源姿态、真实移动输入和各层姿态记录，先修校准与交接，不能把引用 Motion Matching 名称当作已实现该系统。GDC PDF 仍返回 403，未据其不可见页面作制作结论。

9 月 29 日补充阅读了 [Epic 的混合与惯性过渡文档](https://dev.epicgames.com/documentation/unreal-engine/animation-blueprint-blend-nodes-in-unreal-engine)。本轮实际采用的是同一连续权重控制姿态、步幅及接触相位；尚未实现该引擎的惯性过渡节点，不能改称已经集成。ACCAD 的 `Male2_B18_WalkToLeapToWalk` 已作为连续三阶段跳跃候选进入五机现有 JSON 格式，保留整身记录并提取弹道根位移，避免和游戏重力叠加；手腕及手指明确另行制作。初号机第一版与 UN00 第二版均已实机查看，但上举双臂／手掌与 TV 的攻击性前扑观感仍有距离，因此尚未采用为正式美术。

再次查看本地 TV 第二话 2.5、3.0、3.7 秒参考图，采用其收紧躯干、向前扑入的整体轮廓作为暴走前扑的依据；普通游戏跳跃是否使用同一姿态还需区别运动情境。这些参考没有作为游戏贴图或视频资源嵌入。官方 [30 周年展资料介绍](https://ao-eva.exhibit.jp/highlight/) 区分 TV 制作资料与新剧场版资料；本轮只读取介绍，未声称看过展出的全部设定。
