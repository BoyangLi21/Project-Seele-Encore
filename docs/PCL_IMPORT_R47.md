# R47 PCL 导入说明

使用 `D:/eva/delivery/Project_SEELE_Encore_R47_20261005_Client_PCL.zip`（368,596,492 字节）。原 `Client.zip` 是手动实例文件包，缺少整合包清单，不能直接拖入 PCL。

1. 将新的 **Client_PCL.zip** 直接拖入 PCL 主窗口，也可以在下载页使用“安装整合包”。不要先解压。
2. 确认新版本名称，默认 `Project_SEELE_Encore_R47_PCL_20261005`，等待安装完成。
3. 选择 Java 17 启动。它与先前 R47 服务器包使用同一模组版本，服务器无需更新。

21个模组、配置、地图显示资源和两份材质都已放进包内。整合包的远程模组列表为空，PCL 不需要从 CurseForge 下载这些模组；Minecraft／Forge 的基础文件缺失时仍需补下载。不要求保留旧R46实例，也不执行旧 `Install-R47-From-Local-R46.ps1`。

首次启动通过 PCL 的版本启动前命令，在当前隔离实例内生成 R47 个人光影。完成后后续启动直接跳过；默认关闭光影。需要时在游戏视频设置的光影菜单选择 `SEELE_Local_Cavern_R47_Private_v1.zip`。若关闭启动前命令，可以在实例目录手动运行 `Initialize-R47-Visuals.ps1` 一次；初始化失败记录在 `R47-Visual-Initialization-Error.txt`。

本次只修安装包装，没有改游戏JAR、服务器包或世界。新ZIP已回读清单、启动脚本和原模组／运行文件的内容记录；未调用PCL窗口完成实际安装，实际拖入与启动仍由用户验收。

制作依据：[PCL官方整合包导入代码](https://github.com/Meloong-Git/PCL/blob/main/Plain%20Craft%20Launcher%202/Modules/Minecraft/ModModpack.vb) 的根 `manifest.json` 与 `overrides` 路径，以及 [官方替换标记](https://github.com/Meloong-Git/PCL/wiki/%E6%9B%BF%E6%8D%A2%E6%A0%87%E8%AE%B0) 的 `{version_indie}`。未根据普通文件ZIP的名称推断可导入。
