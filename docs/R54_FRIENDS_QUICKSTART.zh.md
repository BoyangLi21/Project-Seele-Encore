# Project SEELE R54 联机快速说明

这是 R54 近三测。请搭配同批服务端与客户端使用；本轮更新及延期项目见随包 `R54_REQUIREMENTS_LOG.zh.md`。

## 客户端

1. 将 `Project_SEELE_Encore_R54_日期_Client_PCL.zip` 拖入 PCL。整合包默认名称为 `EVANGELION_Encore_R54`，无需手动填写名称；若本地已经存在同名实例，PCL 仍可能要求处理重名。
2. 使用 Java 17，建议分配 6–8 GB 内存。PCL 按清单安装 Minecraft 1.20.1 和 Forge 47.4.10；本包不重复附带 PCL、Java、Minecraft assets 或启动器运行库。
3. 多人游戏中添加服务器，服务器名称填写 `SEELE`，地址由服主提供。名称区分大小写，用于匹配预装远景缓存。

客户端不含单人存档；包含当前模组、运行资源、配置、材质、当前光影和离线远景。当前光影文件为 `SEELE_Local_Cavern_R53_Review_20261026.zip`，保留文件名以匹配实际配置，整包版本为 R54。

远景取自本次服务端世界的完整现有 Distant Horizons 数据库，GeoFront 中已缓存的 UN 区域一并保留。缓存不会生成客户端单人世界，也不改变近处真实方块。若更改服务器列表名称，关闭游戏后需把版本目录下 `Distant_Horizons_server_data/SEELE` 同步改为新名称。不要重复安装旧远景包覆盖本次缓存。

## 服主

将 Server ZIP 解压到独立目录。Windows 运行 `Start-Server.bat`，Linux 运行 `start-server.sh`，使用 Java 17。

服务端世界直接取自打包当时正常保存退出的 `HOTFIX_20261025`，包含实际玩家、机体、NPC、任务、交通及各维度进度。包内世界目录继续使用 `SEELE_R53_WORLD` 以保持既有启动配置兼容；这只是目录名，交付批次、客户端名称和服务器介绍均为 R54。不要将旧 ready-world 或旧 ZIP 的世界覆盖进去。

服务器介绍为两行：

```text
EVANGELION:Encore R54 近三测
NERV！ | EVA！| SEELE!
```

实际服务端带指定颜色、粗体及 NERV 图标。地址、端口映射和联网方式由服主按现有环境配置。

## 常用按键

| 按键 | 功能 |
|---|---|
| `0`（主键盘） | 重载光影 |
| `-` | 开关光影 |
| `=` | 光影包选择 |
| `R` | EVA 切换武器／Superb Warfare 换弹 |
| `O` | 指挥通信 |
| `G` | AT 力场 |
| `V` | 离开 EVA |

客户端保留当前实际按键和画面设置；如与个人已有配置不同，以游戏内设置为准。
