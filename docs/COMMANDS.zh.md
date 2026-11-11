# 游戏内指令

全部指令都在 `/seele` 下，只由 `src/main/java/com/projectseele/visual/SeeleCommands.java` 注册一次。根节点不设权限，每个一级子指令各自设权限：

- **玩家指令**：不需要 OP。处理器仍按原规则检查 NERV 通行证、机体归属、所在位置等。
- **管理员指令**：需要 OP（权限等级 2）。
- **开发指令**：需要 OP，而且只在开发构建里存在（JVM 参数 `-Dprojectseele.developerCommands=true`，或任意 `-PregionalBuild`）。

机体编号：NERV 机体写 `0|1|2`（零号机、初号机、二号机），`/seele eva` 还接受 `unit00`、`rei`、`all` 这类写法；UN 机体写 `un0|un1`。

新指令不要再单独注册 `seele` 根：在所属的类里写一个返回 `LiteralArgumentBuilder` 的方法，再挂到 `SeeleCommands`，权限写在挂接处。

## 玩家

| 指令 | 作用 |
|---|---|
| `/seele call [联络人]` | 接通指挥通信，默认美里；可写美里、律子、冬月、摩耶或 misato、ritsuko、fuyutsuki、maya。条件与 O 键相同 |
| `/seele route <目的地>` | 在总部公共通道里步行引导；`/seele route stop` 停止 |
| `/seele sortie status` | 当前作战简报 |
| `/seele sortie select <sachiel\|shamshel\|ramiel\|gaghiel>` | 选择作战 |
| `/seele sortie begin` | 开始已选的作战 |
| `/seele sortie retry` | 作战失败、机体和装备回收后，用同一批机体重试 |
| `/seele sortie cancel` | 结束作战并回收机体 |
| `/seele sortie support <0-4> <player\|npc>` | 追加支援机体：0–2 为零号机、初号机、二号机，3–4 为 UN-00、UN-01 |
| `/seele sortie collect <0\|1>` | 空手站在已回库的机体旁，领取待归还的装备 |
| `/seele cannon raise` | 升起屋岛固定炮 |
| `/seele cannon release` | 解除自己驾驶的机体对固定炮位的占用 |
| `/seele synch start\|abort` | 坐进实验栓后，请本槽技师开始或中止同步测量 |
| `/seele hangar door open\|close\|status <0\|1\|2>` | 机库后门应急开、关和查看状态 |
| `/seele recover <0\|1\|2>` | 本次出动的操作员申请地下回收 |
| `/seele crew [status]` | NERV 六个岗位的认领情况 |
| `/seele crew claim <岗位>` | 认领岗位：commander、operations、magi、unit00、unit01、unit02 |
| `/seele crew ready\|standby` | 把自己的岗位设为就绪或待命 |
| `/seele crew release` | 释放自己的岗位 |
| `/seele crew clear <岗位>` | 清除失效的岗位认领（需 OP） |
| `/seele un phone` | 打开联合国战略运输通信界面 |
| `/seele un status` | 两台 UN 机体和运输机的状态 |
| `/seele un deliver <un0\|un1> <x> <z>` | 呼叫运输机把机体投放到 X、Z 附近可承载的地面 |
| `/seele un recover <un0\|un1>` | 回收机体：已在库外接应平台就直接入库，否则呼叫运输机送回 |
| `/seele un dock <un0\|un1>` | 机体在库外接应平台时，由地面载台送回库位 |
| `/seele un cancel <un0\|un1>` | 取消运输；已起飞的机体先安全返回基地 |
| `/seele un board <un0\|un1>` | 走到机体附近后接入它的插入栓 |
| `/seele un hangar status\|drain\|door\|fill <un0\|un1>` | UN 试验舱状态、排液、舱门、注液，与墙上按钮同一套联锁 |

`/seele un` 整组需要 UN 卫星电话、正在驾驶 UN 机体或 OP。界面按钮仍由 UN 通信界面处理；输入的指令在聊天栏回复。

