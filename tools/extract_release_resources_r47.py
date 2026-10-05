"""Extract a user's private protocol55 R47 resources locally; never publish models."""
from __future__ import annotations
import argparse
import json
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
NETWORK_CLASS = 'com/projectseele/network/SeeleNetwork.class'
REQUIRED_CLASSES = (
    'com/projectseele/ProjectSeele.class',
    NETWORK_CLASS,
    'com/projectseele/visual/GeoFrontCommands.class',
    'com/projectseele/world/EquipmentVaultsR47.class',
    'com/projectseele/world/SynchLabDirectorR47.class',
    'com/projectseele/world/ExperimentalLiftStopsR47.class',
    'com/projectseele/network/ServerboundSynchLabExitR47.class',
    'com/projectseele/entity/EvaShieldRigR47.class',
)
REQUIRED_RESOURCES = ('META-INF/mods.toml', 'pack.mcmeta', 'projectseele.mixins.json')
# The annotation processor regenerates projectseele.refmap.json in a rebuild;
# copying the old generated mapping would duplicate/stale that jar entry.
TOP_RESOURCES = set(REQUIRED_RESOURCES)
RESERVED_WINDOWS_NAMES = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}


def entry_path(info: zipfile.ZipInfo) -> PurePosixPath:
    name = info.filename
    if not name or '\\' in name or ':' in name or '\x00' in name or name.startswith('/'):
        raise ValueError(f'Unsafe archive path: {name!r}')
    pieces = name.rstrip('/').split('/')
    if any(not part or part in ('.', '..') or part.endswith((' ', '.'))
           or part.split('.')[0].casefold() in RESERVED_WINDOWS_NAMES for part in pieces):
        raise ValueError(f'Unsafe archive path component: {name!r}')
    kind = stat.S_IFMT(info.external_attr >> 16)
    if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
        raise ValueError(f'Non-regular archive entry is not allowed: {name!r}')
    return PurePosixPath(*pieces)


def network_protocol(data: bytes) -> str:
    """Read only the class ConstantValue; protocol55 is not class-file major55."""
    offset = 0

    def take(size: int) -> bytes:
        nonlocal offset
        value = data[offset:offset + size]
        if len(value) != size:
            raise ValueError('Truncated SeeleNetwork class')
        offset += size
        return value

    def u2() -> int:
        return int.from_bytes(take(2), 'big')

    def u4() -> int:
        return int.from_bytes(take(4), 'big')

    if take(4) != b'\xca\xfe\xba\xbe':
        raise ValueError('Invalid SeeleNetwork class file')
    take(2)
    major = u2()
    if major > 61:
        raise ValueError(f'Class requires newer than release Java17: major={major}')
    count = u2()
    pool: list[tuple[int, object] | None] = [None]
    index = 1
    while index < count:
        tag = take(1)[0]
        if tag == 1:
            value = take(u2()).decode('utf-8', errors='replace')
        elif tag in (7, 8, 16, 19, 20):
            value = u2()
        elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
            value = take(4)
        elif tag == 15:
            value = take(3)
        elif tag in (5, 6):
            value = take(8)
            pool.extend(((tag, value), None))
            index += 2
            continue
        else:
            raise ValueError(f'Unsupported constant-pool tag: {tag}')
        pool.append((tag, value))
        index += 1

    def utf8(at: int) -> str:
        item = pool[at]
        if item is None or item[0] != 1:
            raise ValueError('Invalid protocol field metadata')
        return str(item[1])

    take(6)
    take(2 * u2())
    for _ in range(u2()):
        take(2)
        name, descriptor = utf8(u2()), utf8(u2())
        constant = None
        for _ in range(u2()):
            attribute, size = utf8(u2()), u4()
            payload = take(size)
            if attribute == 'ConstantValue' and size == 2:
                constant = int.from_bytes(payload, 'big')
        if name == 'PROTOCOL_VERSION' and descriptor == 'Ljava/lang/String;' and constant is not None:
            item = pool[constant]
            if item is None or item[0] != 8:
                raise ValueError('Protocol constant is not a String')
            return utf8(int(item[1]))
    raise ValueError('SeeleNetwork.PROTOCOL_VERSION ConstantValue is missing')


