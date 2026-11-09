# Prompt 手册 — 给未来的 Claude Code 会话

> 用法：换机器/新会话时，从这里复制对应 prompt 直接粘贴给 Claude Code。
> 所有 prompt 假定在仓库根目录打开会话（Claude 会自动读到 CLAUDE.md）。

---

## P0 · 新机器首次接手（换电脑后的第一条消息）

```
你接手一个进行中的 Minecraft Forge 1.20.1 模组项目 Project SEELE（EVA 世界观，开源）。
仓库：git@github.com:BoyangLi21/Project-Seele.git

请按顺序执行：
1. 通读 CLAUDE.md、docs/ROADMAP.md、docs/SETUP.md，理解项目现状与协作约定
2. 体检本机环境：java -version（需 17）、git 及其身份配置、SSH 连 GitHub 是否通
   （ssh -T git@github.com）、仓库是否已 clone。缺什么按 SETUP.md 处理：
   你能自动做的直接做，需要 GUI 安装的给我下载链接和步骤
3. 环境就绪后跑 ./gradlew build（新机器首次构建要反编译 MC，耐心等），
   再跑 runClient 冒烟测试（日志验证套路见 CLAUDE.md「验证套路」）
4. 汇报：环境状态 + ROADMAP 中下一个未完成任务 + 你的开工建议，等我确认再动代码
```

## P1 · Phase 1 收尾开工

```
继续 Project SEELE 的 Phase 1 收尾。读 docs/ROADMAP.md §2，按任务表顺序实现
（1.1 警报系统 → 1.2 光束渲染 → 1.3 十字爆炸 → 其余）。
要求：每完成一个任务就 build + runClient 日志验证，通过即 commit（署名规范见
CLAUDE.md），攒 2-3 个任务 push 一次。涉及画面效果的，停下来列出「我该在游戏里
看什么」，等我目视确认再继续。数值改动先报我拍板。
```

## P2 · Phase 2 EVA 初号机开工

```
开工 Project SEELE 的 Phase 2（可驾驶初号机），读 docs/ROADMAP.md §3。
第一步先接 GeckoLib：用 Modrinth API 确认 geckolib-forge-1.20.1 当前最新 4.x 版本，
接入 build.gradle 并跑通一个空的 GeckoLib 实体，然后按 2.1→2.9 顺序推进。
铁律：模型先用程序生成的占位方块人形，玩法逻辑优先，美术后行。
驾驶手感（2.1/2.2）做完先停，给我一版可玩的试驾，我反馈后再继续武器和暴走。
```

## P3 · Phase 3 使徒图鉴开工

```
开工 Phase 3（AT 力场与新使徒），读 docs/ROADMAP.md §4。
先做 3.1 AT 力场通用机制（这是整个 Phase 的地基，设计成使徒注册即用的 Capability），
用 Ramiel 当第一个试点验证破防流程，然后按 Sachiel → Shamshel → Zeruel 顺序做。
每只使徒完成后给我一份「行为差异说明 + 测试清单」。
```

## P4 · Phase 4 场景开工

```
开工 Phase 4（GeoFront/发射井/可升降城市），读 docs/ROADMAP.md §5。
从 4.1 GeoFront 维度开始（datapack dimension + 自定义 ChunkGenerator）。
注意 ADR-4：可升降楼用方块交换实现，不引入 Valkyrien Skies 依赖。
授权地图清单在 §9，涉及联系作者的事项列出来交给我。
```

## P5 · Phase 5 第三次冲击开工

```
开工 Phase 5（SEELE 剧本与第三次冲击），读 docs/ROADMAP.md §6——尤其 6.2 的分镜表。
顺序：5.1 朗基努斯 → 5.4 LCL 流体 → 5.2 Terminal Dogma → 5.3 量产机 → 6.2 三冲事件。
三冲事件先搭 SavedData 状态机骨架 + 各阶段空实现 + 调试指令（/seele dev impact <阶段>，挂到 SeeleCommands 的 dev 分支，见 docs/COMMANDS.zh.md），
让我能跳阶段验收演出，再逐阶段填充视觉。生命之树渲染是视觉巅峰，单独留一轮打磨。
```

## 专项 Prompt

**视觉打磨轮**
```
本轮只做视觉：读 ROADMAP 任务 1.2/1.3。用直连顶点渲染（参考 RamielRenderer 的
八面体画法）实现 <光束/十字爆炸/生命之树>。做完给我截图检查点清单。
着色器相关放 client config 开关，保低配可关。
```

**音效生成轮**
```
为 <目标音效列表> 生成原创合成音效：写脚本（正弦/锯齿叠加+ADSR包络）产 44.1kHz ogg，
存 assets/projectseele/sounds/，注册 sounds.json，生成器脚本入库 tools/。
红线：不得使用/模仿原作音频的旋律。完成后给我逐个试听的指令清单（/playsound）。
```

**数值平衡轮**
```
读 CLAUDE.md 数值表。我的体验反馈：<填写>。给出调整建议（前值→后值+理由），
我确认后改 Config 默认值并更新 CLAUDE.md 的表。
```

**发布准备轮**
```
按 ROADMAP §7 走发布检查：CI、双平台元数据（CurseForge/Modrinth 的描述、截图位）、
CHANGELOG.md、CONTRIBUTING.md（招募模型师/建筑师）、合规自查（§9 红线逐条过）。
```

## Bug 反馈模板（用户 → Claude）

```
【现象】（一句话，最好带截图）
【复现】我做了什么 → 发生了什么 → 期望是什么
【环境】单人/局域网；创造/生存
日志在 run/logs/latest.log，崩溃报告在 run/crash-reports/，你自己去翻。
```
