# R51 干净非地图封包准备

唯一源码基线为新 worktree 的 de1dc4824c28de90f216205f5b596478839de7cf（2026-10-07 09:24:07）。提交说明确认内容与 build23／实际两包一致；原 JAR SHA256 为 `0e5d4f4afba826a06cbb142870391fa6e841b828693c1e20b2786841a94e711d`、292,163,684 字节、协议 60。Server 813,287,065 字节／3,240 成员，Client_PCL 573,651,291 字节／89 成员；原 world 为 3,066 文件，原 Client 为 manifestVersion 1、files 空列表、overrides 格式。原执行回执已声明实际 archive 回读；PCL GUI 导入未执行。

准备命令（不创建 ZIP、不解压世界）：

```powershell
python tools/prepare_r51_nonmap_two_pack.py
```

输出 `artifacts/r51-nonmap-two-pack/PACK_PLAN_R51.json`。Root 从 `tools/templates/r51-nonmap/ROOT_SELECTION_R51.json.template` 建立选择文件，填写最终干净 nonmap JAR 的 path／sha256、确切内嵌资源允许名单、可选纯动作 runtime 覆盖以及真实变更／测试边界，再准备一次 `--selection`。选入新文件位于本干净 worktree；另允许明确的 `D:/eva/artifacts/r51_nonmap_release` 输入根，但须在 selection 的 `resource_selection_receipt` 指向该根的实际 `RESOURCE_SELECTION.json`，且其 world_source_unchanged=true、new_map_assets=0、new_yashima_or_marine_assets=0。不会读取 construction、取消的 R52 assets 或 QA。

`jar_resource_allowlist` 行为 `{"member":"assets/projectseele/…","sha256":"…"}`，必须与原 JAR 的资源差量完全一致。固定设施／原载架／夹具、worldgen、NBT 结构不能列入。代码／mixin 改动由 Root 审查最终 JAR；包装不改源码或 mixin 配置。新 facility 类／packet/cache 与协议 63 被拒绝，最终协议须匹配此干净 worktree 源码。

`archive_resource_overrides` 只接受现有 `projectseele-local-maps` 下明确列举的纯动作／rig／handling 文件，格式为 `{"member":"projectseele-local-maps/eva_gameplay_r44_0.json","source":"Root-selected file inside this worktree","sha256":"…"}`；两端同时覆盖。`combat_bundle_r44.json` 是身份绑定文件，Root 更换动作时也须提供一致绑定。目录名中的 local-maps 不授权地图覆盖；NERV／城市 NBT、标识与地图资料、config、导航／MTR／世界始终来自原 ZIP。

仅 Root 决定最终执行：

```powershell
python tools/prepare_r51_nonmap_two_pack.py --selection artifacts/r51-nonmap-two-pack/ROOT_SELECTION_R51.json --execute --delivery D:/eva/delivery
```

工具直接 archive→archive 流式保留所有原成员，唯一改写项为最终 nonmap JAR、明确白名单、R51 新说明／批次元数据、Client manifest 的 name／version、服务器 MOTD 和 PCL 显示 title。原 R50 文档／初始化脚本、全部其他配置与依赖保留；SEELE_R50_WORLD／level.dat 不重命名或修改。实际输出逐成员与原 ZIP 或选定源做字节回读，原 zip 不被覆盖，不创建世界目录，不复制／清理 QA，不启动 Java／Gradle／游戏或修改已安装 PCL。

新输出名：`Project_SEELE_Encore_R51_20261009_Server.zip` 和 `Project_SEELE_Encore_R51_20261009_Client_PCL.zip`。此准备工作尚未执行封包。
