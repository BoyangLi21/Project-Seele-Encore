# R55 联机说明

客户端和服务端请使用同一批 R55 包。

1. 把 `Project_SEELE_Encore_R55_20261029_Client_PCL.zip` 拖入 PCL，默认实例名为 `EVANGELION_Encore_R55`。
2. 使用 Java 17，在本版本设置中分配 8 GB 内存。Minecraft 1.20.1、Forge 47.4.10 由启动器按清单安装。
3. 多人游戏添加服务器，名称填写 `SEELE`，地址由服主提供。该名称用于匹配预装远景缓存。

客户端不带单人存档、启动器或 Java；包含当前模组、配置、运行资源、材质、选用光影和完整现有离线远景（含 UN 区域）。光影沿用 `SEELE_Local_Cavern_R53_Review_20261026.zip` 文件名。

包内 `PCL/Setup.ini` 只有版本隔离和针对已定位 JIT 故障的启动参数，不含账号信息。`jit-recovery-r54.json` 只排除三个已定位方法的 C2 编译及内联，不全局降低 Java 编译级别；不要删掉这个文件。PCL 的实例设置与工作目录行为见[官方启动代码](https://github.com/Meloong-Git/PCL/blob/main/Plain%20Craft%20Launcher%202/Modules/Minecraft/ModLaunch.vb)。

服主把 Server ZIP 解压到独立目录，Windows 运行 `Start-Server.bat`，Linux 运行 `start-server.sh`。使用 Java 17；服务器延续上一包的 2 GB 初始、20 GB 最大内存参数，可按主机容量调整 `user_jvm_args.txt`。

服务端世界来自本次正常退出后的实际 `HOTFIX_20261025`，保留玩家、三机、NPC、任务和交通进度。包内历史目录名仍为 `SEELE_R53_WORLD`，产品版本和服务器介绍为 R55。不要把旧包世界覆盖回来。

服务端 Distant Horizons 使用两线程、0.5 工作比例，关闭远处地形生成，并同步游戏中的方块和城市变化。离线远景保留 `PIXEL_ART` 垂直质量与关闭洞穴裁剪的配置。

常用键：`R` 切换 EVA 武器，`O` 指挥通信，`G` AT 力场，`V` 离开 EVA；主键盘 `0` 重载光影、`-` 开关光影、`=` 选择光影。屋岛炮位按住右键蓄力、松开发射，Shift＋右键退出炮位。

本地已有试玩实例直接运行 `F:/eva/Start-Local-Review.cmd`，无需导入无存档的联机客户端包。
