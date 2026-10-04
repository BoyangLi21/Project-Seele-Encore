#!/usr/bin/env python3
"""Build private Project SEELE server, world-import, and client archives."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORLD_NAME = "SEELE_TV_WORLD_PREVIEW_20260906"
MC_VERSION = "1.20.1"
FORGE_VERSION = "47.4.10"


def validate_private_eva_mesh_contracts() -> None:
    """Reject a package whose embedded EVA meshes would be hidden at runtime."""
    asset_root = (
        ROOT / "run" / "resourcepacks" / "eva_real_model"
        / "assets" / "projectseele"
    )
    source = (
        ROOT / "src" / "main" / "java" / "com" / "projectseele"
        / "client" / "render" / "LocalVisualAssetFingerprint.java"
    ).read_text(encoding="utf-8")
    contracts = {
        name: (int(triangles.replace("_", "")), int(parts))
        for name, triangles, parts in re.findall(
            r'"([a-z0-9_]+)"\s*,\s*new MeshContract\('
            r'([\d_]+),\s*(\d+)(?:,\s*(?:true|false))?\)',
            source,
        )
    }
    r30_file=asset_root/'eva/un_models_r30.json'
    r30=json.loads(r30_file.read_text(encoding='utf8'))['models'] if r30_file.exists() else {}
    jaw_file=asset_root/'eva/unit01_tv_jaw_r37.json'
    jaw=json.loads(jaw_file.read_text(encoding='utf8')) if jaw_file.exists() else None
    for name in ("eva_unit00", "eva_unit01", "eva_unit02", "eva_prototype", "eva_un01"):
        expected = (r30[name]['triangles'],r30[name]['parts']) if name in r30 else contracts.get(name)
        if name=='eva_unit01' and jaw:
            if jaw.get('schema')!='projectseele.tv-jaw-r37.v1' or jaw.get('parts')!=49:raise ValueError('Invalid R37 jaw contract')
            expected=(jaw['triangles'],jaw['parts'])
            for key,relative in {'mesh':f'mesh/{name}.mesh.json','geo':f'geo/{name}.geo.json','animation':f'animations/{name}.animation.json','texture':f'textures/entity/{name}.png'}.items():
                if sha256(asset_root/relative)!=jaw['sha256'][key]:raise ValueError('R37 jaw identity mismatch: '+key)
        if expected is None:
            raise ValueError(f"Missing Java mesh contract for {name}")
        path = asset_root / "mesh" / f"{name}.mesh.json"
        if not path.is_file():
            raise FileNotFoundError(f"Missing private EVA mesh: {path}")
        mesh = json.loads(path.read_text(encoding="utf-8"))
        stride = int(mesh.get("stride", 8))
        values = sum(
            len(part.get("vertices", ()))
            for part in mesh.get("parts", {}).values()
        )
        if stride <= 0 or values % (stride * 3) != 0:
            raise ValueError(f"Malformed mesh vertex stream: {path}")
        actual = (values // (stride * 3), len(mesh.get("parts", {})))
        if actual != expected:
            raise ValueError(
                f"{name} would be invisible: Java contract={expected}, "
                f"private mesh={actual}"
            )
        if name in r30:
            core={'mesh':f'mesh/{name}.mesh.json','geo':f'geo/{name}.geo.json','animation':f'animations/{name}.animation.json','texture':f'textures/entity/{name}.png'}
            for key,relative in core.items():
                if sha256(asset_root/relative)!=r30[name]['sha256'][key]:raise ValueError(f'R30 model manifest mismatch: {name}/{key}')
            for relative,digest in r30[name]['pbr'].items():
                if sha256(asset_root/relative)!=digest:raise ValueError(f'R30 material manifest mismatch: {relative}')


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def newest_project_jar() -> Path:
    jars = [
        path
        for path in (ROOT / "build" / "libs").glob("projectseele-*.jar")
        if not path.name.endswith(("-sources.jar", "-javadoc.jar"))
    ]
    if not jars:
        raise FileNotFoundError("Missing Project SEELE build JAR; run gradlew.bat build first")
    bundled=[path for path in jars if path.name.endswith('-all.jar')]
    if bundled:
        candidate=max(bundled,key=lambda path:path.stat().st_mtime_ns)
        with zipfile.ZipFile(candidate) as jar:
            if 'META-INF/jarjar/metadata.json' not in jar.namelist():raise ValueError('Bundled physics dependencies are missing')
        return candidate
    if 'minecraftLibrary(\'com.github.stephengold:jbullet' in (ROOT/'build.gradle').read_text(encoding='utf8'):
        raise FileNotFoundError('Build the bundled Project SEELE JAR; plain JAR has no physics runtime')
    return max(jars, key=lambda path: path.stat().st_mtime_ns)


def find_geckolib() -> Path:
    root = (
        Path.home()
        / ".gradle"
        / "caches"
        / "modules-2"
        / "files-2.1"
        / "software.bernie.geckolib"
        / "geckolib-forge-1.20.1"
        / "4.8.4"
    )
    jars = [
        path
        for path in root.rglob("*.jar")
        if not path.name.endswith(("-sources.jar", "-javadoc.jar"))
    ]
    if not jars:
        raise FileNotFoundError("Missing GeckoLib 4.8.4 in Gradle cache")
    return max(jars, key=lambda path: path.stat().st_mtime_ns)


def required_mods() -> list[Path]:
    local = ROOT / ".Codex" / "local-mods"
    mods = [
        newest_project_jar(),
        find_geckolib(),
        local / "ars-nouveau-4.12.7.jar",
        local / "curios-forge-1.20.1-5.14.1.jar",
        local / "another-furniture-1.20.1-3.0.4.jar",
        local / "movingelevators-1.4.12-forge-mc1.20.1.jar",
        local / "supermartijn642configlib-1.1.8-forge-mc1.20.jar",
        local / "supermartijn642corelib-1.1.24-forge-mc1.20.1.jar",
        local / "MTR-forge-4.0.5+1.20.1.jar",
        local / "superbwarfare-0.8.9.1-hotfix-mc1.20.1-993063bed-all.jar",
        local / "kotlinforforge-4.12.0-all.jar",
        local / "Patchouli-1.20.1-85-FORGE.jar",
        local / "grandpianomod-1.0.0.jar",
        local / "ferritecore-6.0.1-forge.jar",
        local / "modernfix-forge-5.27.83+mc1.20.1.jar",
    ]
    missing = [path for path in mods if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required mod(s): " + ", ".join(map(str, missing)))
    return mods


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(
    source: Path,
    destination: Path,
    *,
    ignore_world_locks: bool = False,
    extra_ignore_patterns: tuple[str, ...] = (),
) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"Missing directory: {source}")
    patterns = list(extra_ignore_patterns)
    if ignore_world_locks:
        patterns.extend(("session.lock", "*.lock"))
    ignored = shutil.ignore_patterns(*patterns) if patterns else None
    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignored)


def copy_local_maps_without_commander_skin(destination: Path) -> None:
    """Copy private map plates while excluding the user's personal skin."""
    source = ROOT / "run" / "projectseele-local-maps"
    if not source.is_dir():
        raise FileNotFoundError(f"Missing directory: {source}")
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("gendo_player.png"),
    )
    leaked = list(destination.rglob("gendo_player.png"))
    if leaked:
        raise ValueError(f"Commander skin leaked into package: {leaked}")


