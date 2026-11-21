"""Package the current game as one release: a server zip with the world and a PCL client zip without it.

Inventory only by default; --pack writes both zips; --check runs every gate, reports all failures at once
and writes nothing but its report. The previous release's packages (--template, kept in the delivery folder)
supply the server bootstrap (libraries, start scripts), server.properties, the icon and the PCL manifest.
--pack holds the world's session.lock while it reads, so nothing may have the world open.
--geofront-lod takes the GeoFront LOD database from tools/rebake_r63.py instead of the formal world's,
so a re-baked far view never has to be written into the formal world.
"""
from contextlib import contextmanager, nullcontext
from pathlib import Path
import argparse
import datetime
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import struct
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'R65'
NAME = 'EVANGELION_Encore_' + VERSION
SHADER = 'SEELE_Local_Cavern_R53_Review_20261026.zip'
SERVER_WORLD = 'SEELE_R53_WORLD'
JIT = 'jit-recovery-r54.json'
JVM = '-XX:+UnlockDiagnosticVMOptions -XX:CompilerDirectivesFile=' + JIT
MOTD = '§b§lEVANGELION:Encore ' + VERSION + ' §r\n§6NERV！ §8| §aEVA！§8| §fSEELE!'
DH_MOD = 'mods/DistantHorizons-2.3.4-b-1.20.1-fabric-forge.jar'
TRAFFICCRAFT = 'mods/trafficcraft-forge-1.20.1-1.1.3.jar'
MTR = 'mods/MTR-forge-4.0.5+1.20.1.jar'
MAIN_JAR = 'mods/projectseele-0.1.0-all.jar'
# Must be in the shipped jar. R63: outer boundary generator, perf batches 1-2, Fable phases 3-5, MTR ride sync.
# R64: mission audio and its headset, the sea-level horizon, off-thread entity textures, shared JSON leaves.
RELEASE_CLASSES = ('world/OuterBoundaryTerrain', 'world/SbwIdlePause', 'physics/GiantInsideBlocks', 'physics/TerrainPruningBroadphase',
                   'client/render/EntityShadowRange', 'client/render/EvaRackReleaseR63', 'client/render/EvaKneeHingeR63',
                   'client/render/EvaArmClearanceR63', 'mixin/client/MtrRideSyncR63Mixin',
                   'world/MissionAudioR64', 'client/sound/HeadsetSoundsR64', 'mixin/client/TvGeoFrontHorizonR64Mixin',
                   'client/render/HeavyTextureLoad', 'util/SharedJsonLeaves')
GRASS_PACK = 'SEELE_GreenGrassSide.zip'  # R64: enabled for every client (owner-approved), built by tools/gen_green_grass_side.py
SBW_SERVER = 'serverconfig/superbwarfare-server.toml'
GEOFRONT_LOD = 'dimensions/projectseele/geofront/data/DistantHorizons.sqlite'
CHECK = None  # a list while --check runs: failed gates are collected there instead of raised


def gate(ok, message):
    if ok:
        return True
    if CHECK is None:
        raise AssertionError(message)
    CHECK.append(message if isinstance(message, str) else json.dumps(message, ensure_ascii=False, default=str))
    return False
CLIENT_TREES = ('mods', 'projectseele-local-maps', 'config', 'defaultconfigs', 'resourcepacks', 'shaderpacks', 'licenses')
PRUNE = {'.codex', 'logs', 'crash-reports', 'debug', 'screenshots', 'pose-captures', 'backups', 'backup', 'tests', 'test',
         '__pycache__', '.git', 'distanthorizons', 'distant_horizons_server_data'}
SUFFIXES = ('.bak', '.old', '.backup', '.log', '.tmp', '.pyc')
STORED = ('.jar', '.zip', '.png', '.ogg', '.gz', '.jpg', '.mca')
TRAFFICCRAFT_NOTICE = """TrafficCraft 1.20.1-1.1.3 by MrJulsen, GPL-3.0-or-later, distributed unmodified.
Source: https://github.com/MisterJulsen/TrafficCraft
The jar embeds DragonLib 1.20.1-2.2.24 and Architectury 9.1.12 as published by its author.
Project SEELE only places this mod's blocks in its map and does not link against it.
"""
DRY_ORIGINAL = 'uniform float inDry;'
DRY_REPLACEMENT = '''#ifdef SEELE_GEOFRONT
// The custom GeoFront biome has no precipitation; it is not a desert.
const float inDry = 0.0;
#else
uniform float inDry;
#endif'''
# The shader always discards LODs near the player, on the promise that vanilla terrain
# is there. The mod raises this uniform while the sections in view are still unmeshed.
DH_FADE_ORIGINAL = 'color.a *= mix(smoothstep(far * 0.5, far * 0.7, lengthCylinder), 1.0, SeeleCavernWeight());'
DH_FADE_REPLACEMENT = 'color.a *= mix(smoothstep(far * 0.5, far * 0.7, lengthCylinder), 1.0, max(SeeleCavernWeight(), seeleDhNearFill));'
SERVER_LOD_AGE_MS = 86_400_000
SHADER_PATCHES = (
    ('shaders/lib/uniforms.glsl', DRY_ORIGINAL, DRY_REPLACEMENT),
    ('shaders/lib/seele/cavern.glsl', '#define SEELE_CAVERN_HELPER', '#define SEELE_CAVERN_HELPER\nuniform float seeleDhNearFill;'),
    ('shaders/program/dh_terrain.glsl', DH_FADE_ORIGINAL, DH_FADE_REPLACEMENT),
    ('shaders/program/dh_water.glsl', DH_FADE_ORIGINAL, DH_FADE_REPLACEMENT),
)


