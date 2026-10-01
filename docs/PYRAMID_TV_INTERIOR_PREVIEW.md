# 金字塔内部扩建初稿（2026-09-05）

状态：空间与通路已落到本机预览副本，可人工验收；家具和设备外观仍是粗稿，未作为最终美术通过。

## 打开与检查

本页保留 2026-09-05 的历史预览记录。原独立预览存档已不在当前工作目录，对应 BAT 入口已退役；当前试玩使用 PCL **Project SEELE R44 Stage**，见 [R44 阶段手册](MANUAL_ACCEPTANCE_R44_STAGE.md)。下列旧坐标仅解释当时预览，不作为当前安装入口。
存档目录是 `run/saves/SEELE_PYRAMID_TV_PREVIEW_20260905`，源图为 `SEELE_S20_RECOVERY_R28`。
入口在 `projectseele:geofront` 维度的 **(28.5, -448, 267.5)**，朝西进入新增通道。

必要时可用：

```text
/execute in projectseele:geofront run tp @s 28.5 -448 267.5 90 0
```

建议依次检查：入口接头 → 西翼值班准备 → 西翼作战简报 → 西折返楼梯 → 下层维护舱
→ 东折返楼梯 → 东翼通信支援 → 原有东侧人员通道。
关注楼梯上下是否顺畅、通道转角和净空，以及新增房间的体量与主指挥厅的关系。

| 区域 | 脚底 Y | 参考位置 |
|---|---:|---|
| 西翼值班准备 | -448 | (-16, -448, 270) |
| 西翼作战简报 | -448 | (-24, -448, 282) |
| 东翼通信支援 | -448 | (60, -448, 290) |
| 下层数据链路维护 | -461 | (28, -461, 302) |

两侧折返楼梯各下降 13 格，带中间平台、护栏和支承结构。上下层组成可绕行的连接，
不需要用传送代替走廊。入口对齐实测人员通道，未把其上方的检修顶板当成入口。
东侧接口避开自动扶梯设备及护栏。

## TV 版参考与设计取舍

- [Nerv Headquarters / EvaGeeks](https://wiki.evageeks.org/Nerv_Headquarters)：参考总部的层级、指挥区与技术区域关系。
- [Command Center / EvaGeeks](https://wiki.evageeks.org/Command_Center)：参考多层主指挥厅以及低层计算设施的组织关系。
- [TV 第十一话场景记录](https://wrongeverytime.com/2019/06/24/neon-genesis-evangelion-episode-11/)：参考停电时人工通行、维护和人员交通的重要性。
- [TV 第十三话场景记录](https://wrongeverytime.com/2019/09/16/neon-genesis-evangelion-episode-13/)：参考 MAGI 检修场景中的灰白设备包壳、红色识别带与外露管线。

上述资料用于风格和功能关系研究，不是精确建筑图纸。本轮新增房间和连通线是为现有地图设计的补充，
不宣称是 TV 版逐尺寸复刻。未把官方截图、音频或图案导入游戏资源。

初稿采用灰白墙体、暗色结构、局部红色带、顶梁和遮挡灯槽；保留现有主指挥厅及上部办公室。
设备和家具目前主要承担场景表达，未新增一套 MAGI 计算或通信业务系统。

## 实施与校验

`tools/build_pyramid_tv_interior_preview.py` 通过 `query_blocks.py` 读取源图，生成正向/逆向逐格差异。
在预览副本中写入后，进行了完整差异读回和标牌 NBT 读回；源图涉及的区域文件哈希保持不变。
路线检查覆盖四个房间、两组楼梯的中间平台，以及与现有通道的接点。

本地记录：`artifacts/pyramid_tv_interior_20260905/`，包括 `manifest.json`、`forward.csv`、
`inverse.csv`、`region_before/` 和迭代备份。它们只适用于这个预览，不应直接覆盖其他存档。
实机图在 `run/screenshots/projectseele_pyramid_tv/20260905_224724/`，共九个视角。

预览含只读布局标记，用于停用自动地图生成器；原始 R28 未写入本次扩建。
等负责人确认后，再处理正式地图的晋升。