def ignored_empty_output(value: Path) -> Path:
    lexical = value if value.is_absolute() else ROOT / value
    output = lexical.resolve()
    if output == ROOT or not output.is_relative_to(ROOT):
        raise ValueError('Output must be a new ignored local directory inside this checkout')
    for parent in (lexical, *lexical.parents):
        if parent == ROOT:
            break
        if parent.is_symlink() or getattr(parent, 'is_junction', lambda: False)():
            raise ValueError(f'Output ancestors must not redirect through a link: {parent}')
    ignored = subprocess.run(['git', 'check-ignore', '--no-index', '--quiet', '--',
                              output.relative_to(ROOT).as_posix()], cwd=ROOT)
    if ignored.returncode != 0:
        raise ValueError('Output is not Git-ignored; use .Codex/... or artifacts/...')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Output already exists and is not an empty directory; nothing will be overwritten')
    return output


def extract(jar: Path, output: Path) -> dict:
    if not jar.is_file():
        raise ValueError(f'Actual private R47 fat jar is missing: {jar}')
    written: list[Path] = []
    created_directories: list[Path] = []
    with zipfile.ZipFile(jar) as archive:
        infos = archive.infolist()
        if len(infos) > 20000:
            raise ValueError('Unexpectedly large archive entry list')
        names: dict[str, zipfile.ZipInfo] = {}
        folded: set[str] = set()
        selected: list[zipfile.ZipInfo] = []
        for info in infos:
            entry_path(info)
            if info.is_dir():
                continue
            if info.filename in names:
                raise ValueError(f'Duplicate archive file: {info.filename}')
            names[info.filename] = info
            if not (info.filename.startswith(('assets/', 'data/')) or info.filename in TOP_RESOURCES):
                continue
            if info.flag_bits & 1:
                raise ValueError(f'Encrypted resource is not allowed: {info.filename}')
            if info.filename.casefold() in folded:
                raise ValueError(f'Case-colliding resource path: {info.filename}')
            folded.add(info.filename.casefold())
            selected.append(info)
        missing = [name for name in (*REQUIRED_CLASSES, *REQUIRED_RESOURCES) if name not in names]
        if missing:
            raise ValueError('Missing required R47 entry classes/resources: ' + ', '.join(missing))
        for name in REQUIRED_CLASSES:
            if archive.read(names[name])[:4] != b'\xca\xfe\xba\xbe':
                raise ValueError(f'Invalid required R47 entry class: {name}')
        protocol = network_protocol(archive.read(names[NETWORK_CLASS]))
        if protocol != '55':
            raise ValueError(f'Expected actual R47 network protocol55; found {protocol!r}')
        if any(info.file_size > 256 * 1024 * 1024 for info in selected) or sum(info.file_size for info in selected) > 2 * 1024 ** 3:
            raise ValueError('Unexpectedly large resource payload')
        # All admission/path checks finish before any snapshot file is created.
        if not output.exists():
            output.mkdir(parents=True)
            created_directories.append(output)
        try:
            for info in selected:
                target = output.joinpath(*entry_path(info).parts)
                if not target.resolve().is_relative_to(output):
                    raise ValueError(f'Resource escapes output: {info.filename}')
                parents = []
                parent = target.parent
                while parent != output and not parent.exists():
                    parents.append(parent)
                    parent = parent.parent
                for parent in reversed(parents):
                    parent.mkdir()
                    created_directories.append(parent)
                # Exclusive creation and unmodified bytes; no text/EOL conversion.
                payload = archive.read(info)
                with target.open('xb') as stream:
                    written.append(target)
                    stream.write(payload)
        except Exception:
            # Undo only files/directories created by this attempt; never recursive
            # deletion, user files, source resources, or an existing snapshot.
            for path in reversed(written):
                path.unlink(missing_ok=True)
            for path in reversed(created_directories):
                try:
                    path.rmdir()
                except OSError:
                    pass
            raise
    return {'schema': 'projectseele.r47.private-resource-extraction.v1',
            'source_jar': str(jar), 'output': str(output), 'network_protocol': protocol,
            'required_R47_entry_classes': list(REQUIRED_CLASSES),
            'resource_files': len(selected), 'unmodified_resource_bytes': sum(info.file_size for info in selected),
            'classes_dependencies_worlds_runtime_config_not_extracted': True,
            'generated_refmap_not_extracted': True,
            'source_main_resources_untouched': True, 'JVM_started': False, 'network_used': False,
            'SHA_computed': False, 'private_assets_must_remain_uncommitted': True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jar', required=True, type=Path, help="User's actual protocol55 R47 projectseele fat jar")
    parser.add_argument('--out', required=True, type=Path, help='NEW empty Git-ignored local snapshot, e.g. .Codex/r47-private-resources')
    args = parser.parse_args()
    try:
        output = ignored_empty_output(args.out)
        report = extract(args.jar.resolve(), output)
    except (ValueError, OSError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        parser.exit(2, f'R47 resource extraction refused: {error}\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
