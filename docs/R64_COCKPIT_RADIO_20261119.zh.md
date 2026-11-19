# R64 同步率实验中的驾驶舱无线电

2026 年 11 月 19 日的四阶段实录中，英文驾驶舱把说话人显示为 Ritsuko Akagi，右上角仍出现中文正文。原始画面位于采集批次 `20261119_144225`，平均 82.65 fps；含中文的旧截图和录像记录的是补译前版本。

根据这次实录的聊天记录定位到五条旧提示。受击、开始自律和自律减弱由 `CombatCommandBriefR47` 发出，无外部供电时的惊呼由 `EvaBerserkMotionR34` 发出，主电源锁止提示由 `EvaShutdownR30` 发出。工作人员原来把频道和台词拼成字面字符串；驾驶舱能够识别人物，却没有可供客户端翻译的正文。

现在这些提示将 Minecraft 可翻译文本组件发给接收者。频道、机体简称与正文分别按接收者的语言显示，UN 机体沿用原序号。受击的重伤分支和停机的损毁分支也使用同一传文方式。中文语言表逐字保留旧台词，普通聊天与右上角通讯沿用原来的说话人、收件人和颜色。

英文初号机受击时显示 “Unit-01 took a hit. Pilot, how are the controls responding?”，暴走开始时显示 “Unit-01 is moving on its own. Control readings are abnormal. Check on the pilot first.”，路由至原说话人 Ritsuko Akagi。主电源锁止仍归为系统通知。

正式 JAR 与增量替换后的测试 JAR 分别通过 38 项双语检查。检查通过 Minecraft 文本组件 JSON 往返、客户端语言表与驾驶舱实际使用的说话人分类器，覆盖中英文、零号机／初号机／二号机／UN 机体、受击／重伤／自律起止、惊呼和停机通知。JDK 17 离线构建成功，全套检查 103/103。实际游戏画面可用相同小存档复录核验。

本次测试包仅替换 `CombatCommandBriefR47.class`、`NervStaffDialogue.class`、`EvaBerserkMotionR34.class`、`EvaShutdownR30.class` 与 `en_us.json`、`zh_cn.json`。采集用 `PilotCockpitReviewR64.class` 经 SHA256 核对保留原字节。