def copy_runtime_mods(destination: Path) -> None:
    """Build one private SEELE runtime JAR for both client and server.

    The private model assets are harmless on a dedicated server, while using
    the exact same JAR on both sides prevents stale client/server batches from
    being mixed.  The separate resource pack remains in the client archive for
    live F3+T iteration.
    """
    project_jar = newest_project_jar()
    private_assets = ROOT / "run" / "resourcepacks" / "eva_real_model" / "assets"
    if not private_assets.is_dir():
        raise FileNotFoundError(f"Missing private model assets: {private_assets}")
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / project_jar.name
    replaced = {
        f"assets/{path.relative_to(private_assets).as_posix()}"
        for path in private_assets.rglob("*") if path.is_file()
    }
    with zipfile.ZipFile(project_jar, "r") as source, zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as target:
        for info in source.infolist():
            if info.filename not in replaced:
                target.writestr(info, source.read(info.filename))
        for path in sorted(private_assets.rglob("*")):
            if path.is_file():
                target.write(path,
                             f"assets/{path.relative_to(private_assets).as_posix()}")
    for source in required_mods():
        if source.resolve() != project_jar.resolve():
            copy_file(source, destination / source.name)


def copy_configs(destination: Path, *, client: bool) -> None:
    source_root = ROOT / "run" / "config"
    common_names = (
        "projectseele-common.toml",
        "ars_nouveau-common.toml",
        "ars_nouveau-server.toml",
        "curios-common.toml",
        "movingelevators-common.toml",
        "superbwarfare-common.toml",
        "mtr.json",
    )
    client_names = (
        "projectseele-client.toml",
        "ars_nouveau-client.toml",
        "curios-client.toml",
    )
    for name in common_names + (client_names if client else ()):
        source = source_root / name
        if source.is_file():
            copy_file(source, destination / name)
    if client:
        for name in ('embeddium-options.json','xaerominimap.txt','xaeroworldmap.txt','xaerohud.txt'):
            source=source_root/name
            if source.is_file():copy_file(source,destination/name)
        # Only portable project defaults: do not distribute the operator's
        # account preferences, private addresses or other resource packs.
        settings={'renderDistance':'24','simulationDistance':'8','mipmapLevels':'4',
            'graphicsMode':'1','particles':'0','entityDistanceScaling':'1.0',
            'resourcePacks':'["vanilla","mod_resources","file/eva_real_model"]',
            'key_gui.xaero_new_waypoint':'key.keyboard.n',
            'key_gui.xaero_enlarge_map':'key.keyboard.backslash',
            'key_gui.xaero_zoom_in':'key.keyboard.right.bracket',
            'key_gui.xaero_zoom_out':'key.keyboard.left.bracket',
            'key_gui.xaero_toggle_manual_cave_mode':'key.keyboard.f8',
            'key_gui.xaero_open_settings':'key.keyboard.unknown'}
        (destination.parent/'options.txt').write_text(''.join(f'{k}:{v}\n' for k,v in settings.items()),encoding='utf8')


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8-sig")


