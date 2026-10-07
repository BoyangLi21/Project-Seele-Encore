# R50 启动入口清理

2026-10-06。按用户本轮删除冗余bat/log的要求，核对Git跟踪文件及现R50制作、打包、正常开发依赖后，退休10个旧批处理。`gradlew.bat` 保留；没有删除Java类、当前R50模板、当前交付包或个人PCL实例。未stage或commit，由Root统一审diff和提交。R50仍在制作，本记录不表示已经发行。

## 原文件归档与退休范围

原文件先复制到 `D:/eva/.Codex/r50-retired-launchers/`，保留原相对目录；逐个比较SHA-256相同后，才用PowerShell `Remove-Item -LiteralPath` 删除对应工作树文件。源和归档绝对路径均核在 `D:/eva` 内，10个目标是明确文件，没有递归清理。恢复索引为 [receipt.json](D:/eva/.Codex/r50-retired-launchers/receipt.json)，包含原路径、归档路径、字节数和SHA-256；`.Codex/` 已忽略，不随公开Git提交。

| 已退休路径 | 实际用途与退休依据 |
|---|---|
| `tools/deployment_r25/Start-Server.bat` | 绑定R25就绪标记及旧预览世界；仅旧打包器复制该版本目录 |
| `tools/deployment_r26/Start-Server.bat` | 绑定R26就绪标记；属于旧版本包装 |
| `tools/deployment_r27/Start-Server.bat` | 绑定R27就绪标记；属于旧版本包装 |
| `tools/deployment_r28/Start-Server.bat` | 绑定R28就绪标记；属于旧版本包装 |
| `tools/deployment_r29/Start-Server.bat` | 绑定R29就绪标记，R30/R31历史打包器也复制此目录；现R50不读取它 |
| `tools/start_test.bat` | 自动下载开发依赖、删除/迁移部分run mods、重做旧资源或存档准备、配置GPU偏好，并自动选择旧R28世界。不是现R50交付或同一QA准入入口 |
| `tools/start_test_desktop.bat` | 硬编码D盘路径，转调旧 `start_test.bat play` |
| `tools/start_motion_lab.bat` | 转调旧 `start_test.bat motion`，继承上述旧准备行为 |
| `tools/start_pose_lab.bat` | 旧本机Blender动作台包装，缺少实验blend时自动调用重建；底层Python工具保留 |
| `tools/rebuild_pose_lab.bat` | 旧Blender动作台重建包装，默认固定本机Blender路径，会覆盖固定实验blend内未导出的编辑；底层Python工具保留 |

核查时Git跟踪的 `.log` / `.LOG` 文件为0，因此没有凭文件扩展名大扫历史日志、原生回执、截图或当前运行证据。此处没有删除个人文件或从个人PCL扫描清理。

R25–R31历史打包器仍保留源码，但依赖相应版本模板目录；复现完整旧包时应恢复对应Git提交，或从归档恢复所需原bat。五个旧静态校验脚本还读取 `start_test.bat`：`validate_eva_berserk_contract.py`、`validate_eva_logistics_contract.py`、`validate_eva_sync_contract.py`、`validate_geofront_contract.py`、`validate_local_eva_pack.py`。它们不在Gradle build或R50准备/打包链中，本次没有把失去旧入口的历史校验伪装成R50通过。历史手册中的旧bat命令按其原批次复现。

单文件恢复示例，只复制原文件，不自动执行：

```powershell
Copy-Item -LiteralPath 'D:/eva/.Codex/r50-retired-launchers/tools/start_test.bat' -Destination 'D:/eva/tools/start_test.bat'
```

## 当前明确入口

| 用途 | 入口 |
|---|---|
| 人工客户端试玩 | 对应已交付批次的 `Client_PCL.zip` 拖入PCL导入独立实例，与同批Server配套；本轮R50须待实际封包完成。历史R47导入见 `docs/PCL_IMPORT_R47.md` |
| 配套服务端 | 解压对应批次Server包，使用包内的 `Start-Server.bat`；Java17，按包内说明审阅EULA、存档和配置。这里退休的是仓库旧版本模板，不是已交付Server包的启动器 |
| 普通源码构建 | 项目根目录 `./gradlew build`；Windows PowerShell用 `.\gradlew.bat build` |
| 普通开发客户端 | 项目根目录 `.\gradlew.bat runClient`，显式选择开发世界；不会通过旧bat自动挑R28或启动旧迁移链 |
| R50同一QA制作检查 | `tools/prepare_r50_native_client.py` 准备/显式stage，再由 `tools/launch_rendered_client_r17.py --prepared-file` 启动所准备的单份launch配置 |

R50包由 `tools/prepare_r50_two_pack.py` 的现行计划制作。服务器启动文本继承已冻结R48 stage/server中的 `Start-Server.bat`、`start-server.sh`、`user_jvm_args.txt` 并生成所选R50包，未读取 `tools/deployment_r25..r29/Start-Server.bat`。当前 `tools/templates/r50`、PCL导入模板、生产classes及打包输入均保持。

下面是制作入口，针对Root已经建立的同一QA目录与所选jar，不是发行安装命令。本清理任务没有执行这些命令或启动游戏：

```powershell
python tools/prepare_r50_native_client.py
python tools/prepare_r50_native_client.py --stage --jar artifacts/rebuild_r49/release_inputs/projectseele-0.1.0-all.jar
python tools/launch_rendered_client_r17.py --prepared-file artifacts/rebuild_r50/native_client/launch.json
```

第一步准备配置；`--stage` 按既有身份、当前协议、所选jar和已有QA存档验证并布置独立QA客户端，不启动Java、不复制存档。最后一条实际启动正常Forge客户端。已准备配置仍须与Root最终编译版本一致，原生运行和用户验收不会因为删除旧入口而自动通过。

Blender底层 `tools/blender_pose_lab.py` 及实验文件未删除。需要复现旧动作台时，可在所选Blender中用该Python工具打开对应实验blend；重建和导出是独立、显式操作，旧bat的自动重建行为不作为现R50默认启动步骤。旧动作台使用范围见 [BLENDER_POSE_LAB.md](D:/eva/docs/BLENDER_POSE_LAB.md)。
