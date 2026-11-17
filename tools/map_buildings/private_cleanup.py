"""Take the old imported bodies of private towers 93-95 out of a world's city data, without code changes.

  prepare <formal world> <donor world> <bundle dir>
      Reads both worlds only. The donor is a copy of the same world (same WorldUUID) that already carries the new
      93-95 bodies and has made two lift trips in the same directions as the formal world's last two journeys, so its
      journals for 93-95 are what the lift itself writes for the new bodies.
  apply <world> <bundle dir> <backup dir> [--dry-run]
      Checks every target's md5 and that the world's parked 93-95 bodies are the new ones, copies every touched file
      to the backup dir (same relative path), then replaces or moves. Nothing is deleted.

What holds the old bodies and why each action is safe (CityRigidGenerationR45, CityCreateDistrictR45):
  data/projectseele_city_private_cargo_r45_{0,1,2}.dat      no code reads them                    -> move to backup
  city_rigid_journal_r45/<current|previous>/{93,94,95}.dat  chunk generation reads Cells of the    -> replace with the
                                                            committed journey; the lift reads a      donor's lift-written
                                                            journal only while that journey runs     files, Journey kept
  city_rigid_journal_r45/<other journeys>/{93,94,95}.dat     not referenced by the control ledger   -> move to backup
  city_rigid_generation_r45/cargo/{93,94,95}.dat            chunk generation always opens it        -> Cargo replaced by
                                                            (must exist)                             the new body
"""
import argparse, hashlib, json, shutil, sys, uuid
from pathlib import Path
import nbtlib

DATA = Path('dimensions/projectseele/geofront/data')
REGION = 'dimensions/projectseele/geofront/region'
TOWERS = (93, 94, 95)


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def as_uuid(a):
    a = [int(x) & 0xffffffff for x in a]
    return str(uuid.UUID(int=(a[0] << 96) | (a[1] << 64) | (a[2] << 32) | a[3]))


def control(world):
    files = sorted((Path(world) / DATA).glob('projectseele_city_rigid_control_r45_*.dat'))
    if len(files) != 1:
        raise SystemExit('expected one city control ledger in ' + str(world))
    c = nbtlib.load(files[0])['data']
    prev = c['PreviousCommittedLedgerR48']
    return dict(uuid=str(c['WorldUUID']), phase=str(c['Phase']), depth=int(c['Depth']),
                current=(as_uuid(c['Journey']), int(c['JourneySourceDepth']), int(c['JourneyTargetDepth']), c['Journey']),
                previous=(as_uuid(prev['Journey']), int(prev['JourneySourceDepth']), int(prev['JourneyTargetDepth']), prev['Journey']))


def unpack(v):
    v = int(v)

    def sx(v, b):
        return v - (1 << b) if v >= 1 << (b - 1) else v
    return sx((v >> 38) & ((1 << 26) - 1), 26), sx(v & 0xFFF, 12), sx((v >> 12) & ((1 << 26) - 1), 26)


def state(s):
    p = s.get('Properties')
    return str(s['Name']) + ('[' + ','.join(f'{k}={v}' for k, v in sorted(p.items())) + ']' if p else '')


def prepare(a):
    formal, donor, out = Path(a.formal), Path(a.donor), Path(a.bundle)
    f, d = control(formal), control(donor)
    if f['uuid'] != d['uuid']:
        raise SystemExit('donor is not a copy of this world')
    for k in ('current', 'previous'):
        if f[k][1:3] != d[k][1:3]:
            raise SystemExit(f'{k} journey directions differ: formal {f[k][1:3]} donor {d[k][1:3]}')
    if out.exists():
        raise SystemExit('bundle dir exists: ' + str(out))
    rows = []

    def stage(rel, tag):
        dst = out / 'files' / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        tag.save(dst, gzipped=True)
        rows.append(dict(path=str(rel).replace('\\', '/'), action='replace', old_md5=md5(formal / rel), new_md5=md5(dst)))
    journals = formal / DATA / 'city_rigid_journal_r45'
    for i in TOWERS:
        for k in ('current', 'previous'):
            tag = nbtlib.load(donor / DATA / 'city_rigid_journal_r45' / d[k][0] / f'{i}.dat')
            if int(tag['Index']) != i or str(tag['WorldUUID']) != f['uuid']:
                raise SystemExit('unexpected donor journal ' + d[k][0] + f'/{i}.dat')
            tag['Journey'] = nbtlib.IntArray([int(x) for x in f[k][3]])
            stage(DATA / 'city_rigid_journal_r45' / f[k][0] / f'{i}.dat', tag)
        body = nbtlib.load(donor / DATA / 'city_rigid_journal_r45' / d['current'][0] / f'{i}.dat')['Cells']
        cargo = nbtlib.load(formal / DATA / 'city_rigid_generation_r45' / 'cargo' / f'{i}.dat')
        cells = []
        for c in body:
            c = nbtlib.Compound(c)
            if 'Data' in c:
                c['NBT'] = c.pop('Data')
            cells.append(c)
        cargo['data']['Buildings'][0]['Cargo'] = nbtlib.List[nbtlib.Compound](cells)
        stage(DATA / 'city_rigid_generation_r45' / 'cargo' / f'{i}.dat', cargo)
    for n in range(3):
        rel = DATA / f'projectseele_city_private_cargo_r45_{n}.dat'
        if (formal / rel).exists():
            rows.append(dict(path=str(rel).replace('\\', '/'), action='move', old_md5=md5(formal / rel)))
    live = {f['current'][0], f['previous'][0]}
    for j in sorted(p for p in journals.iterdir() if p.is_dir() and p.name not in live):
        for i in TOWERS:
            if (j / f'{i}.dat').exists():
                rel = DATA / 'city_rigid_journal_r45' / j.name / f'{i}.dat'
                rows.append(dict(path=str(rel).replace('\\', '/'), action='move', old_md5=md5(formal / rel)))
    manifest = dict(world_uuid=f['uuid'], current=f['current'][0], previous=f['previous'][0], rows=rows)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1), 'utf8')
    print(json.dumps(dict(replace=sum(r['action'] == 'replace' for r in rows), move=sum(r['action'] == 'move' for r in rows),
                          manifest_md5=md5(out / 'manifest.json'))))


