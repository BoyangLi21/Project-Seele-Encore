# EVANGELION:Encore R50 测试版

本轮先修好原机吊装，再交付测试版Server与Client_PCL两包；大型运输井、多机并行、远距离屋岛与升炮/趴姿设备接驳留下一轮。这是用户同意的测试版范围，不是全图、全部动作或完整两战已验收。

本说明封包前编写，实际包制作/回读结果见交付回执及聊天。拟定包为delivery/Project_SEELE_Encore_R50_20261006_Server.zip与delivery/Project_SEELE_Encore_R50_20261006_Client_PCL.zip，不在这里预填通过。

## 安装

- `Project_SEELE_Encore_R50_20261006_Client_PCL.zip`：在PCL选择整合包导入，直接选完整ZIP，不先解压、不把它当普通mod扔进mods。标准CurseForge manifest v1与overrides包含21模组（主mod+20依赖），Minecraft1.20.1、Forge47.4.10，用Java17和独立游戏目录。客户端不带world，连接Server测试世界。
- `Project_SEELE_Encore_R50_20261006_Server.zip`：解压到独立服务端目录，保留内含`SEELE_R50_WORLD`与`server.properties`的level-name对应关系。使用Java17，阅读并自行接受Minecraft EULA后设置eula=true；Windows执行`Start-Server.bat`，其他系统用`start-server.sh`。默认最大堆20G，含17模组、Forge运行库、NERV图标，MOTD为EVANGELION:Encore R50测试版。
- 同机客户端连接本机服务端；远程连接使用实际服务器地址和server.properties端口。保留原PCL/旧实例及个人按键，不删除其他mods。O为通讯，F8为光影选择，默认不启用光影；首次本地视觉初始化由本包脚本管理。

## 原进度保护

Server只从唯一冷施工源`artifacts/rebuild_r49/construction/SEELE_R49_WORLD`流式取world，保原玩家、三原机、栓、驾驶员、任务、库存与MTR交通进度。QA的试战/回收/坐标结果不整包覆盖发行world，不声称已合并远端后来进度。登录应保持原玩家身份；UUID不同不会自动继承另一个玩家的背包。旧R48和未发布R49源档保留。

## 本轮已证与待验

已证：原02V后原机地面receiver回库；原00/01NPC真实出站/领货/库存归还；屋岛原盾两束拦截与同柜维修，build18/gen2首炮Shots1及实际350→150.08伤损；8板真实钻进/修复；原01地下飞机断电闭环、有电准入与一次活CRUISE存盘重登后回库。仅有电准入早于断电24秒，不能写全程有电；原栓05:44为OCCUPIED1真人仍乘坐，后来才正常离座。

launch18/build21脚部已放过，hand_r#0仍在39/109/452承载面浅交叠2.93cm被拒。新纯up支承条件及真实73骨/19独立凸部件全上扫234.975m离线blockingPairs0；最终build23完整构建及针对性碰撞回归已通过，不是native起飞。CU两次未报foreground pid，用户09:12:39正常退出，不再反复开；最终实际起飞交用户验收。首炮不等第二炮/屋岛胜利；炮后Readyfalse尚未完成服务。港区完整接战、全飞机姿态/节点/NPC/其他中断和自由机体重登、全动作/光照/人物手感、人员实走与用户美术仍待验。

41大项按主状态为9项有有限原生证据、31项已有实现/资源/资料候选待场景或人工、1项两包/Git交付执行尚未完成；不是31项没实现。真实未制作的能力和下一轮范围另列。[完整事实表](FINAL_STATUS_R50.md)、[操作手册](MANUAL_R50.zh.md)、[下一轮](NEXT_ROUND_R50.zh.md)。

单机机场、短距屋岛阵地、八层厚度与按钮库存是本项目工程改编，不声称TV原图或官方参数。原总部/Terminal后半侵入、同原紧急栓运输、TV舰船动态航行/沉降未制作。测试版保留这些边界，不以构建/安装数冒称用户认可。
