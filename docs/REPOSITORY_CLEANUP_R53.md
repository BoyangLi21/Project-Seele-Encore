# R53 仓库清理 · 2026-10-19

负责人在人工试玩期间要求清理仓库、删除无用测试代码并更新 README，允许加入实际宣传图。

## 范围和恢复

基线：`289dfed3f567b527e4f5d514d8d3cc73eb382ba4`。在独立分支 `codex/repo-cleanup-20261019` 整理；不改正在试玩的客户端、存档、原始美术、历史检查结果或其他工作树中的未提交候选。

下面 19 个入口不被当前构建或保留的工具调用，固定依赖已退役 R23–R44 的安装目录、批次收据和测试包。R43 包检查仅导入同批删除的 R42 入口。删除工作树中的脚本，完整源码仍在上述 Git 提交中。

| 删除的入口 | 原用途 |
|---|---|
| `tools/test_packaged_server_r25.py` | 固定历史包的独立服务端启动检查 |
| `tools/test_packaged_server_r26.py` | 固定历史包的独立服务端启动检查 |
| `tools/test_packaged_server_r27.py` | 固定历史包的独立服务端启动检查 |
| `tools/test_packaged_server_r28.py` | 固定历史包的独立服务端启动检查 |
| `tools/test_packaged_server_r29.py` | 固定历史包的独立服务端启动检查 |
| `tools/test_packaged_server_r30.py` | 固定历史包的独立服务端启动检查 |
| `tools/test_packaged_server_r39.py` | 固定历史包的独立服务端启动检查 |
| `tools/test_packaged_server_r40.py` | 固定历史包的独立服务端启动检查 |
| `tools/test_packaged_server_r41.py` | 固定历史包的独立服务端启动检查 |
| `tools/test_packaged_server_r42.py` | 固定历史包的独立服务端启动检查 |
| `tools/test_packaged_server_r43_stage.py` | 固定历史包的独立服务端启动检查 |
| `tools/test_packaged_server_r44_stage.py` | 固定历史包的独立服务端启动检查 |
| `tools/verify_install_r23.py` | 固定历史施工批次的安装回读 |
| `tools/verify_install_r24.py` | 固定历史施工批次的安装回读 |
| `tools/verify_install_r25.py` | 固定历史施工批次的安装回读 |
| `tools/verify_install_r26.py` | 固定历史施工批次的安装回读 |
| `tools/verify_install_r28.py` | 固定历史施工批次的安装回读 |
| `tools/verify_install_r29.py` | 固定历史施工批次的安装回读 |
| `tools/test_visual_installer_r29.ps1` | R29 专用光影安装器的本地检查 |

需要查阅旧脚本时，可读取指定历史版本而不覆盖当前文件：

```powershell
git show 289dfed3f567b527e4f5d514d8d3cc73eb382ba4:tools/test_packaged_server_r25.py
```

若需完整复现旧环境，应在独立历史检出中恢复该批工具与其输入，不能只把旧测试指向当前玩家存档。R25 的历史文档仍保留当时工具名，不将历史说明伪装成当前入口。

## 其他整理

- README 改为 R53 项目介绍、当前状态、源码启动、驾驶操作与文档入口，移出 R47/R50 内部流水账；原内容可从基线提交查阅。
- 加入 GeoFront 的实际离线宣传图网页预览与来源记录；保留源图 SHA-256、处理方式和实时画质边界。
- 增加 tools 与 Java 回归检查说明；区分默认 check 任务、需要额外夹具的入口以及原生人工验收。
- SETUP 补上新克隆必需的依赖下载步骤。
- 忽略 Python 缓存、根目录 JVM 崩溃日志和操作系统元数据，防止再次误入 Git。
- 保留所有现有 Java 回归、物理夹具、共享导入模块和生产代码。版本号旧、未被默认 check 调用，都不足以证明测试无用。

## 验证与交付

2026-10-20 已完成保留脚本对19个删除文件的引用扫描：没有仍需这些旧入口的可执行引用。新增文档的本地链接可解析，完整构建通过。历史说明中的旧文件名仍保留，便于从对应提交复现当时环境。

本次清理仅包含上述历史脚本、忽略规则及工具/检查/安装文档；游戏修复和新的机械恢复回归任务分别提交，不借清理混入未经实机复核的候选。README及宣传图已于上一暂停点单独推送到main；本清理提交继续在当前工作分支交付。
