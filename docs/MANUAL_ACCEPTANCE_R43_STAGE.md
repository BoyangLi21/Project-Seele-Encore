# R43 阶段验收包

这是按你要求提前收尾的阶段包。全域质量重构尚未完成，下一轮继续；本包不宣称最终美术或战斗手感已达标。

Minecraft 1.20.1 / Forge 47.4.10 / Java 17，协议 45。客户端和服务端请使用本批次。新存档名称为 **Project SEELE R43 阶段验收**，文件夹 `SEELE_R43_STAGE_WORLD`。沿用你实际试玩 R42 的玩家、机体、插入栓、NPC、任务及交通进度，原 R42 保留。

## 安装

- 本机 PCL 安装完成后，选择 **Project SEELE R43 Stage**。原 R42 实例保留，可用于对照。
- 换电脑时，将 **Client.zip** 拖入 PCL。模型、模组、存档、材质、光影都已内置；Minecraft/Forge 基础运行库若缺失，启动器仍可能补齐。
- 服务器：解压 **Server.zip**，将 **World.zip** 内容放入服务器的 `SEELE_R43_STAGE_WORLD`，该文件夹下直接包含 `level.dat`。确认 Minecraft EULA 后设置 `eula=true`，以 Java 17 运行 `Start-Server.bat`。
- **Textures.zip / Shaders.zip** 是独立资源备份，与 Client.zip 内置资源相同，不必重复安装。
- 客户端建议分配 6–8 GB。实例中的 `Enable-Visuals.bat` 启用内置光影；也可在视频设置中开关。总指挥席后拉杆继续控制指挥室照明。

## 进入世界与快速传送

`/seele enter` 固定传送到 SEELE 世界的 NERV 地面入口（X=-360.5、Y=81、Z=730.5）。输入 `/seele tp` 可查看并点击完整地点列表。

| 指令 | 目的地 |
|---|---|
| `/seele tp hanger` | EVA 机库登机廊，接替旧 `geofront hangar` |
| `/seele tp entrance` | NERV 地面入口 |
| `/seele tp command` | 指挥室入口 |
| `/seele tp dogma` | 终极教条前厅 |
| `/seele tp observation` | 机库上层观察廊 |
| `/seele tp station` | NERV 总部车站 |
| `/seele tp hanger_station` | EVA 机库车站 |
| `/seele tp tokyo3` | 第三新东京中央区域 |
| `/seele tp hakone` | 新箱根中央车站 |
| `/seele tp port` | 港口登舰栈桥 |
| `/seele tp airport` | NERV 航空基地航站楼 |
| `/seele tp un` | 联合国军事基地 |
| `/seele tp un_hangar` | 联合国试验机库人员走廊 |
| `/seele tp rei` | 绫波丽公寓门外 |

指令需要开启作弊／服务器 OP 权限。固定地点会检查脚下支撑与身体净空；被改建或设备占据时会拒绝传送，不会自动填改地图。

旧的地图生成、原型战斗和动作实验指令已从正式指令树移除。现用战役、整备、发射、回收、城市升降、武器部署和 UN 控制继续保留。需要开发工具时才显式使用 JVM 参数 `-Dprojectseele.developerCommands=true`；普通启动不用加。

## 建议先验收这些

1. **眼睛状态**：正常初号机应为原涂装眼色，暴走红眼，暴走收尾停机后黑眼。若载入时机体已经处于上次战后的停机状态，请先回库维修再查正常状态。
2. **初号机普通攻击**：连续两段左键、移动后出拳、出拳后转身或蹲起。初号机的地面空手片段使用新候选；其余四机的攻击片段仍沿用 R42。五机的基础待机／走／跑已更新，并修复蹲起归零、疾跑切入战斗步态时的硬切。
3. **速度**：普通拳、刀攻击和 B 踢已按要求提速 1.5 倍。100 同步率时，实测普通拳 21/23→14/15 tick，刀 45/33→30/22 tick，B 踢 14→9 tick；普通攻击重复间隔 40→27 tick。伤害未改；空手右键重击和枪械射速本次未改。
4. **发射许可**：先取消任务，再入栓等一会，应保持待命；选择萨基尔任务并编入机体后，再检查自动整备与发射。取消任务应撤销后续自动命令，已经开始的机械转移需要先安全停靠。手动命令仍可使用。
5. **萨基尔收尾**：正常战斗触发 50 血暴走，再进入处决，重点看拉拽双臂、前扑和最终爆炸。已去掉前空翻和中途十字架，保留最后自爆。异常地形、重登中断和远端表现仍未全部验证。
6. **地图**：走机库车站电梯前室、站台北侧、双向站台门和路牌周围。修复包括完整旧隔墙／低顶棚冲突、端部半扇门、挡在下车口的指示牌支架、Dogma 步道护边、UN 湿舱旧步道与压力壁。路线图现为双列站序，突出本站及下一站。
7. **电梯**：从门外呼叫，实际走入、乘坐、走出，再反向乘坐；尤其检查冷启动后的第一次呼叫。不要只传送进轿厢判断。

取消和查看任务：

```mcfunction
/seele tv cancel
/seele tv status
```

几个便于检查的落脚点：

```mcfunction
/execute in projectseele:geofront run tp @s 95.5 -442 -45.5
/execute in projectseele:geofront run tp @s 124.5 -442 -45.5
/execute in projectseele:geofront run tp @s -1073.5 119 560.5
/execute in projectseele:geofront run tp @s 6394.5 77 -6192.5
```

## 操作

WASD 移动，Ctrl 跑，空格跳，Shift 蹲，Z 趴／起身，左键普通攻击，右键重击，B 踢，R 切武器，G 力场，逗号键抓取／投掷，V 脱离，O 驾驶时联系指挥室。

第一幕：NERV 电话 → 美里 → 作战记录 → 萨基尔，选择亲自或驾驶员出战。需要手动排查时：

```mcfunction
/seele tokyo3 retract
/seele eva prepare unit01
/seele eva status unit01
/seele eva launch unit01
/nerv transport status
/nerv transport force_recover
```

手动发射请等待 `SILO_READY`。完整旧流程见同包《第一幕流程.md》。

## 本包边界与下一轮

- 新跳跃试片的观感仍不合格，**未采用**，继续沿用原跳跃片段。UN 外形、全体攻击动作、使徒反馈及吼叫尚待继续精修。
- 刚规划的四处金字塔东翼楼梯前室开口**未施工、未放入本包**。
- 全部车站出入口／换乘／真实开门上下车、全图城市与地下美术、剩余孤立空间仍未全部关闭。
- 已有实测包括五机攻击时序、任务门控与原三机出动、25 趟指定乘梯、站台接口修复、852 段建筑楼梯的 5,112 次服务器碰撞通行。它们不等于全地图、真实双客户端或最终手感验收。
- 下一章仍是设计稿，尚未交付新的完整可玩剧情。
- 准备交付副本的检查结果与资源校验值见 `RELEASE.json`。本阶段没有新增“用户认可”记录，等待本次人工验收。
