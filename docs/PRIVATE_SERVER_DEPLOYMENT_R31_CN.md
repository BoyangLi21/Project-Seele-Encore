# R31 五包部署

服务端、客户端与存档必须使用同一批 R31，网络协议 **35**。五个 ZIP 各自带 `R31_BATCH.json`，其中记录运行 JAR、模型和动作文件散列；外部 `SHA256SUMS.txt` 用来核对五个压缩包。

| 压缩包 | 解压位置 |
| --- | --- |
| `Project_SEELE_R31_Server.zip` | 新的服务端目录 |
| `Project_SEELE_R31_World.zip` | 服务端目录下 `SEELE_R31_WORLD` |
| `Project_SEELE_R31_Client.zip` | PCL 的 Forge 1.20.1 独立游戏目录 |
| `Project_SEELE_R31_Textures.zip` | 同一个客户端游戏目录，合并 `resourcepacks` |
| `Project_SEELE_R31_Shaders.zip` | 同一个客户端游戏目录，合并 `shaderpacks`、`config` |

R31 世界从本轮保存的 R30 用户冷备份复制，只加入两座 UN 机库扩宽的明确方块差量和相应静态通行目录。新存档在游戏列表中显示为 **Project SEELE R31**：仅将新副本 `level.dat` 的 `Data.LevelName` 改为这个名称，其余 NBT 标签深比较保持一致。原玩家、实体、NPC、交通及剧情进度保留；没有把自动测试世界的动态实体、玩家或地表测试平台复制进去。原 R30 源世界和旧压缩包不覆盖。

如果远程服务器在本地冷备份之后已有新的游玩进度，先保存远端目录。这份存档没有自动合并那部分远端新增进度。不要混拷旧、新地图的 region 文件。

## 服务端

1. 准备 Java 17，把 Server 包解压到一个新目录。
2. 把 World 包解压进该目录的 `SEELE_R31_WORLD`，确认路径直接为 `SEELE_R31_WORLD/level.dat`，没有多套一层文件夹。
3. Windows 运行 `Install-Server.bat`；Linux 运行 `bash install-server.sh`。模组和世界已包含，首次安装 Forge 运行库仍需网络。
4. 阅读 Minecraft EULA，同意后自行将 `eula.txt` 改为 `eula=true`。
5. 根据主机内存调整 `user_jvm_args.txt`。默认上限 16 GB，需要给系统和其他服务留内存。
6. Windows 运行 `Start-Server.bat`；Linux 运行 `bash start-server.sh`。
7. 确认 `server.properties` 中 `level-name=SEELE_R31_WORLD`，按需配置白名单、正版验证和端口。

服务端不要安装 Oculus、Embeddium 或 Xaero 客户端模组。新加入的三个 `projectseele-local-maps/eva_combat_capture_r31*.json`、`angel_grip_r31.json` 和 `eva_recovery_r31.json` 都必须保留，不能只更新 JAR；两边需要相同动作、使徒表面接触和五机型起身支撑数据，手端与身体计算才能一致。`R31_BATCH.json` 的 `runtime_profile_sha256` 记录这五个文件的散列。

## PCL 客户端

在 PCL 该版本的设置中打开**游戏文件夹**。确认版本为 Minecraft 1.20.1、Forge 47.4.10。关闭游戏后合并 Client 包，移走旧 Project SEELE JAR，`mods` 里只留本批的一份。

客户端已经包含 EVA 私人模型、动作数据与必需模组。单机测试时，把 World 包放到该游戏目录的 `saves/SEELE_R31_WORLD`；连接服务器时，不需要给客户端复制完整世界。

材质和光影是两个可选 ZIP，包含你已下载的作者原始包，不需要在 PCL 再下载：

- Textures 包解压合并后，运行 `Install-Textures.bat`。它会校验本地原包并启用，EVA 专用资源保持更高优先级。
- Shaders 包解压合并后，在「视频设置 → 光影」选择 Complementary Unbound。客户端已经带 Oculus；也可运行 `Install-Visuals.bat` 复用本地文件。
- 外层 ZIP 是安装包，内层作者原始材质／光影 ZIP 保持完整，由游戏读取。

不要解压到 PCL 启动器程序所在目录。若安装脚本仍想下载，先检查是否解压到了该版本真正使用的隔离游戏目录，以及原 ZIP 的文件名是否完整。

仓库本机可运行 `start_eva_test_r31.bat`，加 `--city-shaders` 开启光影；这个 BAT 使用仓库开发启动器，不代替远程电脑上的 PCL。

## 交付状态与验收

`R31_BATCH.json` 的 `acceptance_mode` 区分已提供原生报告的交付与 `manual_by_user`。后者表示本批按人工验收方式交付；`passed:null`／`status:not_run` 表示未运行，不能读成通过。压缩和散列校验只证明包完整，不证明游戏手感、运输或专用服务器均无问题。

先检查新战斗、双机复位、横向空运及机库，再走第一幕。服务端与客户端要来自相同 `R31_BATCH.json`，尤其不要把旧 R30 JAR 和新的动作 JSON 混用。

服务器承担世界与实体模拟；本地显卡仍负责绘制。远景继续使用实际区块渲染，没有重新启用此前透视严重的 LOD 方案。高分辨率、光影和较远视距都会增加显卡负载，可在 Windows 图形设置中把实际 Java 17 的 `javaw.exe` 设为高性能独显，并在游戏 F3 查看 GPU。

本批五包是私人测试部署备份，第三方模型、材质、光影等仍保留各自许可。公开项目源码时，以自有代码、生成工具和获准再分发的资源为范围。

## 维护者打包顺序

以下由项目维护者执行，普通 PCL 用户无需运行：

```powershell
C:/Python314/python.exe tools/stage_world_r31.py --apply --manual-acceptance
```

这一步只生成新世界及 `r31_world_stage.json`。完成最终模型安装、三个动作文件安装和最终构建后，再执行：

```powershell
C:/Python314/python.exe tools/package_release_r31.py stage --personal-local --manual-acceptance
C:/Python314/python.exe tools/package_release_r31.py seal --personal-local --manual-acceptance
```

脚本要求 R31 模型安装收据 `artifacts/facility_r31/models/promotion.json`，其中 `installed=true`，`models.eva_prototype.mesh_sha256` 与 `models.eva_un01.mesh_sha256` 对应正式资源包。可以用 `--model-receipt` 指定同格式的实际收据。它还会和 R31 `staging.json` 指定的评审模型核对网格、骨架、动画、纹理、PBR、两套 CPU 骨架与背部接口，防止只换模型却仍使用旧碰撞／接触数据。现有 R30 命名的运行时模型 manifest 仍作为兼容校验合同，不能只改版本标签而不更新散列。评审资源包仅用于核对，客户端实际打包的是已晋升的 `eva_real_model`。

若有完整原生验证报告，可去掉 `--manual-acceptance`，向阶段脚本传 `--verification-report`。合并报告应标记 `revision:R31`，其 `coverage` 分别记录 `combat`、`recovery`、`un_reset_capsules`、`air_transport`、`rendered_socket_alignment` 的真实通过结果。仅有运输／复位流程通过，不能把模型与插入栓的实际显示位置算作通过；即使原报告的 `passed:true`，缺项仍标为部分证据。封包还要求真实的 `artifacts/server-ready-r31/production_check.json`。没有报告时不能伪造 `passed:true`。脚本禁止覆盖已有 R31 世界、分阶段目录或 ZIP，避免覆盖人工验收之后的进度。
