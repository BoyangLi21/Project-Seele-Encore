"""Package the current game as one release: a server zip with the world and a PCL client zip without it.

Inventory only by default; --pack writes both zips. The R55 packages supply the server
bootstrap (libraries, start scripts), server.properties, the icon and the PCL manifest.
--pack holds the world's session.lock while it reads, so nothing may have the world open.
"""
from contextlib import contextmanager, nullcontext
from pathlib import Path
import argparse
import gzip
import io
import json
import os
import re
import shutil
import sqlite3
import struct
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'R62'
NAME = 'EVANGELION_Encore_' + VERSION
SHADER = 'SEELE_Local_Cavern_R53_Review_20261026.zip'
SERVER_WORLD = 'SEELE_R53_WORLD'
JIT = 'jit-recovery-r54.json'
JVM = '-XX:+UnlockDiagnosticVMOptions -XX:CompilerDirectivesFile=' + JIT
MOTD = '§b§lEVANGELION:Encore ' + VERSION + ' §r\n§6NERV！ §8| §aEVA！§8| §fSEELE!'
DH_MOD = 'mods/DistantHorizons-2.3.4-b-1.20.1-fabric-forge.jar'
TRAFFICCRAFT = 'mods/trafficcraft-forge-1.20.1-1.1.3.jar'
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


