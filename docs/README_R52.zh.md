# R52 原地图快修版（2026-10-13）

当前版本使用金字塔下沉前的原 R50 世界，保留已经授权的旧机库小修复。新地图重构取消并转为代办。源码位于 `C:/Users/liboy/.codex/worktrees/r51-nonmap/eva`，当前入口以 `.Codex/R52_ACTIVE_CURRENT.json` 的 `authoritative_latest` 为准。

已安装前一批回退修复包时，正常停服、退出游戏，将两端 `mods` 中旧 Project SEELE JAR 移出，再放入 `D:/eva/delivery/Project_SEELE_Encore_R52_NonMapUnified_20261013.jar`。每端仅保留一个该模组 JAR；沿用当前试玩存档、配置、玩家、交通和任务进度。

新安装可使用同批 `Project_SEELE_Encore_R52_NonMapUnified_20261013_Client_PCL.zip` 与 `Project_SEELE_Encore_R52_NonMapUnified_20261013_Server.zip`。完整服务器包的世界名为 `SEELE_R50_WORLD`。Minecraft 1.20.1 / Forge 47.4.10 / Java 17 保持。

修复前两使徒被新地图远端路线阻挡的问题，以及插入栓桥侧缺失贴图和旧方块三机库配色。三门归位、幽灵碰撞清理、楼梯无栏杆和原地下运输修复全部保留，数值平衡未改。

源码增量编译、完整 Forge 重混淆、编译分支检查和实际交付包逐成员回读已通过；未再启动游戏，不宣称实际出击、最终画面或性能已经验收。[发行说明](R52_RELEASE_NOTES.zh.md)和[人工检查](R52_USER_ACCEPTANCE.zh.md)使用同一口径。

已完成非地图改动的统一范围见 [收束说明](R52_NONMAP_INTEGRATION_20261013.zh.md)。
