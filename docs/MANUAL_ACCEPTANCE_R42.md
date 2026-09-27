# R42 安装与验收

Minecraft 1.20.1 / Forge 47.4.10 / Java 17，协议 **45**。客户端与服务端均须 R42；发布状态和校验值见 `RELEASE.json`。延续实际试玩的 R41 玩家、机体、插入栓、任务和交通进度；原 R41 实例保留。

## 启动与安装

- 本机入口 `D:\eva\start_eva_test_r42.bat`。`--check` 只检查准备；`--no-shaders` 关闭光影。
- **Client.zip** 拖入 PCL，模型、模组、存档、材质及光影已内置，只可能补齐缺失的 Minecraft／Forge 基础库。
- **Server.zip** 解压，将 **World.zip** 内容放进 `SEELE_R42_WORLD` 文件夹，其中直接包含 `level.dat`。确认 Minecraft EULA 后设置 `eula=true`，以 Java 17 运行 `Start-Server.bat` 或 `start-server.sh`。
- **World.zip** 可单独装进客户端 `saves/SEELE_R42_WORLD`。
- **Shaders.zip／Textures.zip** 是独立资源备份，Client.zip 已包含相同资源。

客户端建议 6–8 GB。实例内 `Enable-Visuals.bat` 选择已内置的 `ComplementaryUnbound_r5.3_SEELE_R39.zip`，无须下载。总指挥席拉杆控制指挥室灯光。开发 BAT 共用源码运行目录，完整回退请使用原 PCL R41。

## 本次重点

1. 五机分别行走、跑步、蹲趴、前爬、起身，近看左右手四指及拇指；持枪再查一次。
2. 起跳到落地完整看一遍；两段普通拳的第二拳中途按蹲或趴，检查腿部／上肢是否翻折、突跳。此次普通跳跃实测滞空约 1.25 秒。
3. 与萨基尔交战，使初号机自然降至 50 血，检查静默、吼叫、红眼及自动收尾。结束后应停机黑眼，不能立刻再次暴走；随后电话回收检修。
4. 开光影，进大指挥室与最高会客厅，从图案正面、墙背后、楼上看 NERV／生命之树；墙后不应出现图案，再关光影对照。
5. 机库观察层电梯实际走过门槛并乘坐三层，检查关闭层门与左右侧护、中文楼层；按路牌到指挥室、机库和车站。
6. 从站外按入口牌走到闸机和站台，核对箭头、下一站和运行方向；查看更新的墙面及座椅。

反复反馈的三个区域可用以下安全落脚点附近查看：

```mcfunction
/execute in projectseele:geofront run tp @s 95.5 -442 -45.5
/execute in projectseele:geofront run tp @s 104.5 -394 -45.5
/execute in projectseele:geofront run tp @s 84.5 -394 -269.5
```

分别检查站厅临空边、旧扶梯附墙、自动步道双格出口。本轮复核实际画面，原 R41 修复保持。

## 操作与第一幕

WASD 移动，Ctrl 跑，空格跳，Shift 蹲，Z 趴／起身，左键两段攻击，右键重击，R 切换已持武器，G 力场，逗号键抓取／投掷，V 脱离，O 驾驶时联系指挥室。

NERV 电话 → 美里 → 作战记录 → 萨基尔，可亲自出战或指定驾驶员，并呼叫其他机体支援。入栓后美里和律子自动整备、转移及发射。详细流程见同包《第一幕流程.md》。管理员排查：

```mcfunction
/seele tokyo3 retract
/seele tv status
/seele eva prepare unit01
/seele eva status unit01
/seele eva launch unit01
/nerv transport status
/nerv transport force_recover
```

手动发射等待 `SILO_READY`。暴走剧情保护不等于普通战斗无敌；停机后先回库检修再出击。伤害、血量、冷却不变，起跳初速 **6.2→5.3**，重力增量 **0.32→0.42**。

原生功能与画面已做复核，最终手感与美术仍需实际试玩评价。覆盖范围和旧验证记录见《R42整改与验证.md》；本地服务端冷启动不等于远程多人网络测试。