@contextmanager
def stopped_world(world):
    with (world / 'session.lock').open('r+b') as handle:
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def excluded(name):
    low = name.lower()
    return low in PRUNE or low.startswith(('hs_err_pid', 'replay_pid')) or low.endswith(SUFFIXES)


def files(root):
    for parent, dirs, names in os.walk(root, followlinks=False):
        parent = Path(parent)
        for name in dirs:
            if (parent / name).is_symlink():
                raise ValueError('Unexpected linked input: ' + str(parent / name))
        dirs[:] = sorted(n for n in dirs if not excluded(n))
        for name in sorted(names):
            path = parent / name
            if path.is_symlink():
                raise ValueError('Unexpected linked input: ' + str(path))
            if name == 'session.lock' or excluded(name) or name.startswith(('DistantHorizons.sqlite', 'Distant_Horizons.sqlite')):
                continue
            yield path


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8')


def property_value(value):
    return ''.join(r'\n' if c == '\n' else r'\\' if c == '\\' else r'\:' if c == ':'
                   else '\\u%04X' % ord(c) if ord(c) > 126 or ord(c) < 32 else c for c in value)


def level_name(world):
    data = gzip.decompress((world / 'level.dat').read_bytes())
    key = b'\x08\x00\x09LevelName'
    at = data.index(key) + len(key)
    size = struct.unpack('>H', data[at:at + 2])[0]
    return data[at + 2:at + 2 + size].decode('utf8')


