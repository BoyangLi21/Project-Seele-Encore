# 构建、启动与打包

## 开发环境

使用 Git、64 位 JDK 17、Python 3.11 或更新版本。项目锁定 Minecraft 1.20.1、Forge 47.4.10，仓库自带 Gradle Wrapper。先在仓库根目录确认 `java -version` 和 `python --version`，再执行以下命令。

```powershell
python tools/bootstrap_dev_dependencies_r24.py
.\gradlew.bat build
.\gradlew.bat runClient
```

在 Linux 或 macOS 上用 `./gradlew`。源码构建的 JAR 位于 `build/libs/`。发布运行环境使用带嵌入依赖的 `projectseele-0.1.0-all.jar`。开发启动使用 ForgeGradle 的运行目录。首次下载由引导脚本校验固定依赖；已备妥全部依赖的机器后续可执行 `.\gradlew.bat --offline build`。在游戏中选新世界即可验证公开代码的注册和启动。完整 GeoFront 试玩还需取得相应世界、模组和资源的使用授权。

## 制作配套的客户端与服务端

同一版本应选定源码提交、完整停服世界、配套模组目录、该存档的远景库和 Xaero 导出目录。地图修改完成后，先按改动区块刷新远景和地图，再冻结本次输入。R64 工具沿用了脚本名称 `package_r60.py`。查看本次版本的参数和烘焙子命令可以运行以下命令。

```powershell
python tools/rebake_r63.py --help
python tools/package_r60.py --help
```

以下 PowerShell 示例假定准备好的输入放在 `release-input` 下。将配套的模板 ZIP 放入交付目录；模板版本按本次发布设置。服务器地址以环境变量传入。实际运行前应将日期、地图批次说明和路径换成本次交付值。

```powershell
$delivery = New-Item -ItemType Directory -Force ./delivery
$inputs = @(
    '--client', 'release-input/client',
    '--world', 'release-input/world',
    '--xaero-map', 'release-input/xaero/projectseele$geofront',
    '--geofront-lod', 'release-input/geofront_lod.sqlite',
    '--compare-build', 'build/libs/projectseele-0.1.0-all.jar',
    '--delivery', $delivery.FullName,
    '--template', 'R63r_20261115'
)
python tools/package_r60.py @inputs --check ./delivery/check.json
if ($LASTEXITCODE) { throw '查看 delivery/check.json 中的失败项' }
python tools/package_r60.py @inputs --pack --date (Get-Date -Format yyyyMMdd) --map-note '填写实际完成的地图批次' --server-address $env:SEELE_RELEASE_HOST
```

服务端包携带世界，客户端包携带相应模组和地图缓存。用交付回执核对两个包的文件名和摘要，在独立目录解压，按包内启动脚本使用指定 Forge。由服务器所有者阅读并接受 EULA，然后实际连服检查出生、维度和客户端模组握手。向项目外分发前应按素材许可选取可发布的文件，正式存档、私有资源和开发缓存各有独立的交付范围。参见[公开发布约定](OPEN_SOURCE_RELEASE_R24.md)和[素材登记](ASSETS.md)。