def check_bodies(world, bundle, man, depth):
    sys.path.insert(0, str(Path(__file__).parent))
    from mca import World
    w = World(str(Path(world) / REGION))
    report = {}
    for i in TOWERS:
        tag = nbtlib.load(Path(bundle) / 'files' / DATA / 'city_rigid_journal_r45' / man['current'] / f'{i}.dat')
        cx, cy, cz = unpack(tag['Centre'])
        base = cy if depth == 0 else int(tag['RetractedY'])
        half, height = int(tag['Half']), int(tag['Height'])
        want = {unpack(c['Pos']): state(c['State']) for c in tag['Cells']}
        got = {}
        for y in range(height + 4):
            for z in range(int(tag['MinZ']), int(tag['MaxZ']) + 1):
                for x in range(int(tag['MinX']), int(tag['MaxX']) + 1):
                    s = w.get(cx + x, base + y, cz + z) or 'minecraft:air'
                    if not s.endswith(':air') and not s.endswith('cave_air') and not s.endswith('void_air'):
                        got[(x, y, z)] = s
        report[i] = dict(cells=len(want), world=len(got), wrong=sum(1 for k in set(want) | set(got) if want.get(k) != got.get(k)))
    return report


def apply(a):
    world, bundle, backup = Path(a.world), Path(a.bundle), Path(a.backup)
    man = json.loads((bundle / 'manifest.json').read_text('utf8'))
    c = control(world)
    if c['uuid'] != man['world_uuid'] or c['current'][0] != man['current'] or c['previous'][0] != man['previous']:
        raise SystemExit('world ledger does not match the bundle (another lift trip happened?)')
    if c['phase'] != 'IDLE':
        raise SystemExit('city lift is not IDLE')
    if world.resolve() in backup.resolve().parents or backup.resolve() == world.resolve():
        raise SystemExit('backup dir must be outside the world')
    bad = [r['path'] for r in man['rows'] if not (world / r['path']).is_file() or md5(world / r['path']) != r['old_md5']]
    if bad:
        raise SystemExit('targets differ from the bundle: ' + ', '.join(bad[:5]))
    bodies = check_bodies(world, bundle, man, c['depth'])
    if any(v['wrong'] for v in bodies.values()):
        raise SystemExit('world does not carry the new 93-95 bodies yet: ' + json.dumps(bodies))
    clash = [r['path'] for r in man['rows'] if (backup / r['path']).exists()]
    if clash:
        raise SystemExit('backup already holds: ' + ', '.join(clash[:5]))
    if a.dry_run:
        print(json.dumps(dict(dry_run=True, bodies=bodies, rows=len(man['rows']))))
        return
    for r in man['rows']:
        src, keep = world / r['path'], backup / r['path']
        keep.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, keep)
        if md5(keep) != r['old_md5']:
            raise SystemExit('backup copy differs: ' + r['path'])
    for r in man['rows']:
        src = world / r['path']
        if r['action'] == 'replace':
            shutil.copyfile(bundle / 'files' / r['path'], src)
            if md5(src) != r['new_md5']:
                raise SystemExit('replace readback differs: ' + r['path'])
        else:
            src.unlink()   # the byte-identical copy is already in the backup dir
    (backup / 'applied.json').write_text(json.dumps(dict(world=str(world), bundle=str(bundle), rows=man['rows'], bodies=bodies), indent=1), 'utf8')
    print(json.dumps(dict(applied=len(man['rows']), bodies=bodies)))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest='cmd', required=True)
    q = s.add_parser('prepare')
    q.add_argument('formal'); q.add_argument('donor'); q.add_argument('bundle')
    q = s.add_parser('apply')
    q.add_argument('world'); q.add_argument('bundle'); q.add_argument('backup'); q.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    prepare(a) if a.cmd == 'prepare' else apply(a)