def dh_identifier(client, world, logged_world_folder=None):
    display = level_name(world)
    patterns = [re.compile(r'DhClientServerLevel\{' + re.escape(n) + r'_([0-9a-v]{13})@') for n in {world.name, display, logged_world_folder} if n]
    logs = [client / 'logs/latest.log'] + sorted((client / 'logs').glob('*.log.gz'), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in logs:
        if not path.exists():
            continue
        text = gzip.open(path, 'rt', encoding='utf8', errors='replace').read() if path.suffix == '.gz' else path.read_text('utf8', errors='replace')
        found = {m for pattern in patterns for m in pattern.findall(text)}
        if len(found) > 1:
            raise ValueError('Ambiguous DH key in ' + str(path))
        if found:
            return found.pop(), dict(log=str(path), world_folder=world.name, level_display_name=display, logged_world_folder=logged_world_folder)
    raise ValueError('No logged DH identifier for this world')


def dimensions(world):
    yield world
    for name in ('DIM-1', 'DIM1'):
        if (world / name).is_dir():
            yield world / name
    custom = world / 'dimensions'
    if custom.exists():
        for namespace in sorted(custom.iterdir()):
            if namespace.is_dir():
                yield from (p for p in sorted(namespace.iterdir()) if p.is_dir())


def aged_lod_copy(db, target):
    """A copy of a LOD database with every row a day older than the client's copy of the same file.

    A DH client asks for each section it shows and the server resends it when its row is newer,
    after shifting the client's timestamp by the measured clock offset. With identical files any
    offset below zero makes every row newer, so the client downloads and rebuilds a map it already
    has. Later changes on the server carry their own, newer times and still reach the clients.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(db, target)
    connection = sqlite3.connect(target)
    try:
        connection.execute('UPDATE FullData SET LastModifiedUnixDateTime = LastModifiedUnixDateTime - ?', (SERVER_LOD_AGE_MS,))
        connection.commit()
        connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    finally:
        connection.close()
    for suffix in ('-wal', '-shm'):
        Path(str(target) + suffix).unlink(missing_ok=True)
    return target


def lod_summary(db):
    # immutable: even mode=ro leaves -wal and -shm files beside a WAL database, and these sit in the formal world.
    # The caller has already refused a database with a non-empty WAL, so nothing is skipped.
    c = sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        levels = c.execute('select DetailLevel, count(*) from FullData group by DetailLevel').fetchall()
        pending = c.execute('select count(*) from FullData where ApplyToParent = 1').fetchone()[0]
        check = c.execute('pragma quick_check').fetchone()[0]
    finally:
        c.close()
    return dict(rows=sum(n for _, n in levels), levels=levels, pending_parent_updates=pending, quick_check=check)


def distant_caches(world, seed, pack, work, geofront_lod=None):
    client, server, details = {}, {}, []
    for dim in dimensions(world):
        db = dim / 'data/DistantHorizons.sqlite'
        if not db.exists():
            continue
        entry = db.relative_to(world).as_posix()
        source = 'formal world'
        if entry == GEOFRONT_LOD and geofront_lod:
            db, source = geofront_lod, 'tools/rebake_r63.py'
        rel = dim.relative_to(world).as_posix()
        name = {'.': 'minecraft:overworld', 'DIM-1': 'minecraft:the_nether', 'DIM1': 'minecraft:the_end'}.get(rel) or ':'.join(Path(rel).parts[1:])
        wal = Path(str(db) + '-wal')
        gate(not (wal.exists() and wal.stat().st_size), 'DH database has an unmerged WAL: ' + str(db))
        summary = lod_summary(db)
        gate(summary['quick_check'] == 'ok', 'DH database failed quick_check: ' + str(db))
        client['Distant_Horizons_server_data/SEELE/' + (seed + '@' + name).replace(':', '@@') + '/DistantHorizons.sqlite'] = db
        server[entry] = aged_lod_copy(db, work / entry) if pack else db
        details.append(dict(dimension=name, bytes=db.stat().st_size, source=source, **summary))
    gate({'data/DistantHorizons.sqlite', GEOFRONT_LOD} <= set(server), 'Overworld or GeoFront LOD database missing')
    return client, server, details


def shader_payload(path):
    with zipfile.ZipFile(path) as source:
        patched = {}
        for member, original, replacement in SHADER_PATCHES:
            text = patched.get(member, source.read(member).decode('utf8'))
            if replacement not in text:
                assert text.count(original) == 1
                patched[member] = text.replace(original, replacement)
        # R64 V2: entities beyond the real chunks no longer show through the far view. Same file name, so
        # oculus.properties and the pack's .zip.txt need no change.
        depth = tool_module('shader_dh_entity_depth_v2')
        for member, margin in depth.TARGETS.items():
            text = patched.get(member, source.read(member).decode('utf8'))
            if depth.patch_text(text, margin) != text:
                patched[member] = depth.patch_text(text, margin)
        # R64: the ground hatch cover of the remote air shaft is lit as the grass it shows.
        cover = tool_module('shader_ground_hatch_material')
        text = patched.get(cover.MEMBER, source.read(cover.MEMBER).decode('utf8'))
        if cover.patch_text(text) != text:
            patched[cover.MEMBER] = cover.patch_text(text)
        if not patched:
            return path
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as target:
            for entry in source.infolist():
                data = patched[entry.filename].encode('utf8') if entry.filename in patched else source.read(entry)
                target.writestr(entry, data)
            target.comment = source.comment
    return output.getvalue()


def dh_config(text, settings):
    for key, value in settings.items():
        text = re.sub(r'(?m)^(\s*' + re.escape(key) + r'\s*=\s*)[^\r\n]*', lambda m: m[1] + value, text)
    return text.encode('utf8')


# R64 (perf): LZMA2 keeps 32 compressors of 34 MB resident (1.1 GB); with LZ4 a 7.2 GB client heap had no full GC.
# The database grows up to about 1.3x; rows already stored keep their own compression mode and stay readable.
DH_COMPRESSION = {'dataCompression': '"LZ4"'}


def server_dh_config(text):
    # Remote city motion must update LODs outside vanilla chunk tracking, without generating distant terrain.
    return dh_config(text, {'numberOfThreads': '2', 'threadRunTimeRatio': '"0.5"', 'enableDistantGeneration': 'false',
                            'distantGeneratorMode': '"PRE_EXISTING_ONLY"', 'enableRealTimeUpdates': 'true',
                            'realTimeUpdateDistanceRadiusInChunks': '256', 'synchronizeOnLoad': 'true',
                            'sendLevelKeys': 'true', 'levelKeyPrefix': '""', **DH_COMPRESSION})


def client_dh_config(text):
    # Two threads at half duty leave the preinstalled terrain filling in for a minute after joining.
    return dh_config(text, {'numberOfThreads': '4', 'threadRunTimeRatio': '"1.0"', **DH_COMPRESSION})


def sbw_server_config(text):
    """R64 (perf): with vehicle chunk loading on, SuperbWarfare gives every vehicle loaded at shutdown a permanent
    radius-3 ticket at the next start (93 tickets, 969 chunks, 92 MB, nearly all at the UN base), and the set only
    grows. Nothing of ours relies on it: our sites keep their own tickets and parked vehicles already drop theirs."""
    gate(re.search(r'(?m)^\s*vehicle_chunk_loading\s*=', text), SBW_SERVER + ' has no vehicle_chunk_loading key')
    return re.sub(r'(?m)^(\s*vehicle_chunk_loading\s*=\s*)true\b', r'\1false', text).encode('utf8')


def tool_module(name):
    """One of the repository's tools, so a pack-time change has a single source that also runs on its own."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def grass_pack():
    """The green grass-side pack, built here from its generator so the release never carries a stale copy."""
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / GRASS_PACK
        tool_module('gen_green_grass_side').build(target)
        return target.read_bytes()


def servers_dat(name, address):
    """One multiplayer entry. The name has to stay SEELE: DH finds the preinstalled LODs by it."""
    def text(key, value):
        k, v = key.encode('utf8'), value.encode('utf8')
        return b'\x08' + struct.pack('>H', len(k)) + k + struct.pack('>H', len(v)) + v
    entry = text('name', name) + text('ip', address) + b'\x00'
    return b'\x0a\x00\x00\x09\x00\x07servers\x0a' + struct.pack('>i', 1) + entry + b'\x00'


def xaero_map(source, world, address):
    """The baked world map, moved to where Xaero looks for it on this server.

    A multiplayer client only lists regions that have an N_M.zip in the map folder, so tile
    caches without those files never show. Both come from a run with -Dprojectseele.xaeroBake=true.
    """
    converted = source / 'cm$converted'
    target = f'xaero/world-map/Multiplayer_{address}/projectseele$geofront/mw$default/'
    regions = {target + p.relative_to(converted).as_posix(): p for p in converted.rglob('*.zip')}
    caches = {target + p.relative_to(source).as_posix(): p for p in source.rglob('*.xwmc') if converted not in p.parents}
    region_name = lambda path: path.rsplit('/', 1)[1].split('.')[0]
    leaves = {region_name(n) for n in caches if n.rsplit('/', 2)[1] == 'cache_1'}
    # The regions around the baking player end up marked outdated; a client rebuilds those from their zips.
    outdated = {region_name(p.as_posix()) for p in source.rglob('*.outdated')}
    surface = {region_name(n) for n in regions if '/caves/' not in n}
    if not gate(surface, 'No baked region files in ' + str(converted)):
        return {}
    gate(surface <= leaves | outdated, ('Bake did not finish', sorted(surface - leaves - outdated)[:5]))
    saved = world / 'dimensions/projectseele/geofront/region'
    baked, newest = min(p.stat().st_mtime for p in regions.values()), max(p.stat().st_mtime for p in saved.glob('*.mca'))
    stamp = lambda t: datetime.datetime.fromtimestamp(t).isoformat(timespec='seconds')
    gate(baked > newest, 'The world changed after the map was baked (oldest zip %s, newest region %s); bake it again'
         % (stamp(baked), stamp(newest)))
    # Cave mode type 2 ("full") makes Xaero use the one baked cave layer everywhere in the GeoFront.
    config = source / 'dimension_config.txt'
    caves = {n for n in regions if '/caves/' in n}
    gate(not caves or (config.exists() and 'caveModeType:2' in config.read_text('utf8')),
         'Baked cave layer without caveModeType:2 in ' + str(config))
    settings = {f'xaero/world-map/Multiplayer_{address}/projectseele$geofront/dimension_config.txt': config} if caves else {}
    return regions | caches | settings


def jar_report(path, compare=None):
    """Size, digest and release marker classes of the shipped mod jar; with a build of current main, every class must match."""
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    with zipfile.ZipFile(path) as z:
        classes = {i.filename: i.CRC for i in z.infolist() if i.filename.startswith('com/projectseele/') and i.filename.endswith('.class')}
    missing = [c for c in RELEASE_CLASSES if 'com/projectseele/' + c + '.class' not in classes]
    gate(not missing, ('Shipped mod jar lacks release classes', missing))
    report = dict(bytes=path.stat().st_size, sha256=digest.hexdigest(), classes=len(classes), release_classes_missing=missing,
                  modified=datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds'))
    if compare:
        with zipfile.ZipFile(compare) as z:
            built = {i.filename: i.CRC for i in z.infolist() if i.filename.startswith('com/projectseele/') and i.filename.endswith('.class')}
        differ = sorted(n for n in classes.keys() & built.keys() if classes[n] != built[n])
        only_shipped, only_built = sorted(classes.keys() - built.keys()), sorted(built.keys() - classes.keys())
        gate(not (differ or only_shipped or only_built), dict(message='Shipped jar classes differ from ' + str(compare),
                                                             differ=differ[:10], only_shipped=only_shipped[:10], only_built=only_built[:10]))
        report['compared_with'] = dict(jar=str(compare), differ=len(differ), only_shipped=len(only_shipped), only_built=len(only_built))
    return report


def config_spec(source=ROOT / 'src/main/java/com/projectseele/config/SeeleConfig.java'):
    """(file, section, key) -> default value, read from the ForgeConfigSpec builder calls."""
    text = source.read_text('utf8')
    files = {'common': 'config/projectseele-common.toml', 'client': 'config/projectseele-client.toml'}
    stacks, builder, spec = {'common': [], 'client': []}, None, {}
    token = re.compile(r'\b(common|client)\.(push|pop)\(\s*(?:"([^"]+)")?\s*\)|\b(common|client)\.'
                       r'|\.define(?:InRange|InList)?\(\s*"([^"]+)"\s*,\s*("(?:\\.|[^"\\])*"|[^,)]+)')
    for m in token.finditer(text):
        if m[2] == 'push':
            builder = m[1]
            stacks[builder].append(m[3])
        elif m[2] == 'pop':
            builder = m[1]
            stacks[builder].pop()
        elif m[4]:
            builder = m[4]
        elif m[5] and builder:
            raw = m[6].strip()
            value = json.loads(raw) if raw.startswith('"') or raw in ('true', 'false') else float(raw.rstrip('DdFf'))
            spec[(files[builder], '.'.join(stacks[builder]), m[5])] = value
    return spec


def config_report(client, release_source=ROOT):
    """Shipped config files against the code's defaults. Missing keys get their defaults on first start."""
    spec, shipped = config_spec(release_source / 'src/main/java/com/projectseele/config/SeeleConfig.java'), {}
    def collect(name, nodes, section=''):
        for key, value in nodes.items():
            if isinstance(value, dict):
                collect(name, value, section + '.' + key if section else key)
            else:
                shipped[(name, section, key)] = value

    def matches(default, actual):
        if isinstance(default, float):
            return type(actual) in (int, float) and abs(actual - default) <= 1e-9
        return type(actual) is type(default) and actual == default

    for name in sorted({f for f, _, _ in spec}):
        path = client / name
        if not gate(path.is_file(), 'Config file missing: ' + name):
            continue
        collect(name, tomllib.loads(path.read_text('utf8')))
    differ = [dict(file=f, key=s + '.' + k, shipped=shipped[(f, s, k)], default=v) for (f, s, k), v in sorted(spec.items())
              if (f, s, k) in shipped and not matches(v, shipped[(f, s, k)])]
    missing = [dict(file=f, key=s + '.' + k, default=v) for (f, s, k), v in sorted(spec.items()) if (f, s, k) not in shipped]
    stale = [dict(file=f, key=s + '.' + k) for (f, s, k) in sorted(shipped) if (f, s, k) not in spec]
    return dict(keys_in_code=len(spec), differ_from_default=differ, missing_filled_on_first_start=missing, not_in_code=stale)


def server_xaerolib(client, current):
    """The xaerolib jar both Xaero mods embed, unchanged, for the server's mods folder.

    xaerolib requires itself on both sides, so a server without it shows as an incompatible FML server
    in the list (R60-R63). Only the library goes to the server: Xaero's map mods there would hand clients
    a world id and move their map folder away from the baked mw$default one (checked 2026-11-13).
    """
    found = {}
    for name in sorted(n for n in current if re.fullmatch(r'mods/xaero(minimap|worldmap)-[^/]+\.jar', n)):
        with zipfile.ZipFile(client / name) as z:
            meta = json.loads(z.read('META-INF/jarjar/metadata.json')) if 'META-INF/jarjar/metadata.json' in z.namelist() else {'jars': []}
            for jar in meta['jars']:
                if jar['identifier']['artifact'].startswith('xaerolib-'):
                    found.setdefault(jar['path'].rsplit('/', 1)[1], set()).add(z.read(jar['path']))
    if not found:
        return {}
    gate(len(found) == 1 and all(len(v) == 1 for v in found.values()),
         ('The Xaero mods embed different xaerolib builds', sorted(found)))
    name, copies = next(iter(found.items()))
    return {'mods/' + name: next(iter(copies))}


def build_inputs(a, work):
    client, world = a.client.resolve(), a.world.resolve()
    assert (world / 'level.dat').is_file() and (client / MAIN_JAR).is_file()
    seed, provenance = dh_identifier(client, world, a.logged_world_folder)
    client_lod, world_lod, lod_details = distant_caches(world, seed, a.pack, work, a.geofront_lod and a.geofront_lod.resolve())
    gate(a.geofront_lod, VERSION + ' needs --geofront-lod: the formal world still has the R62 far view (tools/rebake_r63.py core)')
    jar = jar_report(client / MAIN_JAR, a.compare_build)
    config = config_report(client, a.release_source)

    current = {p.relative_to(client).as_posix(): p for tree in CLIENT_TREES for p in files(client / tree)}
    for name in list(current):
        inactive_shader = name.startswith('shaderpacks/') and Path(name).name not in {SHADER, SHADER + '.txt'}
        if inactive_shader or name == 'config/projectseele-private-visuals-r46.json':
            del current[name]
    bundle = json.loads(current['projectseele-local-maps/combat_bundle_r44.json'].read_text('utf8'))
    missing = [n for n in bundle['files'] if 'projectseele-local-maps/' + n not in current]
    gate(not missing, ('Declared runtime resource absent', missing))
    gate('shaderPack=' + SHADER in (client / 'config/oculus.properties').read_text('utf8'), 'Oculus does not have ' + SHADER + ' selected')
    current['shaderpacks/' + SHADER] = shader_payload(current['shaderpacks/' + SHADER])
    raw_options = (client / 'options.txt').read_bytes()
    pack_line = next(l for l in raw_options.decode('utf8').splitlines() if l.startswith('resourcePacks:'))
    packs = json.loads(pack_line.split(':', 1)[1])
    if 'file/' + GRASS_PACK not in packs:
        # Last in the list is applied on top: above the terrain pack whose 128 px grass maps the shader reads.
        packs.append('file/' + GRASS_PACK)
        raw_options = raw_options.replace(pack_line.encode('utf8'),
                                          ('resourcePacks:' + json.dumps(packs, separators=(',', ':'))).encode('utf8'), 1)
    current['options.txt'] = raw_options
    current['resourcepacks/' + GRASS_PACK] = grass_pack()
    required = ['resourcepacks/' + n.removeprefix('file/') for n in packs if n.startswith('file/')]
    gate(all(n in current for n in required), ('Enabled resource pack missing', [n for n in required if n not in current]))
    if (client / 'COMPLEMENTARY_CREDITS.txt').is_file():
        current['COMPLEMENTARY_CREDITS.txt'] = client / 'COMPLEMENTARY_CREDITS.txt'
    gate(TRAFFICCRAFT in current, 'TrafficCraft must be installed: the roads are its blocks')
    gate(MTR in current, 'MTR must be installed: every railway and station is its blocks')
    with zipfile.ZipFile(client / DH_MOD) as dh:
        gpl = dh.read('LICENSE.txt')
    assert b'GNU GENERAL PUBLIC LICENSE' in gpl[:400] and b'Version 3' in gpl[:400]
    current['licenses/TrafficCraft-GPL-3.0.txt'] = gpl
    current['licenses/TrafficCraft-NOTICE.txt'] = TRAFFICCRAFT_NOTICE.encode('utf8')

    world_files = {p.relative_to(world).as_posix(): p for p in files(world)}
    world_files.update(world_lod)
    if gate(SBW_SERVER in world_files, 'World has no ' + SBW_SERVER):
        source = world_files[SBW_SERVER]
        world_files[SBW_SERVER] = sbw_server_config(source.read_bytes().decode('utf8') if isinstance(source, Path) else source.decode('utf8'))
    gate(any(n.startswith('dimensions/projectseele/geofront/data/city_rigid_generation_r45/') for n in world_files),
         'City generation data missing from the world')

    template = a.server_template
    if template is None:
        fixed = a.delivery / f'Project_SEELE_Encore_{a.template}_Server_Fix1.zip'
        template = fixed if fixed.is_file() else a.delivery / f'Project_SEELE_Encore_{a.template}_Server.zip'
    with zipfile.ZipFile(template) as z:
        names = [n for n in z.namelist() if not n.endswith('/')]
        # The template's xaerolib (R63r on) is not a client jar: server_xaerolib() below takes it out of the Xaero mods.
        server_mods = {n for n in names if n.startswith('mods/') and n.endswith('.jar') and not re.fullmatch(r'mods/xaerolib-[^/]+\.jar', n)}
        server_mods |= {DH_MOD, TRAFFICCRAFT, MTR, MAIN_JAR}
        bootstrap = {n for n in names if n.startswith(('libraries/', 'launcher-source/')) or n in {'Start-Server.bat', 'start-server.sh', 'user_jvm_args.txt', 'eula.txt', 'server.jar'}}
        if 'server.jar' in names:
            gate('server.jar' in bootstrap, 'The server template launcher is missing from the output payload')
            with zipfile.ZipFile(io.BytesIO(z.read('server.jar'))) as launcher:
                manifest = launcher.read('META-INF/MANIFEST.MF').decode('utf8')
                main_class = re.search(r'(?m)^Main-Class: ([^\r\n]+)', manifest)
                gate(main_class and main_class[1].strip().replace('.', '/') + '.class' in launcher.namelist(),
                     'Template server.jar has no runnable Main-Class')
            forge = 'libraries/net/minecraftforge/forge/1.20.1-47.4.10/'
            gate({forge + 'win_args.txt', forge + 'unix_args.txt'} <= bootstrap,
                 'Template launcher is missing the pinned Forge argument files')
        absent = server_mods - set(current)
        gate(not absent, ('Server mod missing from the client', sorted(absent)))
        server_mods &= set(current)
        gate(JVM in z.read('user_jvm_args.txt').decode('utf8'), 'Template user_jvm_args.txt lacks the JIT directive')
        props = z.read('server.properties').decode('utf8')
        icon = z.read('server-icon.png')
    props = '\n'.join('motd=' + property_value(MOTD) if l.startswith('motd=') else l for l in props.splitlines())
    gate('level-name=' + SERVER_WORLD in props, 'Template server.properties does not name ' + SERVER_WORLD)
    server = {n: p for n, p in current.items() if n.startswith(('projectseele-local-maps/', 'config/', 'defaultconfigs/', 'licenses/')) or n in server_mods}
    xaero = server_xaerolib(client, current)
    server.update(xaero)
    server_mods |= set(xaero)
    xaero_map_mods = sorted(n for n in current if re.fullmatch(r'mods/xaero(minimap|worldmap)-[^/]+\.jar', n))
    gate(not xaero_map_mods or len(xaero) == 1, ('The client has Xaero map mods but the server would lack their xaerolib', xaero_map_mods))
    gate(not any(re.match(r'mods/xaero(minimap|worldmap)-', n) for n in server_mods),
         'Xaero map mods must stay off the server: they move the clients\' map folder away from the baked minimap')
    client_dh_text = current['config/DistantHorizons.toml'].read_text('utf8')
    server['config/DistantHorizons.toml'] = server_dh_config(client_dh_text)
    current['config/DistantHorizons.toml'] = client_dh_config(client_dh_text)
    server.update({SERVER_WORLD + '/' + n: p for n, p in world_files.items()})
    server.update({'server.properties': (props + '\n').encode('ascii'), 'server-icon.png': icon})

    with zipfile.ZipFile(a.client_template or a.delivery / f'Project_SEELE_Encore_{a.template}_Client_PCL.zip') as z:
        manifest = json.loads(z.read('manifest.json'))
    assert not manifest.get('files')
    manifest.update(name=NAME, version=VERSION + '-' + a.date)
    minimap = xaero_map(a.xaero_map.resolve(), world, a.server_address) if a.xaero_map else {}
    gate(a.xaero_map, 'No --xaero-map given: bake the minimap with tools/rebake_r63.py xaero')
    pcl = {'overrides/' + n: p for n, p in (current | client_lod | minimap).items()}
    pcl['overrides/servers.dat'] = servers_dat('SEELE', a.server_address)
    pcl['manifest.json'] = json_bytes(manifest)
    # PCL starts Java in the instance folder, so this relative path survives extraction anywhere.
    pcl['overrides/PCL/Setup.ini'] = ('VersionArgumentIndie:1\r\nVersionArgumentIndieV2:True\r\nVersionAdvanceJvm:' + JVM + '\r\n').encode()

    batch = dict(version=VERSION, date=a.date, actual_save=str(world), client_contains_save=False, map_state=a.map_note,
                 acceptance='Friends test package; content and archive integrity checked, not verified in game')
    for payload, prefix in ((server, ''), (pcl, 'overrides/')):
        payload[prefix + JIT] = client / JIT
        payload[prefix + VERSION + '_QUICKSTART.zh.md'] = a.release_source / f'docs/{VERSION}_QUICKSTART.zh.md'
        payload[prefix + VERSION + '_RELEASE.zh.md'] = a.release_source / f'docs/{VERSION}_RELEASE.zh.md'
        payload[prefix + VERSION + '_BATCH.json'] = json_bytes(batch)
        absent = sorted(name for name, value in payload.items() if isinstance(value, Path) and not value.is_file())
        gate(not absent, ('Payload file missing', absent[:10]))
    regions = sum(1 for n in minimap if n.endswith('.zip') and '/caves/' not in n)
    return dict(world=world, template=template, bootstrap=bootstrap, server=server, pcl=pcl, lod=lod_details, dh_key=seed,
                dh_source=provenance, server_mods=sorted(server_mods), jar=jar, config=config, minimap_region_zips=regions)


def package(target, payload, level, template=None, bootstrap=()):
    partial = target.with_suffix('.zip.partial')
    if target.exists() or partial.exists():
        raise FileExistsError('Keep the existing output: ' + str(target))
    before = {n: (p.stat().st_size, p.stat().st_mtime_ns) for n, p in payload.items() if isinstance(p, Path)}

    def method(name):
        return zipfile.ZIP_STORED if name.lower().endswith(STORED) else zipfile.ZIP_DEFLATED

    print('Writing ' + target.name, flush=True)
    with zipfile.ZipFile(partial, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=level, allowZip64=True) as output:
        if template:
            with zipfile.ZipFile(template) as old:
                for name in sorted(bootstrap):
                    output.writestr(name, old.read(name), compress_type=method(name), compresslevel=level)
        for index, (name, value) in enumerate(sorted(payload.items()), 1):
            if isinstance(value, Path):
                output.write(value, name, compress_type=method(name), compresslevel=level)
            else:
                output.writestr(name, value, compress_type=method(name), compresslevel=level)
            if index % 2000 == 0:
                print(f'{target.name}: {index}/{len(payload)}', flush=True)
    for name, value in payload.items():
        if isinstance(value, Path) and (value.stat().st_size, value.stat().st_mtime_ns) != before[name]:
            raise RuntimeError('Input changed during packaging: ' + str(value))
    with zipfile.ZipFile(partial) as output:
        names = output.namelist()
        assert len(names) == len(set(names)) and set(names) == set(payload) | set(bootstrap)
        for name, value in payload.items():
            assert output.getinfo(name).file_size == (before[name][0] if isinstance(value, Path) else len(value)), name
        bad = output.testzip()
        assert bad is None, ('CRC failure', bad)
        if 'manifest.json' in names:
            assert json.loads(output.read('manifest.json'))['name'] == NAME
            assert not any(n.startswith(('overrides/saves/', 'overrides/assets/', 'overrides/libraries/')) for n in names)
            assert [n for n in names if n.startswith('overrides/PCL/')] == ['overrides/PCL/Setup.ini']
    partial.replace(target)
    result = dict(file=str(target), bytes=target.stat().st_size, entries=len(names), crc_checked=True)
    print(json.dumps(result), flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--client', type=Path, default=Path('F:/eva/artifacts/r53_repair_20261015/client'))
    p.add_argument('--world', type=Path, default=Path('F:/eva/artifacts/r53_repair_20261015/client/saves/HOTFIX_20261025'))
    p.add_argument('--delivery', type=Path, default=Path('F:/eva/delivery'))
    p.add_argument('--date', help='YYYYMMDD; required with --pack')
    p.add_argument('--map-note', help='One line on the map state, recorded in the batch file; required with --pack')
    p.add_argument('--server-address', help='Host friends connect to, default port; keyed into the client minimap cache and server list; '
                                            'required with --pack, never written into the repository')
    p.add_argument('--xaero-map', type=Path, help='xaero/world-map/WORLD/projectseele$geofront written by a -Dprojectseele.xaeroBake=true run on a copy of --world')
    p.add_argument('--geofront-lod', type=Path, help='GeoFront DistantHorizons.sqlite from tools/rebake_r63.py (WORK/out/geofront_lod.sqlite)')
    p.add_argument('--compare-build', type=Path, help='A jar built from current main: every com/projectseele class of the shipped jar must match it')
    p.add_argument('--release-source', type=Path, default=ROOT, help='Matching source checkout for config defaults and the two release documents')
    p.add_argument('--logged-world-folder', help='Original folder of a renamed world copy, as recorded in the source client DH logs')
    p.add_argument('--server-template', type=Path, help='Server ZIP supplying Forge libraries and startup files')
    p.add_argument('--client-template', type=Path, help='Client PCL ZIP supplying the manifest')
    p.add_argument('--template', default='R63r_20261115', help='Version and date of the previous release whose zips supply the bootstrap')
    group = p.add_mutually_exclusive_group()
    group.add_argument('--pack', action='store_true')
    group.add_argument('--check', type=Path, metavar='REPORT', help='Run every gate, write the report here, never pack')
    a = p.parse_args()
    if a.check:
        global CHECK
        CHECK = []
        a.date = a.date or datetime.date.today().strftime('%Y%m%d')
        a.map_note = a.map_note or '(check)'
        a.server_address = a.server_address or 'check.invalid'
    elif a.pack:
        missing = [n for n in ('date', 'map_note', 'server_address', 'xaero_map', 'geofront_lod') if not getattr(a, n)]
        assert not missing, 'Packing needs --' + ', --'.join(n.replace('_', '-') for n in missing)
    a.date = a.date or datetime.date.today().strftime('%Y%m%d')
    a.server_address = a.server_address or 'inventory.invalid'
    assert re.fullmatch(r'\d{8}', a.date)
    with tempfile.TemporaryDirectory(dir=a.delivery, prefix='release-lod-') as work, stopped_world(a.world) if a.pack else nullcontext():
        d = build_inputs(a, Path(work))
        size = lambda payload: sum(v.stat().st_size if isinstance(v, Path) and v.is_file() else 0 if isinstance(v, Path) else len(v)
                                   for v in payload.values())
        report = dict(version=VERSION, date=a.date, pack_written=False, actual_world=str(d['world']), manifest_name=NAME,
                      server_world_directory=SERVER_WORLD, map_state=a.map_note, dh=d['lod'], dh_key=d['dh_key'],
                      dh_identifier_source=d['dh_source'], server_mods=d['server_mods'], client_contains_save=False,
                      main_jar=d['jar'], release_source=str(a.release_source.resolve()), config=d['config'], minimap_region_zips=d['minimap_region_zips'],
                      raw_bytes=dict(server=size(d['server']), client=size(d['pcl'])), jit_directive=JVM,
                      compression='Already compressed media stored; everything else DEFLATE, client level 9, server level 3')
        print(json.dumps({k: report[k] for k in ('dh', 'dh_key', 'raw_bytes', 'minimap_region_zips')}, ensure_ascii=False), flush=True)
        if a.check:
            report.update(check_failures=CHECK, template=a.template, server_template=str(d['template']),
                          client_template=str(a.client_template or a.delivery / f'Project_SEELE_Encore_{a.template}_Client_PCL.zip'),
                          geofront_lod=str(a.geofront_lod or ''), xaero_map=str(a.xaero_map or ''))
            a.check.write_bytes(json_bytes(report))
            print(json.dumps(dict(check_failures=CHECK), ensure_ascii=False, indent=1), flush=True)
            print(VERSION + ' check: %d failure(s), report %s' % (len(CHECK), a.check), flush=True)
            raise SystemExit(1 if CHECK else 0)
        if a.pack:
            report['outputs'] = [
                package(a.delivery / f'Project_SEELE_Encore_{VERSION}_{a.date}_Client_PCL.zip', d['pcl'], 9),
                package(a.delivery / f'Project_SEELE_Encore_{VERSION}_{a.date}_Server.zip', d['server'], 3, d['template'], d['bootstrap'])]
            report['pack_written'] = True
            (a.delivery / f'{VERSION}_{a.date}_receipt.json').write_bytes(json_bytes(report))
    print(VERSION + (' packed' if a.pack else ' inventory ready (nothing written)'), flush=True)


if __name__ == '__main__':
    main()
