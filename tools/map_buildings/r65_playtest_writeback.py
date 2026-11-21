"""R65 write-back of the building fixes Codex made in the R64 playtest copy, as clean lists against the formal world.

  python r65_playtest_writeback.py <playtest material dir> <out dir>

Material (D:/eva-R64-playtest-fix): field-review/door_rows.json (85 personnel door frames), shaft_rows.json (black
shell of the three joined launch silos), local-structures/{mount,city,airport}_rows.json. The door frames sit in the
city's rising buildings, so Codex appended their cells to each building's cargo recipe; the silo shell was appended to
the surface recipes of its chunks (city_rigid_generation_r45). In the playtest the recipes also picked up play state
(RelocationSnapshotJourney moves with the city), which must not come back.

Every row must still hold its before state in BUILDINGS_WORLD, carry no block entity the list does not replace on
purpose, and pass the protection guards. Each recipe is rebuilt from the formal world's own file plus exactly the
entries Codex appended; any other difference between Codex's original and patched recipe stops the run. Writes per
batch: rows.json, data/<world-relative recipe files>, patch.json (row and file md5 sums, before and after).
"""
import hashlib, json, shutil, sys
from collections import Counter
from pathlib import Path
import nbtlib
from mca import REGION, World, WORLD
from float_fix import guards   # [city lift, lift shafts, launch]

RECIPES = Path('dimensions/projectseele/geofront/data/city_rigid_generation_r45')
BATCHES = {
    'doors': (['field-review/door_rows.json'], 'cargo'),
    'shaft': (['field-review/shaft_rows.json'], 'surface'),
    'local': (['local-structures/mount_rows.json', 'local-structures/city_rows.json', 'local-structures/airport_rows.json'], None),
}
# The door frames are part of the raised towers themselves (their cargo recipes carry them), so that batch is written
# with --allow-city-lift. The leftover road near (185,84,132) lies over two Original96 towers that have no body raised
# or lowered and no hatch cover (their whole footprint is road and grass), so the local batch is too, but only those
# two volumes may be touched. Both batches are still checked against the lift and launch guards.
CITY_LIFT_OK = {'doors': None, 'local': {'original96/57', 'original96/58'}}
# The silo shell lies inside the broad 32-block launch route reservations; the R65 candidate writer's --bank2-exterior
# (784296a0, plan_r64_silo_exterior.on_facade) admits it only as air to black concrete on the casing's outside faces,
# so here that batch is checked against the city and lift guards and the launch check is left to that writer.
LAUNCH_BY_WRITER = {'shaft'}
PLAY_STATE = {'RelocationSnapshotJourney'}
# Codex fitted the door frames with the city raised: their rows sit at street level (y 81-83), where a raised body's
# entrance is. The cargo recipes carry them with the building, so with the city lowered they belong at the same place
# in the lowered body, RetractedBaseY + 1 - 81 lower (in game: raised at 81, lowered at low + 1, both rounds).
# Written at street level into a lowered city they would stand on the closed hatches until the first raise.
RAISED_FLOOR = 81


def towers_of(world):
    from map_pipeline.city_protection import unpack
    data = nbtlib.load(next(Path(world, 'dimensions/projectseele/geofront/data').glob('projectseele_city_rigid_topology_r45_*.dat')))['data']
    out = []
    for label, lst in (('towers', data['Towers']), ('original96', data['LowriseAddonR48']['Original96Towers'])):
        for i, t in enumerate(lst):
            x, y, z = unpack(int(t['Centre'])); b = t['Footprint']
            out.append(dict(name=f'{label}/{i}', x0=x + int(b['MinX']), x1=x + int(b['MaxX']), z0=z + int(b['MinZ']), z1=z + int(b['MaxZ']),
                            low=int(t['RetractedBaseY']), height=int(t['Height'])))
    return out


def city_lowered(w, towers):
    """True when every tower body is down: solid blocks in the lowered volume, nothing in the raised one."""
    down = up = 0
    for t in towers:
        cx, cz = (t['x0'] + t['x1']) // 2, (t['z0'] + t['z1']) // 2
        down += any(not (w.get(cx + dx, t['low'] + 5, cz + dz) or 'air').endswith('air') for dx in (-3, 0, 3) for dz in (-3, 0, 3))
        up += any(not (w.get(cx + dx, RAISED_FLOOR + 5, cz + dz) or 'air').endswith('air') for dx in (-3, 0, 3) for dz in (-3, 0, 3))
    return down, up


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def appended(orig, new, what):
    if len(new) < len(orig) or list(new[:len(orig)]) != list(orig):
        raise SystemExit(f'{what}: not a pure append')
    return list(new[len(orig):])


def cargo(formal, orig, patched, name):
    """Formal cargo recipe plus the Cargo entries Codex appended to each building."""
    f, o, p = (nbtlib.load(x) for x in (formal, orig, patched))
    out, added = f, 0
    fb, ob, pb = f['data']['Buildings'], o['data']['Buildings'], p['data']['Buildings']
    if not (len(fb) == len(ob) == len(pb)):
        raise SystemExit(f'{name}: building count differs')
    for i, (b_f, b_o, b_p) in enumerate(zip(fb, ob, pb)):
        for k in set(b_o) | set(b_p):
            if k == 'Cargo' or k in PLAY_STATE:
                continue
            if b_o.get(k) != b_p.get(k):
                raise SystemExit(f'{name}[{i}].{k} changed in the playtest')
        extra = appended(b_o['Cargo'], b_p['Cargo'], f'{name}[{i}].Cargo')
        b_f['Cargo'].extend(extra)
        added += len(extra)
    for k in set(o['data']) | set(p['data']):
        if k != 'Buildings' and o['data'].get(k) != p['data'].get(k):
            raise SystemExit(f'{name}: data.{k} changed')
    return out, added


