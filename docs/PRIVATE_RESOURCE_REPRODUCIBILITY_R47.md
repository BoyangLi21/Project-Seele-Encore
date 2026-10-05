# R47 私有资源快照复现

公开源码仍提供项目自有资源和fallback画面；完整本机演示使用的未确认公开许可模型、动画、私有fat jar和源档不提交、不由本工具发布。`src/main/resources`内受保护的既有dirty geo00／geo02／unit01动画保持原样。R47新增**显式**`-Pr47FinalAssets`完整资源overlay入口，不默认覆盖私有包；旧R45冻结资源入口保留，两种release overlay互斥。

已有用户自己的实际Full Client R47包时，可离线提取其实际协议55 mod fat jar里的资源，到新建的Git忽略本地目录。`tools/extract_release_resources_r47.py`只读取本地ZIP，解析`SeeleNetwork.PROTOCOL_VERSION`的真实ConstantValue=55，并检查R47入口类；这里的55是网络协议，不是Java class-file major。

```powershell
python tools/extract_release_resources_r47.py `
  --jar 'D:/MyPrivateFullClient/mods/projectseele-0.1.0-all.jar' `
  --out '.Codex/r47-private-resources'
```

工具拒绝缺少入口／协议错误的jar、非空目标、非Git忽略目标、输出链接／越界、ZIP重复／大小写冲突／危险路径及非普通文件。通过所有入口与路径校验后，仅以原字节独占创建`assets/`、`data/`、`META-INF/mods.toml`、`pack.mcmeta`和`projectseele.mixins.json`。不提取class、嵌套依赖jar、存档、runtime/config，也不重算或编辑模型、联网、启动JVM或计算SHA。失败只撤销本次创建的文件／空目录，不递归删除已有数据。

后续由负责人在允许构建的时机，使用R47完整选中资源入口；从自己的实际Full Client提取的完整资源目录也可作此输入：

```powershell
.\gradlew jarJar -Pr47FinalAssets='.Codex/r47-private-resources'
```

本轮负责人选中目录的例子为`-Pr47FinalAssets='artifacts/rebuild_r47/assets'`。新入口必须有`assets/projectseele/sounds.json`和`data/projectseele/dimension_type/geofront.json`，否则拒绝；只按原字节完整复制白名单 **`assets/**`、`data/**`、`META-INF/licenses/**`**。`META-INF/mods.toml`必须沿当前source的`processResources`展开，`projectseele.mixins.json`必须来自当前source，不能被旧snapshot或overlay覆盖。无需把私有模型复制回main或提交仓库。

旧`-Pr45FinalAssets`入口需要其R45 `ASSET_FROZEN.json`并按旧流程验证，该清单记录旧R45内容，当前sounds等已变；本轮没有重做SHA，也不把该旧manifest称本轮hash通过。`-Pr47FinalAssets`与`-Pr45FinalAssets`同时指定会拒绝。旧`-PseeleResourceSnapshot`整目录入口仍是历史复现机制；本轮发行选择新R47白名单入口，避免旧快照漏新mixins或覆盖当前注册元数据。

生成的`projectseele.refmap.json`不从旧jar提取，由当前源码注解处理器生成。两包脚本对最终实际fat jar做必要presence回读：mods.toml不能残留`${…}`模板，client mixin列表必须包含`client.LclWaterResourceReloadR47Mixin`与`client.MovingElevatorRenderOriginR47Mixin`及其class；还有新休息室／持久坐席／最高卡／SEELE props类和实际迁岗／返程诊断入口。这里是防漏资源／漏合入检查，没有SHA重验，manifest、构建或presence均不是原生操作／画面／艺术通过证据。

Jar资源不足以复现实际动作准入。必须从**同一个实际Full Client实例**保留其`projectseele-local-maps/`及配套`config/`，包括原`combat_bundle_r44.json`、真实`eva_body_r44.json`、各variant gameplay clips、locomotion capture及原support／weapon handling admission。不得混用另一个旧client的数据，不根据菜单或文件名伪造ready，不重新生成这些文件的准入字段；这些仍是私有运行资料，不放入公开资源或源档。服务端／客户端组装应沿用同一来源的配置与运行数据，所需第三方mods仍按原依赖和许可管理，本CLI不替其打包。

该工具和说明可以提交；输入fat jar、提取目录、运行数据、私有源码归档和任何许可未清模型都继续留在忽略的本地路径。源码assembly与私有演示交付范围保持分开。文档代理没有执行提取、构建、测试或SHA；负责人实际资源重包／构建及原生结果分别记录，不以本页文字替代结果。
