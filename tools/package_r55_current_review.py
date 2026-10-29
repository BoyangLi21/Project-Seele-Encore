"""Package the current saved R55 game; old archives supply bootstrap only."""
from pathlib import Path
from contextlib import nullcontext
import argparse
import json
import zipfile
import package_r54_current_review as base

NAME = 'EVANGELION_Encore_R55'
JIT = 'jit-recovery-r54.json'
JVM = '-XX:+UnlockDiagnosticVMOptions -XX:CompilerDirectivesFile=' + JIT


def inputs(a):
    d = base.build_inputs(a)
    for payload, prefix in ((d['server'], ''), (d['pcl'], 'overrides/')):
        for name in list(payload):
            if name.startswith(prefix + 'R54_'):
                del payload[name]
        payload[prefix + JIT] = d['client'] / JIT
        payload[prefix + 'R55_QUICKSTART.zh.md'] = base.ROOT / 'docs/R55_QUICKSTART.zh.md'
        payload[prefix + 'R55_RELEASE.zh.md'] = base.ROOT / 'docs/R55_RELEASE.zh.md'
        payload[prefix + 'R55_BATCH.json'] = base.jsonbytes(dict(
            version='R55', date=a.date, build=a.build, actual_save=str(d['world']),
            client_contains_save=False, progress='Current normally saved player/entity/mission state retained',
            map_scope='R54 installed geography; new Lake Ashi and roads are the following work batch',
            acceptance='Compiled and packaged; visual acceptance belongs to the player'))
    manifest = json.loads(d['pcl']['manifest.json'])
    manifest.update(name=NAME, version='R55-' + a.date)
    d['pcl']['manifest.json'] = base.jsonbytes(manifest)
    # PCL starts Java in PathIndie; this relative path survives extraction anywhere.
    # Only instance settings are shipped, never launcher binaries/account data.
    d['pcl']['overrides/PCL/Setup.ini'] = ('VersionArgumentIndie:1\r\n'
        'VersionArgumentIndieV2:True\r\nVersionAdvanceJvm:' + JVM + '\r\n').encode()
    with zipfile.ZipFile(d['template']) as old:
        args = old.read('user_jvm_args.txt').decode('utf8').rstrip()
    d['bootstrap'].discard('user_jvm_args.txt')
    d['server']['user_jvm_args.txt'] = (args + '\n' + JVM + '\n').encode('utf8')
    props = d['server']['server.properties'].decode('ascii')
    motd = base.MOTD.replace('R54', 'R55')
    d['server']['server.properties'] = '\n'.join(
        'motd=' + base.property_value(motd) if line.startswith('motd=') else line
        for line in props.splitlines()).encode('ascii') + b'\n'
    return d


def package(target, payload, template=None, bootstrap=()):
    partial = target.with_suffix('.zip.partial')
    if target.exists() or partial.exists():
        raise FileExistsError('Preserve existing output: ' + str(target))
    before = {n: (p.stat().st_size, p.stat().st_mtime_ns)
              for n, p in payload.items() if isinstance(p, Path)}
    def compression(name):
        return zipfile.ZIP_STORED if name.endswith(('.jar', '.zip', '.png', '.ogg', '.gz', '.jpg')) else zipfile.ZIP_DEFLATED
    print('Writing ' + target.name, flush=True)
    with zipfile.ZipFile(partial, 'x', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=3, allowZip64=True) as output:
        if template:
            with zipfile.ZipFile(template) as old:
                for name in sorted(bootstrap):
                    output.writestr(name, old.read(name), compress_type=compression(name))
        for index, (name, p) in enumerate(sorted(payload.items()), 1):
            if isinstance(p, Path):
                output.write(p, name, compress_type=compression(name))
            else:
                output.writestr(name, p, compress_type=compression(name))
            if index % 1000 == 0:
                print(f'{target.name}: {index}/{len(payload)} files', flush=True)
    for name, p in payload.items():
        if isinstance(p, Path) and (p.stat().st_size, p.stat().st_mtime_ns) != before[name]:
            raise RuntimeError('Input changed during packaging: ' + str(p))
    with zipfile.ZipFile(partial) as output:
        names = output.namelist()
        assert len(names) == len(set(names)) and set(names) == set(payload) | set(bootstrap)
        for name, p in payload.items():
            assert output.getinfo(name).file_size == (before[name][0] if isinstance(p, Path) else len(p)), name
        # Small launch/save declarations are read once. Large assets are not
        # decompressed for a second full audit after writing.
        critical = {'manifest.json', 'server.properties', 'user_jvm_args.txt',
                    'R55_BATCH.json', 'overrides/R55_BATCH.json',
                    'overrides/PCL/Setup.ini', base.SERVER_WORLD + '/level.dat'}
        for name in critical & set(payload):
            p = payload[name]
            assert output.read(name) == (p.read_bytes() if isinstance(p, Path) else p), name
        if 'manifest.json' in names:
            assert json.loads(output.read('manifest.json'))['name'] == NAME
            assert not any(n.startswith(('overrides/saves/', 'overrides/assets/', 'overrides/libraries/')) for n in names)
            assert [n for n in names if n.startswith('overrides/PCL/')] == ['overrides/PCL/Setup.ini']
    partial.replace(target)
    result = dict(file=str(target), bytes=target.stat().st_size, entries=len(names),
                  inventory_and_small_launch_declarations_checked=True)
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(__doc__)
    for name in ('base', 'world', 'delivery', 'icon', 'plan'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--date', default='20261029')
    parser.add_argument('--build', type=int, default=1024)
    parser.add_argument('--pack', action='store_true')
    a = parser.parse_args()
    a.revision = ''
    with base.stopped_world(a.world) if a.pack else nullcontext():
        if a.pack:
            base.require_normal_save(a.base / 'client')
        d = inputs(a)
        report = dict(version='R55', pack_written=False, actual_world=str(d['world']),
                      manifest_name=NAME, server_world_directory=base.SERVER_WORLD,
                      dh=d['lod'], dh_identifier_source=d['dh_provenance'],
                      server_mods=sorted(d['server_mods']),
                      compression='Store already compressed media; DEFLATE level 3 for other files',
                      client_contains_save=False, jit_directive=JVM,
                      current_progress_retained=True, new_lake_and_roads='Next batch')
        a.plan.parent.mkdir(parents=True, exist_ok=True)
        a.plan.write_bytes(base.jsonbytes(report))
        if a.pack:
            report['outputs'] = [package(a.delivery / f'Project_SEELE_Encore_R55_{a.date}_{side}.zip',
                d[key], d['template'] if key == 'server' else None,
                d['bootstrap'] if key == 'server' else ())
                for side, key in (('Server', 'server'), ('Client_PCL', 'pcl'))]
            report['pack_written'] = True
            a.plan.write_bytes(base.jsonbytes(report))
    print('R55 complete' if a.pack else 'R55 inventory ready', flush=True)


if __name__ == '__main__':
    main()