def write_manifest(root: Path, archive_kind: str) -> None:
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    payload = {
        "schema": 1,
        "privateDevelopmentOnly": True,
        "kind": archive_kind,
        "minecraft": MC_VERSION,
        "forge": FORGE_VERSION,
        "java": 17,
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "excludedPrivateAssets": [
            "projectseele-local-maps/gendo_player.png",
        ],
        "files": entries,
    }
    (root / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def zip_tree(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())
    with zipfile.ZipFile(destination) as archive:
        bad = archive.testzip()
        if bad:
            raise OSError(f"ZIP verification failed at {bad}: {destination}")


def server_properties() -> str:
    return f"""# Project SEELE private two-developer server
server-port=25565
motd=Project SEELE Private Development Server
level-name={WORLD_NAME}
gamemode=creative
force-gamemode=false
difficulty=normal
hardcore=false
max-players=4
white-list=true
enforce-whitelist=true
online-mode=true
spawn-protection=0
allow-flight=true
view-distance=24
simulation-distance=8
entity-broadcast-range-percentage=125
network-compression-threshold=256
max-tick-time=120000
sync-chunk-writes=false
enable-command-block=false
"""


def jvm_args() -> str:
    return """-Xms2G
-Xmx20G
-XX:+UseG1GC
-XX:+ParallelRefProcEnabled
-XX:MaxGCPauseMillis=200
-XX:G1HeapRegionSize=16M
-XX:G1ReservePercent=20
-XX:InitiatingHeapOccupancyPercent=15
-Dfile.encoding=UTF-8
"""


def build_server(root: Path, guide: str, revision: str = 'R28') -> None:
    copy_runtime_mods(root / "mods")
    copy_configs(root / "config", client=False)
    copy_local_maps_without_commander_skin(root / "projectseele-local-maps")
    write_text(root / "server.properties", server_properties())
    write_text(root / "user_jvm_args.txt", jvm_args())
    write_text(root / "README_SERVER_CN.txt", guide)
    guide_file=ROOT / "docs" / f"MANUAL_ACCEPTANCE_{revision}.md"
    if guide_file.exists():copy_file(guide_file,root / f"{revision}_TEST_GUIDE_CN.md")
    elif (ROOT / "docs" / "MANUAL_ACCEPTANCE_R25.md").exists():copy_file(ROOT / "docs" / "MANUAL_ACCEPTANCE_R25.md",root / "R25_TEST_GUIDE_CN.md")
    else:copy_file(ROOT / "docs" / "MANUAL_ACCEPTANCE_R24.md", root / "R24_TEST_GUIDE_CN.md")
    write_text(
        root / "PRIVATE_USE_ONLY.txt",
        "本包仅供两名受邀开发者在私人服务器测试。禁止公开上传或再分发其中的第三方资源。",
    )
    write_manifest(root, "server-files")


def build_client(root: Path, guide: str, revision: str = 'R28', city_shaders: bool = False) -> None:
    copy_runtime_mods(root / "mods")
    copy_configs(root / "config", client=True)
    copy_local_maps_without_commander_skin(root / "projectseele-local-maps")
    local = ROOT / ".Codex" / "local-mods"
    client_only = [local / "embeddium-0.3.31+mc1.20.1.jar"]
    if city_shaders:client_only.append(local/'oculus-mc1.20.1-1.8.0.jar')
    client_only.extend(local / row['filename'] for row in json.loads((ROOT/'tools/client_navigation_r19.json').read_text()))
    missing = [path for path in client_only if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing client-only render mod(s): " + ", ".join(map(str, missing))
        )
    for source in client_only:
        copy_file(source, root / "mods" / source.name)
    copy_tree(
        ROOT / "run" / "resourcepacks" / "eva_real_model",
        root / "resourcepacks" / "eva_real_model",
    )
    write_text(root / "README_CLIENT_CN.txt", guide)
    guide_file=ROOT / "docs" / f"MANUAL_ACCEPTANCE_{revision}.md"
    if guide_file.exists():copy_file(guide_file,root / f"{revision}_TEST_GUIDE_CN.md")
    elif (ROOT / "docs" / "MANUAL_ACCEPTANCE_R25.md").exists():copy_file(ROOT / "docs" / "MANUAL_ACCEPTANCE_R25.md",root / "R25_TEST_GUIDE_CN.md")
    else:copy_file(ROOT / "docs" / "MANUAL_ACCEPTANCE_R24.md", root / "R24_TEST_GUIDE_CN.md")
    write_text(
        root / "PRIVATE_USE_ONLY.txt",
        "本包包含本地测试模型与贴图，只能私下发给受邀开发者，禁止公开上传或再分发。",
    )
    write_manifest(root, "client-pack")


def build_world(root: Path) -> None:
    copy_tree(
        ROOT / "run" / "saves" / WORLD_NAME,
        root,
        ignore_world_locks=True,
        extra_ignore_patterns=(
            "DistantHorizons.sqlite",
            "DistantHorizons.sqlite-shm",
            "DistantHorizons.sqlite-wal",
            "lod_cache_r17.json",
        ),
    )
    if not (root / "level.dat").is_file():
        raise FileNotFoundError("World import root does not contain level.dat")
    # R19 retires the LOD cache after observed underground transparency errors.


def validate_outputs(server_zip: Path, world_zip: Path, client_zip: Path, city_shaders: bool = False) -> None:
    def project_jar_bytes(archive: zipfile.ZipFile) -> bytes:
        candidates = [
            name for name in archive.namelist()
            if name.startswith("mods/projectseele-") and name.endswith(".jar")
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"Expected exactly one Project SEELE JAR, found {candidates}"
            )
        return archive.read(candidates[0])

    with zipfile.ZipFile(server_zip) as archive:
        names = set(archive.namelist())
        if any(name.lower().endswith("gendo_player.png") for name in names):
            raise ValueError("Server archive contains excluded commander skin")
        required = {
            "server.properties",
            "user_jvm_args.txt",
            "projectseele-local-maps/manifest.json",
        }
        if not required.issubset(names):
            raise ValueError("Server archive is missing required root files")
        mod_names = [name for name in names if name.startswith("mods/") and name.endswith(".jar")]
        if len(mod_names) != len(required_mods()):
            raise ValueError(f"Server mod count mismatch: {len(mod_names)}")
        server_project_jar = project_jar_bytes(archive)

    with zipfile.ZipFile(world_zip) as archive:
        names = set(archive.namelist())
        if "level.dat" not in names or "session.lock" in names:
            raise ValueError("World import archive root/lock policy is invalid")
        if not any(name.startswith("dimensions/projectseele/geofront/") for name in names):
            raise ValueError("World import archive is missing the GeoFront dimension")
        if "nerv_staff_r15.json" not in names:
            raise ValueError("World import archive is missing the staff roster")
        caches={name for name in names if "distanthorizons" in name.lower()}
        certified=json.loads(archive.read("lod_cache_r17.json")) if "lod_cache_r17.json" in names else {}
        expected={row["path"] for row in certified.get("databases",[])}
        if caches!=expected:
            raise ValueError("World archive contains an uncertified or incomplete LOD cache")
        for row in certified.get("databases",[]):
            if hashlib.sha256(archive.read(row["path"])).hexdigest()!=row["sha256"]:
                raise ValueError("Packaged LOD cache checksum mismatch")

    with zipfile.ZipFile(client_zip) as archive:
        names = set(archive.namelist())
        if any(name.lower().endswith("gendo_player.png") for name in names):
            raise ValueError("Client archive contains excluded commander skin")
        animation_path = (
            "resourcepacks/eva_real_model/assets/projectseele/animations/"
            "eva_unit01.animation.json"
        )
        if "resourcepacks/eva_real_model/pack.mcmeta" not in names:
            raise ValueError("Client archive is missing eva_real_model")
        if animation_path not in names:
            raise ValueError("Client archive is missing the R04 Unit-01 animation")
        mod_names = [name for name in names if name.startswith("mods/") and name.endswith(".jar")]
        navigation_count=len(json.loads((ROOT/'tools/client_navigation_r19.json').read_text()))
        if len(mod_names) != len(required_mods()) + 1 + navigation_count + int(city_shaders):
            raise ValueError(f"Client mod count mismatch: {len(mod_names)}")
        if city_shaders and 'mods/oculus-mc1.20.1-1.8.0.jar' not in names:
            raise ValueError('Missing approved R29 shader loader')
        if any('distanthorizons' in name.lower() or 'acedium' in name.lower() or 'farsight' in name.lower() for name in names):
            raise ValueError('An unapproved terrain renderer entered the default client pack')
        client_project_jar = project_jar_bytes(archive)
        loose_animation = archive.read(animation_path)
    if hashlib.sha256(server_project_jar).digest() != hashlib.sha256(
            client_project_jar).digest():
        raise ValueError("Client and server Project SEELE JAR hashes differ")
    with zipfile.ZipFile(io.BytesIO(client_project_jar)) as project_archive:
        if any(name.lower().endswith("gendo_player.png")
               for name in project_archive.namelist()):
            raise ValueError("Runtime JAR contains excluded commander skin")
        embedded_path = (
            "assets/projectseele/animations/eva_unit01.animation.json"
        )
        if embedded_path not in project_archive.namelist():
            raise ValueError("Private runtime JAR is missing Unit-01 animation")
        if hashlib.sha256(project_archive.read(embedded_path)).digest() != (
                hashlib.sha256(loose_animation).digest()):
            raise ValueError(
                "Embedded and live-reload Unit-01 animations differ"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "server-ready")
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    validate_private_eva_mesh_contracts()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    guide_path = ROOT / "docs" / "PRIVATE_SERVER_DEPLOYMENT_CN.md"
    guide = guide_path.read_text(encoding="utf-8")

    server_zip = output / f"Project_SEELE_Server_Files_{stamp}.zip"
    world_zip = output / f"Project_SEELE_World_Import_{stamp}.zip"
    client_zip = output / f"Project_SEELE_Client_Pack_{stamp}.zip"

    with tempfile.TemporaryDirectory(prefix="project_seele_pack_", dir=output) as temp:
        stage = Path(temp)
        server_root = stage / "server"
        world_root = stage / "world"
        client_root = stage / "client"
        build_server(server_root, guide)
        build_world(world_root)
        build_client(client_root, guide)
        zip_tree(server_root, server_zip)
        zip_tree(world_root, world_zip)
        zip_tree(client_root, client_zip)

    validate_outputs(server_zip, world_zip, client_zip)
    sums = []
    hashes = {}
    for path in (server_zip, world_zip, client_zip):
        digest = sha256(path)
        hashes[path.name] = digest
        sums.append(f"{digest}  {path.name}")
        print(f"[PASS] {path.name}: {path.stat().st_size} bytes")
    write_text(output / f"SHA256SUMS_{stamp}.txt", "\n".join(sums))
    write_text(
        output / "LATEST_PRIVATE_PACK.txt",
        "\n".join(
            [
                f"Project SEELE private test batch: {stamp}",
                "",
                "USE ONLY:",
                server_zip.name,
                world_zip.name,
                client_zip.name,
                "",
                "SHA-256:",
                *[f"{hashes[path.name]}  {path.name}"
                  for path in (server_zip, world_zip, client_zip)],
                "",
                "All earlier batches are superseded.",
            ]
        ),
    )
    copy_file(guide_path, output / "DEPLOYMENT_GUIDE_CN.md")
    print(f"[PASS] output={output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        raise SystemExit(1)