## 管理员（需 OP）

| 指令 | 作用 |
|---|---|
| `/seele tp [地点]` | 不带参数列出已安装的到达点（可点击），带参数传送过去 |
| `/seele enter` | 传送到 NERV 地面入口 |
| `/seele eva status [机体]` | 三台机体的后勤状态 |
| `/seele eva prepare <机体> [geofront\|surface\|hakone]` | 整备，可指定出口 |
| `/seele eva cancel\|launch\|recover <机体>` | 取消后续操作、发射、回收 |
| `/seele eva reset <机体>` | 抢救用：把机体、插入栓、驾驶员复位到机库 |
| `/seele armament deploy\|recall [rifle\|sword\|shield]` | 升起或收回武器井；不写类型时操作 128 格内最近的一座 |
| `/seele armament status` | 最近兵装升降站的状态 |
| `/seele city status` | 第三新东京市升降状态 |
| `/seele city raise` | 楼群升回地表（原 `tokyo3 restore`） |
| `/seele city lower` | 楼群降入地下（原 `tokyo3 retract`） |
| `/seele city recover` | 升降被中断（崩溃、断电）后停在故障状态时，从中断的那一步重做 |
| `/seele un reset <un0\|un1>` | UN 机体维护复位：回到库位，机体和插入栓复位；驾驶员在舱内时拒绝 |
| `/seele un defense\|power` | 切换 UN 基地防御系统、防御能源网 |
| `/seele admin server [status]` | 服务器、地图接入、驾驶舱画面和岗位概况 |
| `/seele admin server audit` | 出击前的有界检查，不重建地图 |
| `/seele admin transport status\|force_recover` | NERV 运输状态；强制回收卡住的运输任务 |
| `/seele admin npc reset <all\|名字>` | 恢复已登记 NPC 的生命和岗位 |
| `/seele admin transit status\|resume` | 地表列车状态；让空线路恢复发车 |
| `/seele admin install <存档内相对路径>` | 安装地图凭证（原 `/nerv r52 install`） |
| `/seele admin install_cancel` | 暂停待推进的地图安装 |
| `/seele admin equipment_update <目录>` | 原设备元数据更新 |

## 开发（需 OP，仅开发构建）

| 指令 | 作用 |
|---|---|
| `/seele dev pilot sync [set <0-100>]` | 查看或设置自己的同步率 |
| `/seele dev eva dummy start\|stop <机体>` | 训练驾驶员登机、离栓 |
| `/seele dev eva dummy status` | 训练驾驶员的阶段、路径和最近故障 |
| `/seele dev traversal [status\|normal\|strict\|bypass]` | 当前维度的穿行检查模式，重启恢复 normal |
| `/seele dev sortie` | 出击阶段与等待条件 |
| `/seele dev city setup\|audit\|overview` | 旧迎击战场搭建、审计、俯瞰 |
| `/seele dev city lower_now\|raise_now` | 维护用强制升降（原 `tokyo3 retract_now\|restore_now`） |
| `/seele dev city ramiel [start\|status\|abort]` | 拉米尔测试战 |
| `/seele dev siege status\|abort` | 使徒围城状态、中止 |
| `/seele dev geofront <子指令>` | 旧 GeoFront 搭建、审计与传送：setup、rebuild、enter、link、sortie_audit、surface、exit、audit、operations、dogma、overview、coastal entrance\|lake\|dock |
| `/seele dev facility_v2 <子指令>` | FacilitySchema v2 预检和历史建造：bootstrap、status、visit、programme、fabric、build |
| `/seele dev silo setup\|board\|status\|audit` | 发射井测试场 |
| `/seele dev motionlab setup\|reset\|enter\|weapon\|demo\|camera` | 动作实验室 |
| `/seele dev firstbattle begin\|cancel\|status` | 初战的独立回放（正式流程已由作战系统接管） |
| `/seele dev armament spawn_here\|remove` | 放置或删除兵装升降站 |
| `/seele dev visit <地点>` | port、un_base、un0_hangar、un0_gantry、un1_control、un1_gantry；随 UN 基地和港口的存档偏移移动 |
| `/seele dev seedscout <数量>\|seed <种子>\|fine <种子>\|anchor <种子>` | 海岸种子扫描（原 `/seele_coastal_seed_scout`） |

