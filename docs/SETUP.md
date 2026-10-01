# 新机器环境搭建指南（Windows）

> 适用场景：换开发机（如 RTX 3070 机器）后从零恢复开发环境。
> 分工：标 🖱 的步骤用户手动操作，其余 Claude Code 可代劳。

## 1. 安装清单

| 软件 | 获取方式 | 备注 |
|---|---|---|
| 🖱 JDK 17 (Temurin) | https://adoptium.net/temurin/releases/?version=17 （慢就用清华镜像 https://mirrors.tuna.tsinghua.edu.cn/Adoptium/17/jdk/x64/windows/ ）| MSI 安装时把 **Set JAVA_HOME** 勾上 |
| 🖱 Git for Windows | https://git-scm.com/download/win | 默认选项即可 |
| 🖱 IntelliJ IDEA | 用户自有付费版 | Community 也够用 |
| 🖱 Blockbench | https://www.blockbench.net/downloads | Phase 2 建模用，可后装 |
| Minecraft 官方启动器 | 可选 | 开发用不到（runClient 自带离线客户端），只有想在正式游戏里玩发布版 jar 时才需要 |

## 2. Git 身份与 SSH（Claude 可代劳生成，🖱 网页添加公钥）

```powershell
git config --global user.name  "Soryu_Asuka"
git config --global user.email "liboyang621@gmail.com"

# 生成 SSH key（如新机器没有）
ssh-keygen -t ed25519 -C "liboyang621@gmail.com"
# 🖱 把 ~/.ssh/id_ed25519.pub 内容添加到 GitHub（账号 BoyangLi21）→ Settings → SSH keys
ssh -T git@github.com   # 出现 "Hi BoyangLi21!" 即成功
```

## 3. 克隆与首次构建

```powershell
git clone git@github.com:BoyangLi21/Project-Seele-Encore.git
cd Project-Seele-Encore
.\gradlew build      # 首次要下载依赖并反编译 MC：强 CPU 机器约 5-15 分钟
.\gradlew runClient  # 冒烟测试：进主菜单 → Mods 列表应有 Project SEELE
```

说明：
- Gradle wrapper 已指向**腾讯镜像**（`gradle/wrapper/gradle-wrapper.properties`），国内直接快
- `gradle.properties` 已启用 daemon 与 4G 堆内存，无需调整
- IDEA 打开项目根目录会自动识别 Gradle；Gradle JVM 选 17（通常自动跟 JAVA_HOME）

## 4. 已知坑

- PowerShell 5.1 的哈希表键**不区分大小写**（写生成脚本时踩过：`'g'` 和 `'G'` 算重复键）
- PowerShell 5.1 把**无 BOM 的 UTF-8 .ps1 当 ANSI(GBK) 解析**——脚本里写中文注释会炸出 ParserError（踩过：gen_sounds.ps1）。`tools/` 下脚本一律 ASCII 注释
- 控制台中文可能乱码（GBK/UTF-8），日志判断以关键英文串为准（如 `Project SEELE initialized`）
- 杀掉游戏窗口后对应的 gradle runClient 任务会报 exit 1，属正常现象
- `.claude/` 是本机会话数据，已 gitignore，换机不迁移、不提交
- 装不了 MSI（无管理员/不想动系统）时可用 **zip 版 Temurin 17**：解压后 `setx JAVA_HOME <目录>`，Claude 会话内跑 gradlew 前需内联 `$env:JAVA_HOME=...`（新 shell 才读得到 setx）
- **GeckoLib 在开发环境启动崩溃**（`TextureManagerMixin FAILED during APPLY ... m_118506_`）：它的 mixin refmap 是 SRG 名而 userdev 跑 official 映射。修复已入库（`build.gradle` runs 里的 `mixin.env.remapRefMap` 两行 + 跑一次 `gradlew createSrgToMcp`）。换机后首次 runClient 前记得跑 createSrgToMcp（build/ 不进版本库）

## 5. 交接检查单（新机器就绪标准）

- [ ] `java -version` → 17.x
- [ ] `ssh -T git@github.com` → Hi BoyangLi21!
- [ ] `gradlew build` → BUILD SUCCESSFUL
- [ ] `gradlew runClient` → Mods 列表见 Project SEELE，日志有初始化行
- [ ] 能 `/summon projectseele:ramiel ~ ~5 ~20` 并看到蓝色八面体
