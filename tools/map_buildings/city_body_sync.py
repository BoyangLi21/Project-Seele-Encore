"""Bring the tower bodies kept in a world's city data in line with the bodies standing in its region files.

Chunk regeneration (CityRigidGenerationR45) rebuilds each tower from the Cells of the current committed journey's journal
(or, in the short untouched-preparation window, the previous one's), and always opens recipe cargo/<i>.dat. After towers
are restyled in the region files those copies still hold the older bodies. No code changes: data only.

  audit <world>                                  which towers' journal/recipe bodies differ from the world
  prepare <world> <donor world> <bundle dir> [--skip 93,94,95]
      The donor is a copy of the same world (same WorldUUID) that made two lift trips in the same directions as the
      world's last two journeys, so its journals are what the lift itself writes for the current bodies.
  apply <world> <bundle dir> <backup dir> [--dry-run]
      md5 of every target, IDLE ledger with the bundle's journeys, every synced tower's world body equal to the bundle's
      journal Cells; backs up every file first; replaces only (nothing moved, nothing deleted).

Chunk recipes (city_rigid_generation_r45/chunks) also regenerate every tower's fixed anchors from their Static rows;
the lift refuses to start a tower whose anchors are not plain iron blocks. prepare also sets any anchor that is iron
in the world but not iron in its chunk recipe to iron there (only the Static row of that position changes).
"""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
import nbtlib

sys.path.insert(0, str(Path(__file__).parent))
from private_cleanup import DATA, REGION, md5, control, unpack, state, as_uuid

JOURNALS = DATA / 'city_rigid_journal_r45'
CARGO = DATA / 'city_rigid_generation_r45' / 'cargo'


def is_air(s):
    return s in ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')


def topology(world):
    files = sorted((Path(world) / DATA).glob('projectseele_city_rigid_topology_r45_*.dat'))
    if len(files) != 1:
        raise SystemExit('expected one city topology in ' + str(world))
    out = {}
    for i, t in enumerate(nbtlib.load(files[0])['data']['Towers']):
        f = t['Footprint']
        out[i] = dict(centre=unpack(t['Centre']), H=int(t['Height']), ret=int(t['RetractedBaseY']),
                      fp=(int(f['MinX']), int(f['MaxX']), int(f['MinZ']), int(f['MaxZ'])))
    return out


def body(w, spec, depth):
    """Non-air cells where chunk generation places tower cargo: topology centre, base by depth, footprint, H+4."""
    cx, cy, cz = spec['centre']
    base = cy if depth == 0 else spec['ret']
    x0, x1, z0, z1 = spec['fp']
    got = {}
    for y in range(spec['H'] + 4):
        for z in range(z0, z1 + 1):
            for x in range(x0, x1 + 1):
                s = w.get(cx + x, base + y, cz + z) or 'minecraft:air'
                if not is_air(s):
                    got[(x, y, z)] = s
    return got


def cells(lst):
    return {unpack(c['Pos']): state(c['State']) for c in lst if not is_air(str(c['State']['Name']))}


def wrong(a, b):
    return sum(1 for k in set(a) | set(b) if a.get(k) != b.get(k))


def towers(world):
    return sorted(int(p.stem) for p in (Path(world) / CARGO).glob('*.dat'))