## 旧写法对照（R63 起已删除）

下列旧写法在 R62 还能用，R63 起已删除，输入会提示未知指令，请改用右边的新写法。机体参数只接受 `un0`、`un1`，旧的 `00`、`01` 也不再接受。

| 旧写法 | 新写法 |
|---|---|
| `/nerv` | `/seele crew` |
| `/nerv contact [联络人]` | `/seele call [联络人]` |
| `/nerv route <目的地>` | `/seele route <目的地>` |
| `/nerv crew ...` | `/seele crew ...` |
| `/nerv synch start\|abort` | `/seele synch start\|abort` |
| `/nerv hangar emergency open\|close\|status <0-2>` | `/seele hangar door open\|close\|status <0-2>` |
| `/nerv underground recover <0-2>` | `/seele recover <0-2>` |
| `/nerv server [status]\|audit` | `/seele admin server [status]\|audit`（`status` 现在也需要 OP） |
| `/nerv transport status\|force_recover` | `/seele admin transport status\|force_recover` |
| `/nerv npc reset <目标>` | `/seele admin npc reset <目标>` |
| `/nerv transit status\|resume` | `/seele admin transit status\|resume` |
| `/nerv r52 install\|install_cancel\|equipment_update` | `/seele admin install\|install_cancel\|equipment_update` |
| `/nerv debug sortie\|traversal ...`（仅开发构建） | `/seele dev sortie\|traversal ...` |
| `/un phone\|status` | `/seele un phone\|status` |
| `/un deliver 00\|01 <x> <z>` | `/seele un deliver un0\|un1 <x> <z>` |
| `/un recover\|dock\|cancel\|board 00\|01` | `/seele un recover\|dock\|cancel\|board un0\|un1` |
| `/un drain\|door\|fill 00\|01` | `/seele un hangar drain\|door\|fill un0\|un1` |
| `/seele tv status\|begin\|select\|retry\|cancel\|support ...` | `/seele sortie status\|begin\|select\|retry\|cancel\|support ...` |
| `/seele tv collect_equipment <0\|1>` | `/seele sortie collect <0\|1>` |
| `/seele tv raise_cannon\|leave_cannon` | `/seele cannon raise\|release` |
| `/seele tokyo3 status\|retract\|restore` | `/seele city status\|lower\|raise` |
| `/seele military status\|drain\|door\|fill` | `/seele un hangar status\|drain\|door\|fill un0` |
| `/seele military un01 status\|drain\|door\|fill` | `/seele un hangar status\|drain\|door\|fill un1` |
| `/seele military defense\|power` | `/seele un defense\|power` |
| `/seele military recover\|reset 00\|01` | `/seele un recover\|reset un0\|un1` |

已删除，没有旧写法：

- `/seele reset <机体>`：用 `/seele eva reset <机体>`。
- `/seele server`：用 `/seele admin server`。
- `/seele military un00|un01 recover|reset`：用 `/seele un recover|reset un0|un1`。
- `/nerv talk`：右键工作人员现在只打招呼，这条指令已没有入口；联络工作人员用 O 键或 `/seele call`。
- 原先直接挂在 `/seele` 下的开发指令（pilot、eva dummy、geofront、facility_v2、silo、motionlab、firstbattle、armament spawn_here|remove、tokyo3 的开发分支、siege、military visit、military un01 visit）和 `/seele_coastal_seed_scout`：都移到 `/seele dev`，见上表。