def surface(formal, orig, patched, name):
    f, o, p = (nbtlib.load(x) for x in (formal, orig, patched))
    for k in set(o) | set(p):
        if k in ('Spans', 'Palette'):
            continue
        if o.get(k) != p.get(k):
            raise SystemExit(f'{name}: {k} changed')
    pal = appended(o['Palette'], p['Palette'], f'{name}.Palette')
    spans = appended(o['Spans'], p['Spans'], f'{name}.Spans')
    f['Palette'].extend(pal)
    f['Spans'].extend(spans)
    return f, len(spans)


def main(material, out):
    material, out = Path(material), Path(out)
    w = World(REGION)
    gs = guards()
    summary = {}
    for batch, (lists, kind) in BATCHES.items():
        rows, seen = [], set()
        active = [g for i, g in enumerate(gs) if not (i == 0 and batch in CITY_LIFT_OK) and not (i == 2 and batch in LAUNCH_BY_WRITER)]
        city_hits = Counter()
        for name in lists:
            for r in json.loads((material / name).read_text('utf8')):
                x, y, z, before, after = r[:5]
                if (x, y, z) in seen:
                    raise SystemExit(f'{batch}: {x},{y},{z} listed twice')
                seen.add((x, y, z))
                cur = w.get(x, y, z)
                if cur != before:
                    raise SystemExit(f'{batch}: {x},{y},{z} is {cur}, list expects {before}')
                be = w.block_entity(x, y, z)
                if be and be != 'trafficcraft:colored_block_entity':
                    raise SystemExit(f'{batch}: {x},{y},{z} carries {be}')
                for g in active:
                    g.assert_positions([(x, y, z)])
                if batch in CITY_LIFT_OK:
                    try:
                        gs[0].assert_positions([(x, y, z)])
                    except ValueError as hit:
                        volume = hit.args[0][1]
                        tower = volume.split()[-1]
                        allowed = CITY_LIFT_OK[batch]
                        if allowed is not None and tower not in allowed:
                            raise SystemExit(f'{batch}: {x},{y},{z} inside {volume}')
                        city_hits[volume] += 1
                rows.append(r)
        if batch == 'doors':
            towers = towers_of(WORLD)
            down, up = city_lowered(w, towers)
            if up or down < len(towers) * 0.9:
                raise SystemExit(f'city not cleanly lowered (bodies down {down}, up {up} of {len(towers)}): plan the frames at street level instead')
            shifted = []
            for r in rows:
                x, y, z = r[:3]
                t = next(t for t in towers if t['x0'] - 1 <= x <= t['x1'] + 1 and t['z0'] - 1 <= z <= t['z1'] + 1)
                y2 = y + t['low'] + 1 - RAISED_FLOOR
                cur = w.get(x, y2, z)
                if cur != r[3]:
                    raise SystemExit(f'doors: lowered cell {x},{y2},{z} is {cur}, expected {r[3]}')
                if w.block_entity(x, y2, z):
                    raise SystemExit(f'doors: lowered cell {x},{y2},{z} carries a block entity')
                for g in active:
                    g.assert_positions([(x, y2, z)])
                shifted.append([x, y2, z, *r[3:]])
            rows = shifted
        dest = out / batch
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        (dest / 'rows.json').write_text(json.dumps(rows), 'utf8')
        files, added = [], 0
        if kind:
            patched_dir = material / 'field-review/recipes' / RECIPES / kind
            names = sorted(p.name for p in patched_dir.glob('*.dat'))
            # the surface recipes Codex touched are exactly the shaft's chunks; cargo ones are the door buildings
            for n in names:
                rel = RECIPES / kind / n
                formal_file = Path(WORLD) / rel
                orig = material / 'field-review/original-recipes' / rel
                if md5(formal_file) != md5(orig):
                    raise SystemExit(f'{rel}: formal recipe is not the one Codex patched')
                build = cargo if kind == 'cargo' else surface
                tag, n_added = build(formal_file, orig, material / 'field-review/recipes' / rel, str(rel))
                target = dest / 'data' / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                tag.save(target)
                added += n_added
                files.append(dict(file=str(rel).replace('\\', '/'), before_md5=md5(formal_file), after_md5=md5(target), added=n_added))
        kinds = Counter(r[4].split('[')[0] for r in rows)
        paint = sum(1 for r in rows if len(r) > 5)
        replaced_paint = sum(1 for r in rows if w.block_entity(*r[:3]))
        info = dict(rows=len(rows), rows_md5=md5(dest / 'rows.json'), sources=lists, recipe_files=len(files), recipe_entries_added=added,
                    rows_with_paint=paint, cells_with_paint_now=replaced_paint, city_lift_volumes_touched=len(city_hits),
                    city_lift_cells=sum(city_hits.values()), after_kinds=dict(kinds.most_common(8)),
                    writer_flags=(['--allow-city-lift'] if batch in CITY_LIFT_OK else []) + (['--bank2-exterior'] if batch in LAUNCH_BY_WRITER else []) + (['--allow-block-entities'] if replaced_paint and not paint else []),
                    files=files)
        (dest / 'patch.json').write_text(json.dumps(info, indent=1), 'utf8')
        summary[batch] = {k: v for k, v in info.items() if k != 'files'}
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