def anchor_patches(world, w):
    """Chunk recipe files whose Static rows would regenerate a fixed anchor as something other than iron."""
    files = sorted((Path(world) / DATA).glob('projectseele_city_rigid_topology_r45_*.dat'))
    towers_ = nbtlib.load(files[0])['data']['Towers']
    by_chunk = {}
    for i, t in enumerate(towers_):
        for a in t['NegativeDomeAnchorMask']:
            p = unpack(a)
            if w.get(*p) != 'minecraft:iron_block':
                raise SystemExit(f'anchor {p} of tower {i} is not iron in the world')
            by_chunk.setdefault((p[0] >> 4, p[2] >> 4), {})[p] = i
    out = {}
    for (cx, cz), anchors in sorted(by_chunk.items()):
        rel = DATA / 'city_rigid_generation_r45' / 'chunks' / f'{cx}_{cz}.dat'
        if not (Path(world) / rel).is_file():
            raise SystemExit(f'no chunk recipe {rel} for anchors {sorted(anchors)[:3]}')
        tag = nbtlib.load(Path(world) / rel); pal = tag['Palette']; changed = []
        iron = next((k for k, e in enumerate(pal) if str(e['Name']) == 'minecraft:iron_block' and not e.get('Properties')), None)
        seen = set()
        for row in tag['Static']:
            p = unpack(row['Pos'])
            if p not in anchors:
                continue
            seen.add(p)
            name = str((pal[int(row['StateId'])] if 'StateId' in row else row['State'])['Name'])
            if name == 'minecraft:iron_block':
                continue
            if iron is None:
                pal.append(nbtlib.Compound({'Name': nbtlib.String('minecraft:iron_block')})); iron = len(pal) - 1
            row.pop('State', None); row['StateId'] = nbtlib.Int(iron); changed.append((p, name, anchors[p]))
        for p in sorted(set(anchors) - seen):
            if iron is None:
                pal.append(nbtlib.Compound({'Name': nbtlib.String('minecraft:iron_block')})); iron = len(pal) - 1
            tag['Static'].append(nbtlib.Compound({'Pos': nbtlib.Long(next(a for a in towers_[anchors[p]]['NegativeDomeAnchorMask'] if unpack(a) == p)),
                                                  'StateId': nbtlib.Int(iron)}))
            changed.append((p, 'missing', anchors[p]))
        if changed:
            out[rel] = (tag, changed)
    return out


def audit_world(world, only=None):
    from mca import World
    w = World(str(Path(world) / REGION)); c = control(world); topo = topology(world); out = {}
    for i in only or towers(world):
        cur = nbtlib.load(Path(world) / JOURNALS / c['current'][0] / f'{i}.dat')
        prev = nbtlib.load(Path(world) / JOURNALS / c['previous'][0] / f'{i}.dat')
        bld = nbtlib.load(Path(world) / CARGO / f'{i}.dat')['data']['Buildings'][0]
        snap = 'RelocationSnapshotJourney' in bld and as_uuid(bld['RelocationSnapshotJourney']) == c['current'][0]
        b = body(w, topo[i], c['depth'])
        out[i] = dict(world=len(b), current=wrong(cells(cur['Cells']), b), previous=wrong(cells(prev['Cells']), b),
                      recipe=wrong(cells(bld['Cargo']), b), regen_source='recipe' if snap else 'current journal')
    return out


def audit(a):
    res = audit_world(a.world)
    for i, r in res.items():
        if r['current'] or r['previous'] or r['recipe']:
            print(i, r)
    print(json.dumps(dict(towers=len(res), current_differs=[i for i, r in res.items() if r['current']],
                          previous_differs=[i for i, r in res.items() if r['previous']],
                          recipe_differs=[i for i, r in res.items() if r['recipe']])))


