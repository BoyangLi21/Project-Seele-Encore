# 开放代码、素材与本机存档的公开准备

代码仓库可以继续按现有 MIT 许可协作；现有本机存档和资源包包含不同作者的材料，不能统一重新标成 MIT。“免费、不盈利”也不会替代各项素材的再分发条件。此文件是项目整理方案，不是对整个同人游戏已获许可的声明。

## 当前材料与具体处理

| 材料 | 当前来源／状态 | 公开前的处理 |
|---|---|---|
| 本项目 Java、Python 与原创设施几何 | 仓库自有代码、生成脚本；按仓库许可 | 提供源文件、生成方式和版本；核对第三方代码的独立声明 |
| R24 电话、时钟、茶室、书报设施 | 本项目原创网格；历史照片仅作观察参考 | 可以作为原创生成资源随代码提供；保留参考与改编说明 |
| 原创合成脚步、机械、警报和光鞭音效 | 固定种子生成，见 `tools/build_*audio*.py` | 提供脚本与源清单；不混入 TV 音轨 |
| 神经语音播报 | 本项目文本，Microsoft 声线，经 edge-tts 生成 | 单列生成途径与文件，确认该服务输出的分发条件；也可由自愿配音者重录 |
| Tigerar1 的 EVA 身体 | 原作者页面标示 CC Attribution-ShareAlike | 提供逐模型署名、原始链接、修改说明及对应许可；衍生美术不改标 MIT；仍核对基础 IP 的使用范围 |
| ACCAD、CMU、CMCD 等动作 | 各自的使用条款，见 [第三方动作声明](THIRD_PARTY_MOTION_NOTICES.md) | 保留来源、动作片段、重定向修改和许可证；逐项核对，不能因“免费动捕”而省略 |
| 混合了非商业许可或演示包的私有动作 | 本机动作包有独立 provenance | 不直接放进通用开放素材包；确认许可或换成允许相应分发的动作 |
| Battle Orchestra 游戏提取模型 | 目前仅本机研究和测试 | 不进公共源码、美术包或地图下载；优先用社区原创模型替换 |
| Audijon2 的 NERV 总部地图及衍生存档 | [原帖](https://www.planetminecraft.com/project/evangelion-nerv-headquarters-command-center/)；本机世界在此基础上大幅改造 | 发布时署名并附原帖链接；发布前告知作者；在地图合适位置致敬 |
| 下载的人物皮肤、军舰、武器等 | 多个作者和页面，部分缺少明确再分发许可 | 补齐具体来源与证据，无法确认的保持本机使用或重做；一项下载成功不等于获准再分发 |
| Lux3D 生成与后续修改的 UN 模型 | 生成任务和本机处理记录 | 保留任务、服务条款与人工修改记录；不把生成参考图的第三方角色／标记权利一并视作已取得 |

本轮重新读取了 [khara 的公开指引](https://www.khara.co.jp/guideline/)：其中列明视频、静止图和小说等公开场景，并限制官方音视频素材的直接使用；不能据此自动认定整套可下载游戏、原始素材和地图都已获准分发。正式公开前应由负责人确认相应范围。

[Tigerar1 初号机原页面](https://sketchfab.com/3d-models/evangelion-unit-01-9fddeb0a7143436598c805dab2f147bf)当前显示 CC Attribution-ShareAlike。其余机体和附件仍需按 [完整素材表](ASSETS.md) 逐项核对，不由这一页替其他作品作授权。

## 可直接交给同好的入口

1. 代码：Forge 1.20.1／JDK 17 的可构建仓库、运行说明、原生回退资源和明确的已实现功能。
2. 原创贡献素材：源文件、导出文件、许可、生成脚本、尺寸／轴向／骨骼契约；与 MIT 代码分开登记。
3. 私有本机包：仅保留本地。公开构建和 CI 不依赖开发者磁盘上的 `run/`、`external-assets/` 或个人账户配置。
4. 地图：完整衍生世界随发布提供时，署名 Audijon2 并附原帖链接，发布前告知作者。其他第三方地图仍按各自来源处理。

建议每个贡献 PR 用同一份素材说明：`作者 → 原网址 → 许可证网址／授权文件 → 原文件 SHA-256 → 修改内容 → 导出文件 → 运行截图`。来源不清的材料不能通过把文件重命名、重拓扑或重新截图来消除来源问题。

## 发布前给 Audijon2 的留言草稿（尚未发送）

> Hi Audijon2,
>
> Your NERV Headquarters Command Center map was the starting point for the NERV HQ in Project SEELE, a free, open-source, non-commercial Evangelion mod for Minecraft Forge 1.20.1. You said you would love to see what people build from it, so here is a link: [release link].
>
> We have rebuilt and extended it a lot since then. The release credits you by name with a link to your original post, and we would like to add a small tribute to you inside the map.
>
> If you would like anything changed about how you are credited, tell us and we will change it. Thank you for sharing the map.

由负责人本人在发布前发送。其他模型／皮肤作者的询问要换成具体作品链接和想公开的材料范围，不能把草稿当作已取得的许可。