def dh_identifier(client, world):
    display = level_name(world)
    patterns = [re.compile(r'DhClientServerLevel\{' + re.escape(n) + r'_([0-9a-v]{13})@') for n in {world.name, display}]
    logs = [client / 'logs/latest.log'] + sorted((client / 'logs').glob('*.log.gz'), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in logs:
        if not path.exists():
            continue
        text = gzip.open(path, 'rt', encoding='utf8', errors='replace').read() if path.suffix == '.gz' else path.read_text('utf8', errors='replace')
        found = {m for pattern in patterns for m in pattern.findall(text)}
        if len(found) > 1:
            raise ValueError('Ambiguous DH key in ' + str(path))
        if found:
            return found.pop(), dict(log=str(path), world_folder=world.name, level_display_name=display)
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


def distant_caches(world, seed, pack, work):
    client, server, details = {}, {}, []
    for dim in dimensions(world):
        db = dim / 'data/DistantHorizons.sqlite'
        if not db.exists():
            continue
        rel = dim.relative_to(world).as_posix()
        name = {'.': 'minecraft:overworld', 'DIM-1': 'minecraft:the_nether', 'DIM1': 'minecraft:the_end'}.get(rel) or ':'.join(Path(rel).parts[1:])
        wal = Path(str(db) + '-wal')
        if pack and wal.exists() and wal.stat().st_size:
            raise RuntimeError('DH database has an unmerged WAL: ' + str(db))
        client['Distant_Horizons_server_data/SEELE/' + (seed + '@' + name).replace(':', '@@') + '/DistantHorizons.sqlite'] = db
        entry = db.relative_to(world).as_posix()
        server[entry] = aged_lod_copy(db, work / entry) if pack else db
        details.append(dict(dimension=name, bytes=db.stat().st_size))
    assert {'data/DistantHorizons.sqlite', 'dimensions/projectseele/geofront/data/DistantHorizons.sqlite'} <= set(server)
    return client, server, details


def shader_payload(path):
    with zipfile.ZipFile(path) as source:
        patched = {}
        for member, original, replacement in SHADER_PATCHES:
            text = patched.get(member, source.read(member).decode('utf8'))
            if replacement not in text:
                assert text.count(original) == 1
                patched[member] = text.replace(original, replacement)
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


def server_dh_config(text):
    # Remote city motion must update LODs outside vanilla chunk tracking, without generating distant terrain.
    return dh_config(text, {'numberOfThreads': '2', 'threadRunTimeRatio': '"0.5"', 'enableDistantGeneration': 'false',
                            'distantGeneratorMode': '"PRE_EXISTING_ONLY"', 'enableRealTimeUpdates': 'true',
                            'realTimeUpdateDistanceRadiusInChunks': '256', 'synchronizeOnLoad': 'true',
                            'sendLevelKeys': 'true', 'levelKeyPrefix': '""'})


def client_dh_config(text):
    # Two threads at half duty leave the preinstalled terrain filling in for a minute after joining.
    return dh_config(text, {'numberOfThreads': '4', 'threadRunTimeRatio': '"1.0"'})


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
    assert surface, 'No baked region files in ' + str(converted)
    assert surface <= leaves | outdated, ('Bake did not finish', sorted(surface - leaves - outdated)[:5])
    saved = world / 'dimensions/projectseele/geofront/region'
    assert min(p.stat().st_mtime for p in regions.values()) > max(p.stat().st_mtime for p in saved.glob('*.mca')), \
        'The world changed after the map was baked; bake it again'
    return regions | caches


def build_inputs(a, work):
    client, world = a.client.resolve(), a.world.resolve()
    assert (world / 'level.dat').is_file() and (client / 'mods/projectseele-0.1.0-all.jar').is_file()
    seed, provenance = dh_identifier(client, world)
    client_lod, world_lod, lod_details = distant_caches(world, seed, a.pack, work)

    current = {p.relative_to(client).as_posix(): p for tree in CLIENT_TREES for p in files(client / tree)}
    for name in list(current):
        inactive_shader = name.startswith('shaderpacks/') and Path(name).name not in {SHADER, SHADER + '.txt'}
        if inactive_shader or name == 'config/projectseele-private-visuals-r46.json':
            del current[name]
    bundle = json.loads(current['projectseele-local-maps/combat_bundle_r44.json'].read_text('utf8'))
    missing = [n for n in bundle['files'] if 'projectseele-local-maps/' + n not in current]
    assert not missing, ('Declared runtime resource absent', missing)
    assert 'shaderPack=' + SHADER in (client / 'config/oculus.properties').read_text('utf8')
    current['shaderpacks/' + SHADER] = shader_payload(current['shaderpacks/' + SHADER])
    current['options.txt'] = client / 'options.txt'
    options = (client / 'options.txt').read_text('utf8')
    packs = json.loads(next(l.split(':', 1)[1] for l in options.splitlines() if l.startswith('resourcePacks:')))
    required = ['resourcepacks/' + n.removeprefix('file/') for n in packs if n.startswith('file/')]
    assert all(n in current for n in required), required
    if (client / 'COMPLEMENTARY_CREDITS.txt').is_file():
        current['COMPLEMENTARY_CREDITS.txt'] = client / 'COMPLEMENTARY_CREDITS.txt'
    assert TRAFFICCRAFT in current, 'TrafficCraft must be installed: the roads are its blocks'
    with zipfile.ZipFile(client / DH_MOD) as dh:
        gpl = dh.read('LICENSE.txt')
    assert b'GNU GENERAL PUBLIC LICENSE' in gpl[:400] and b'Version 3' in gpl[:400]
    current['licenses/TrafficCraft-GPL-3.0.txt'] = gpl
    current['licenses/TrafficCraft-NOTICE.txt'] = TRAFFICCRAFT_NOTICE.encode('utf8')

    world_files = {p.relative_to(world).as_posix(): p for p in files(world)}
    world_files.update(world_lod)
    assert any(n.startswith('dimensions/projectseele/geofront/data/city_rigid_generation_r45/') for n in world_files)

    template = a.delivery / 'Project_SEELE_Encore_R55_20261029_Server.zip'
    with zipfile.ZipFile(template) as z:
        names = [n for n in z.namelist() if not n.endswith('/')]
        server_mods = {n for n in names if n.startswith('mods/') and n.endswith('.jar')} | {DH_MOD, TRAFFICCRAFT}
        bootstrap = {n for n in names if n.startswith('libraries/') or n in {'Start-Server.bat', 'start-server.sh', 'user_jvm_args.txt', 'eula.txt'}}
        absent = server_mods - set(current)
        assert not absent, ('Server mod missing from the client', absent)
        assert JVM in z.read('user_jvm_args.txt').decode('utf8')
        props = z.read('server.properties').decode('utf8')
        icon = z.read('server-icon.png')
    props = '\n'.join('motd=' + property_value(MOTD) if l.startswith('motd=') else l for l in props.splitlines())
    assert 'level-name=' + SERVER_WORLD in props
    server = {n: p for n, p in current.items() if n.startswith(('projectseele-local-maps/', 'config/', 'defaultconfigs/', 'licenses/')) or n in server_mods}
    client_dh_text = current['config/DistantHorizons.toml'].read_text('utf8')
    server['config/DistantHorizons.toml'] = server_dh_config(client_dh_text)
    current['config/DistantHorizons.toml'] = client_dh_config(client_dh_text)
    server.update({SERVER_WORLD + '/' + n: p for n, p in world_files.items()})
    server.update({'server.properties': (props + '\n').encode('ascii'), 'server-icon.png': icon})

    with zipfile.ZipFile(a.delivery / 'Project_SEELE_Encore_R55_20261029_Client_PCL.zip') as z:
        manifest = json.loads(z.read('manifest.json'))
    assert not manifest.get('files')
    manifest.update(name=NAME, version=VERSION + '-' + a.date)
    pcl = {'overrides/' + n: p for n, p in (current | client_lod | xaero_map(a.xaero_map.resolve(), world, a.server_address)).items()}
    pcl['overrides/servers.dat'] = servers_dat('SEELE', a.server_address)
    pcl['manifest.json'] = json_bytes(manifest)
    # PCL starts Java in the instance folder, so this relative path survives extraction anywhere.
    pcl['overrides/PCL/Setup.ini'] = ('VersionArgumentIndie:1\r\nVersionArgumentIndieV2:True\r\nVersionAdvanceJvm:' + JVM + '\r\n').encode()

    batch = dict(version=VERSION, date=a.date, actual_save=str(world), client_contains_save=False, map_state=a.map_note,
                 acceptance='Friends test package; content and archive integrity checked, not verified in game')
    for payload, prefix in ((server, ''), (pcl, 'overrides/')):
        payload[prefix + JIT] = client / JIT
        payload[prefix + VERSION + '_QUICKSTART.zh.md'] = ROOT / f'docs/{VERSION}_QUICKSTART.zh.md'
        payload[prefix + VERSION + '_RELEASE.zh.md'] = ROOT / f'docs/{VERSION}_RELEASE.zh.md'
        payload[prefix + VERSION + '_BATCH.json'] = json_bytes(batch)
        for name, value in payload.items():
            if isinstance(value, Path):
                assert value.is_file(), value
    return dict(world=world, template=template, bootstrap=bootstrap, server=server, pcl=pcl,
                lod=lod_details, dh_key=seed, dh_source=provenance, server_mods=sorted(server_mods))


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
    p.add_argument('--date', required=True)
    p.add_argument('--map-note', required=True, help='One line on the map state, recorded in the batch file')
    p.add_argument('--server-address', required=True, help='Host friends connect to, default port; keyed into the client minimap cache and server list')
    p.add_argument('--xaero-map', type=Path, required=True, help='xaero/world-map/WORLD/projectseele$geofront written by a -Dprojectseele.xaeroBake=true run on a copy of --world')
    p.add_argument('--pack', action='store_true')
    a = p.parse_args()
    assert re.fullmatch(r'\d{8}', a.date)
    with tempfile.TemporaryDirectory(dir=a.delivery, prefix='release-lod-') as work, stopped_world(a.world) if a.pack else nullcontext():
        d = build_inputs(a, Path(work))
        size = lambda payload: sum(v.stat().st_size if isinstance(v, Path) else len(v) for v in payload.values())
        report = dict(version=VERSION, date=a.date, pack_written=False, actual_world=str(d['world']), manifest_name=NAME,
                      server_world_directory=SERVER_WORLD, map_state=a.map_note, dh=d['lod'], dh_key=d['dh_key'],
                      dh_identifier_source=d['dh_source'], server_mods=d['server_mods'], client_contains_save=False,
                      raw_bytes=dict(server=size(d['server']), client=size(d['pcl'])), jit_directive=JVM,
                      compression='Already compressed media stored; everything else DEFLATE, client level 9, server level 3')
        print(json.dumps({k: report[k] for k in ('dh', 'dh_key', 'raw_bytes')}, ensure_ascii=False), flush=True)
        if a.pack:
            report['outputs'] = [
                package(a.delivery / f'Project_SEELE_Encore_{VERSION}_{a.date}_Client_PCL.zip', d['pcl'], 9),
                package(a.delivery / f'Project_SEELE_Encore_{VERSION}_{a.date}_Server.zip', d['server'], 3, d['template'], d['bootstrap'])]
            report['pack_written'] = True
            (a.delivery / f'{VERSION}_{a.date}_receipt.json').write_bytes(json_bytes(report))
    print(VERSION + (' packed' if a.pack else ' inventory ready (nothing written)'), flush=True)


if __name__ == '__main__':
    main()