def prepare(a):
    world, donor, out = Path(a.world), Path(a.donor), Path(a.bundle)
    f, d = control(world), control(donor)
    if f['uuid'] != d['uuid']:
        raise SystemExit('donor is not a copy of this world')
    for k in ('current', 'previous'):
        if f[k][1:3] != d[k][1:3]:
            raise SystemExit(f'{k} journey directions differ: world {f[k][1:3]} donor {d[k][1:3]}')
    if out.exists():
        raise SystemExit('bundle dir exists: ' + str(out))
    skip = {int(v) for v in a.skip.split(',')} if a.skip else set()
    res = audit_world(world)
    sync = [i for i, r in res.items() if (r['current'] or r['previous'] or r['recipe']) and i not in skip]
    from mca import World
    w = World(str(world / REGION)); rows = []; checks = {}; topo = topology(world)

    def stage(rel, tag):
        dst = out / 'files' / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        tag.save(dst, gzipped=True)
        rows.append(dict(path=str(rel).replace('\\', '/'), action='replace', old_md5=md5(world / rel), new_md5=md5(dst)))
    for i in sync:
        donor_tags = {}
        for k in ('current', 'previous'):
            tag = nbtlib.load(donor / JOURNALS / d[k][0] / f'{i}.dat')
            if int(tag['Index']) != i or str(tag['WorldUUID']) != f['uuid']:
                raise SystemExit('unexpected donor journal ' + d[k][0] + f'/{i}.dat')
            old = nbtlib.load(world / JOURNALS / f[k][0] / f'{i}.dat')
            ground = [str(tag[o]) == str(old[o]) for o in ('Ops0', 'Ops3')]
            tag['Journey'] = nbtlib.IntArray([int(x) for x in f[k][3]])
            donor_tags[k] = tag
            checks.setdefault(i, {})[k + '_ground_ops_equal'] = all(ground)
        b = body(w, topo[i], f['depth'])
        for k in ('current', 'previous'):
            n = wrong(cells(donor_tags[k]['Cells']), b)
            checks[i][k + '_cells_wrong'] = n
            if n:
                raise SystemExit(f'donor {k} journal for tower {i} differs from the world body by {n} cells')
            stage(JOURNALS / f[k][0] / f'{i}.dat', donor_tags[k])
        cargo = nbtlib.load(world / CARGO / f'{i}.dat')
        new = []
        for c in donor_tags['current']['Cells']:
            c = nbtlib.Compound(c)
            if 'Data' in c:
                c['NBT'] = c.pop('Data')
            new.append(c)
        cargo['data']['Buildings'][0]['Cargo'] = nbtlib.List[nbtlib.Compound](new)
        stage(CARGO / f'{i}.dat', cargo)
    anchors = {}
    for rel, (tag, changed) in anchor_patches(world, w).items():
        stage(rel, tag)
        anchors[Path(rel).as_posix()] = [dict(pos=p, recipe_was=n, tower=i) for p, n, i in changed]
    manifest = dict(world_uuid=f['uuid'], current=f['current'][0], previous=f['previous'][0], towers=sync, anchors=anchors,
                    audit_before={str(i): res[i] for i in sync}, checks={str(i): v for i, v in checks.items()}, rows=rows)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1), 'utf8')
    print(json.dumps(dict(towers=sync, files=len(rows), anchor_files=len(anchors), anchors=sum(len(v) for v in anchors.values()), ground_ops_differ=[i for i, v in checks.items() if not all(
        v[k] for k in v if k.endswith('_equal'))], manifest_md5=md5(out / 'manifest.json'))))


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
        raise SystemExit(f'{len(bad)} targets differ from the bundle: ' + ', '.join(bad[:5]))
    from mca import World
    w = World(str(world / REGION)); bodies = {}; topo = topology(world)
    for i in man['towers']:
        tag = nbtlib.load(bundle / 'files' / JOURNALS / man['current'] / f'{i}.dat')
        bodies[i] = wrong(cells(tag['Cells']), body(w, topo[i], c['depth']))
    if any(bodies.values()):
        raise SystemExit('world bodies differ from the bundle: ' + json.dumps({k: v for k, v in bodies.items() if v}))
    clash = [r['path'] for r in man['rows'] if (backup / r['path']).exists()]
    if clash:
        raise SystemExit('backup already holds: ' + ', '.join(clash[:5]))
    if a.dry_run:
        print(json.dumps(dict(dry_run=True, towers=len(bodies), bodies_wrong=sum(bodies.values()), rows=len(man['rows']))))
        return
    for r in man['rows']:
        keep = backup / r['path']
        keep.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(world / r['path'], keep)
        if md5(keep) != r['old_md5']:
            raise SystemExit('backup copy differs: ' + r['path'])
    for r in man['rows']:
        dst = world / r['path']
        shutil.copyfile(bundle / 'files' / r['path'], dst)
        if md5(dst) != r['new_md5']:
            raise SystemExit('replace readback differs: ' + r['path'])
    (backup / 'applied.json').write_text(json.dumps(dict(world=str(world), bundle=str(bundle), rows=man['rows']), indent=1), 'utf8')
    print(json.dumps(dict(applied=len(man['rows']), towers=len(bodies), bodies_wrong=0)))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest='cmd', required=True)
    q = s.add_parser('audit'); q.add_argument('world')
    q = s.add_parser('prepare'); q.add_argument('world'); q.add_argument('donor'); q.add_argument('bundle'); q.add_argument('--skip', default='')
    q = s.add_parser('apply'); q.add_argument('world'); q.add_argument('bundle'); q.add_argument('backup'); q.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    {'audit': audit, 'prepare': prepare, 'apply': apply}[a.cmd](a)
