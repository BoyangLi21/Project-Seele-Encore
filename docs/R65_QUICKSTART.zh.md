# R65 联机说明

**服务器和所有玩家必须一起换成 R65**：R65 用协议 83，R63r 的客户端连不上 R65 的服务器，反过来也一样。不要和 R63r 或更早的包混用。R64 没有单独发布，内容都在 R65 里。

## 玩家

1. 把 `Project_SEELE_Encore_R65_<日期>_Client_PCL.zip` 拖入 PCL，默认实例名为 `EVANGELION_Encore_R65`。
2. 使用 Java 17，在本版本设置中分配 7.2 GB 内存。Minecraft 1.20.1、Forge 47.4.10 由启动器按清单安装。

   可选：想让卡顿更少，可以在 PCL 的版本设置 → 高级启动选项 → JVM 参数里，把 PCL 默认的两个 20% 参数（`-XX:G1NewSizePercent=20 -XX:G1ReservePercent=20`）换成 `-XX:+UseG1GC -XX:MaxGCPauseMillis=50 -XX:+PerfDisableSharedMem`。不改也能正常玩。
3. 进入多人游戏，列表里已经有名为 `SEELE` 的服务器，直接加入。这个名称用来匹配预装的远景，不要改。

包里已经带好小地图和预渲染的远景，都按 R65 的世界重新烘焙：远景包括地图外的海和山，小地图包括地图外圈和 GeoFront 地下一层。进服后小地图立刻是完整的；远景大约一到两分钟加载完。

小地图按服务器地址匹配。服主换了地址的话，预装的小地图不会生效，要用新地址重新打包。

客户端包不含单人存档、启动器和 Java。`PCL/Setup.ini` 只有版本隔离和 JIT 启动参数，不含账号信息。`jit-recovery-r54.json` 不要删。

山坡草方块侧面全绿的资源包 `SEELE_GreenGrassSide.zip` 默认开启，不想要可以在“选项 → 资源包”里关掉。

光影下远处的小实体不投影，可以在 `config/projectseele-client.toml` 的 `[shadows]` 里调整距离，填 0 恢复全部投影。

## 服主

**R65 要整包替换，包括世界**：停服后把旧目录整个换成新包解压出来的目录。R65 的世界是新的（地图在 R63 之后又改了很多），换掉会清空玩家在 R63r 服务器上的进度。

把 Server ZIP 解压到单独的目录，使用 Java 17。内存默认 2 GB 初始、20 GB 最大，可以在 `user_jvm_args.txt` 里按机器调整。

- 自己的电脑：Windows 运行 `Start-Server.bat`，Linux 运行 `sh start-server.sh`。
- 托管面板（枫叶等）：内核或服务类型选“自定义 JAR / Custom JAR”，Java 选 17，启动文件填 **`server.jar`**（启动命令 `java -jar server.jar`）。不要填 `unix_args.txt`，也不要让面板自动安装或升级 Forge：面板装的 47.4.28 会让模组注入失败，这套包只能用 47.4.10。面板显式给出的 `-Xms`/`-Xmx` 会传给服务端，没给时用 `user_jvm_args.txt` 的值。日志里应该出现 `[SEELE] Pinned Minecraft 1.20.1 / Forge 47.4.10 / Java 17.`。
- 面板能填完整启动命令时，在包根目录用：`java @user_jvm_args.txt @libraries/net/minecraftforge/forge/1.20.1-47.4.10/unix_args.txt nogui`（两处 `@` 都要有）。
- 包里的 `eula.txt` 是 `eula=false`。首次运行前由服主自己阅读并同意 Minecraft EULA，再改成 `true`。

世界在 `SEELE_R53_WORLD`，这是历史目录名，产品版本是 R65。不要把旧包的世界或远景数据库覆盖回来：包里的远景数据库做过处理，能避免客户端重复下载。

**只能用 R65 包里的模组打开这个世界。** 地图外圈由新模组生成，旧模组打开后会在外圈长回旧地形，而且写进存档就去不掉。

**停服顺序**：先让玩家都退出，在控制台输入 `list` 确认在线人数为 0，再等半分钟左右（远景后台还在处理区块），然后输入 `stop`，等日志写完全部维度保存、Java 自己退出。不要在玩家刚退出时马上 `stop`，也不要强制结束 Java：测试里这样做，远景线程可能卡住不退出。

## 道路 mod

地图的道路用 TrafficCraft 的方块，铁路和车站用 MTR 的方块，两个包里都已经带了。把世界搬进自己装的实例时，先放好 `trafficcraft-forge-1.20.1-1.1.3.jar` 和 `MTR-forge-4.0.5+1.20.1.jar` 再打开存档。遇到缺方块的提示一律退出，不要点继续，否则路面和铁轨会变成空气。

## 指令

游戏内指令都在 `/seele` 下，输入 `/seele` 后按 Tab 查看。城市升降被打断、卡在半途时，管理员用 `/seele city recover`。

初号机默认用新的移动方式（脚踩实地）和新的战斗节奏。想换回旧的：`/seele motion legacy`、`/seele combat legacy`；换回新的：`/seele motion planted`、`/seele combat frames`。联机时以服务器的设置为准。

## 常用键

`R` 切换 EVA 武器，`O` 指挥通信，`G` AT 力场，`V` 离开 EVA；主键盘 `0` 重载光影、`-` 开关光影、`=` 选择光影。屋岛炮位按住右键蓄力、松开发射，Shift＋右键退出炮位。
