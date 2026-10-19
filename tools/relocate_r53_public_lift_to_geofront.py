"""Shorten the original public lift to GeoFront, preserving its actual car.

Authorized 2026-10-18. Retired geometry is the S20 shaft/pavilion and R40
street-access mask, not an inferred room. Exact old cells and device NBT are
recorded before installation. No player, EVA, task or railway state is replaced.
"""
from pathlib import Path
from collections import Counter
import argparse, copy, gzip, hashlib, io, json, msvcrt
import nbtlib
from query_blocks import read_box, iter_block_entities
from repair_r53_reported_landings import apply as apply_cells
from restore_r53_original_personnel_lifts import remap, tagpos
from rebind_r53_personnel_installation import rebind
from retire_r53_old_yashima_platform import packed
from apply_s20_approved_semantic_repairs import atomic_replace, parse_state

DIM = 'projectseele:geofront'
IDENTITY = 's20-surface-transit-v2'
WALL = 'projectseele:nerv_structural_panel'
FLOOR = 'projectseele:nerv_floor_panel'
AIR = 'minecraft:air'
TOP = -466

def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8')

def box(lo, hi):
    for y in range(lo[1], hi[1] + 1):
        for z in range(lo[2], hi[2] + 1):
            for x in range(lo[0], hi[0] + 1):
                yield x, y, z

def run(world, out, install=False):
    mp = world / 'personnel_lifts_r52.json'
    bp = world / 'ROOT_ASSEMBLY_BUNDLE.json'
    cp = world / 'dimensions/projectseele/geofront/data/capabilities.dat'
    manifest = json.loads(mp.read_text('utf8'))
    lift = next(v for v in manifest['lifts'] if v['id'] == IDENTITY)
    upper = next(v for v in lift['floors'] if v['cabin'][1] == 75)
    caps = nbtlib.load(cp)
    group = caps['data']['movingelevators:elevator_groups']['130;269']['group']
    assert not bool(group['isMoving']), 'Wait for the original car to stop'
    ys = list(map(int, group['floors']))
    assert ys == [-535, 75]
    available = [y for y, v in zip(ys, group['floorData']) if bool(v['isCageAvailable'])]
    assert available == [75], ('Preserve actual car; expected last measured stop', available)
    cells, tags, desired, after_tags, reasons = {}, {}, {}, {}, {}
    def read(lo, hi):
        cells.update(read_box(world, DIM, lo, hi))
        tags.update(iter_block_entities(world, DIM, lo, hi))
    read((110, -468, 265), (136, 90, 281))
    read((107, 71, 267), (235, 88, 309))
    read((125, -533, 271), (125, -533, 271))
    def put(p, state, reason, tag=None):
        assert p in cells, p
        desired[p], after_tags[p], reasons[p] = state, tag, reason
    capture = {p: (cells[p], copy.deepcopy(tags.get(p)))
               for p in box((127, 74, 270), (133, 79, 276))}
    assert any(str(t.get('id', '')) == 'movingelevators:button_tile'
               for _, t in capture.values() if t is not None)
    # The nine pyramid panels at X134/Y-433 are an isolated trim on the old
    # shaft (all neighbours outside it are air), not part of the pyramid.
    for p in box((126, -459, 269), (134, 80, 277)):
        y = p[1]
        # Current TV central roof is Y=24 (first cover cell 25), not the
        # retired R640 skyweave datum. An old datum leaves a hanging stone plug.
        armor = 'minecraft:black_concrete' if (p[0]-30)%64 == 0 or (p[2]-296)%64 == 0 else 'projectseele:nerv_structural_panel'
        state = AIR if y < 25 else armor if y < 28 else 'minecraft:stone'
        if y == 80:
            state = 'minecraft:smooth_stone'
        put(p, state, 'retire_tall_shaft_and_seal_sky_ceiling')
    # Full old S20 pavilion and the R40 approach, retired from the street
    # junction. The adjacent street surface is smooth stone at Y80.
    mask = {(x, z) for x in range(116, 137) for z in range(265, 282)}
    mask |= {(x, z) for x in range(110, 126) for z in range(269, 278)}
    mask |= {(x, z) for x in range(110, 120) for z in range(274, 288)}
    mask |= {(x, z) for x in range(110, 233) for z in range(281, 288)}
    mask |= {(x, z) for x in range(220, 233) for z in range(282, 309)}
    for x, z in mask:
        for y in range(73, 81):
            put((x, y, z), 'minecraft:smooth_stone' if y == 80 else 'minecraft:stone', 'retire_old_street_access_from_junction')
        top = 85 if x >= 220 and z >= 289 else 84 if x < 120 and z < 280 else 80
        for y in range(81, top + 1):
            put((x, y, z), AIR, 'remove_old_entrance_canopy')
    # The low GeoFront arrival pavilion has an open west entrance, the same
    # north controller and a continuous landing outside the door sweep.
    for p in box((119, -467, 269), (134, -460, 277)):
        x, y, z = p
        state = FLOOR if y == -467 else WALL if y == -460 or z in (269, 277) or x == 134 else AIR
        if x == 126 and y > -467:
            state = WALL
        put(p, state, 'geofront_arrival_pavilion')
    for p in box((116, -467, 270), (118, -467, 276)):
        put(p, FLOOR, 'open_west_arrival_threshold')
    for x in (120, 123, 130):
        put((x, -460, 273), 'minecraft:sea_lantern', 'pavilion_recessed_lighting')
    def moved(value):
        if isinstance(value, dict):
            return {k: TOP if k == 'approach_y' else moved(v) for k, v in value.items()}
        if isinstance(value, list):
            if len(value) == 3 and all(isinstance(v, int) for v in value) and value[1] in (75, 76, 77):
                return [value[0], value[1] + TOP - 75, value[2]]
            return [moved(v) for v in value]
        return value
    new = moved(upper)
    new['label'] = 'GeoFront 地面 · 总部湖畔'
    lift['floors'][lift['floors'].index(upper)] = new
    refs = {tuple(upper['controller']): tuple(new['controller'])}
    for p, (state, tag) in capture.items():
        q = (p[0], p[1] + TOP - 75, p[2])
        put(q, state, 'same_original_car', None if tag is None else remap(tagpos(tag, q), refs))
    control = tuple(new['controller'])
    tag = tagpos(tags[tuple(upper['controller'])], control)
    tag['data']['name'] = nbtlib.String(new['label'])
    put(control, cells[tuple(upper['controller'])], 'relocated_original_controller', tag)
    for door in new['landing_doors']:
        put(tuple(door['pos']), door['closed_state'], 'native_landing_door')
    for call in new['calls']:
        put(tuple(call['position']), call['state'], 'reachable_native_call_button')
    def sign(p, lines, facing):
        face = nbtlib.Compound({'messages': nbtlib.List[nbtlib.String]([
            nbtlib.String(json.dumps({'text': line}, ensure_ascii=False)) for line in lines]),
            'color': nbtlib.String('white'), 'has_glowing_text': nbtlib.Byte(1)})
        tag = nbtlib.Compound({'id': nbtlib.String('minecraft:sign'),
            'front_text': face, 'back_text': copy.deepcopy(face), 'is_waxed': nbtlib.Byte(1)})
        put(p, f'minecraft:dark_oak_wall_sign[facing={facing},waterlogged=false]',
            'destination_wayfinding', tagpos(tag, p))
    sign((125, -464, 270), ['GeoFront 湖畔', '↓ 总部交通层', '换乘机库 / 指挥区', '呼梯按钮在下方'], 'west')
    sign((125, -533, 271), ['GeoFront 电梯 →', '↑ 地下世界地面', '总部湖畔入口', '沿现有走廊到达'], 'west')
    group['floors'] = nbtlib.IntArray([-535, TOP])
    group['floorData'][1]['name'] = nbtlib.String(new['label'])
    rows = []
    for p, state in desired.items():
        before = tags[p].snbt() if p in tags else None
        after = after_tags[p].snbt() if after_tags[p] is not None else None
        if cells[p] != state or before != after:
            rows.append(dict(pos=p, before=cells[p], after=state, before_nbt=before,
                             after_nbt=after, reason=reasons[p]))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'EXACT_DELTA.json.gz').write_bytes(gzip.compress(encoded(rows), mtime=0))
    (out / 'personnel_lifts_PROPOSAL.json').write_bytes(encoded(manifest))
    report = dict(world=str(world),cells=len(rows),reasons=dict(Counter(r['reason'] for r in rows)),
                  lift=IDENTITY,old_stops=ys,new_stops=[-535, TOP],same_car=True,installed=False)
    if install:
        before_bundle = bp.read_bytes()
        bundle = json.loads(before_bundle)
        bundle['personnel_lifts']['sha256'] = hashlib.sha256(encoded(manifest)).hexdigest()
        raw_bundle = encoded(bundle)
        runtime_path, runtime_raw, _ = rebind(world, before_bundle, raw_bundle)
        stream = io.BytesIO(); caps.write(stream)
        cap_raw = gzip.compress(stream.getvalue(), mtime=0)
        apply_cells(world, out)
        with (world / 'session.lock').open('r+b') as lock:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            for path, raw in ((cp, cap_raw), (mp, encoded(manifest)), (bp, raw_bundle), (runtime_path, runtime_raw)):
                atomic_replace(path, raw)
                assert path.read_bytes() == raw
            data = world / 'dimensions/projectseele/geofront/data'
            topology = nbtlib.load(next(data.glob('projectseele_city_rigid_topology_r45_*.dat')))['data']
            folder = data / str(topology['GenerationFolder']) / 'chunks'
            grouped = {}
            for row in rows:
                grouped.setdefault((row['pos'][0] // 16, row['pos'][2] // 16), []).append(row)
            count = 0
            for (cx, cz), batch in grouped.items():
                path = folder / f'{cx}_{cz}.dat'
                if not path.exists(): continue
                doc = nbtlib.load(path); bypos = {int(r['Pos']): r for r in doc['Static']}
                palette = doc['Palette']; ids = {r.snbt(): i for i, r in enumerate(palette)}; changed = False
                for row in batch:
                    old = bypos.get(packed(row['pos']))
                    if old is None: continue
                    state = parse_state(row['after']); key = state.snbt()
                    if key not in ids: ids[key] = len(palette); palette.append(state)
                    old['StateId'] = nbtlib.Int(ids[key]); old.pop('NBT', None)
                    count += 1; changed = True
                if changed: doc.save(path, gzipped=True)
            marker = world / 'surface_lift_access_r40.json'
            value = json.loads(marker.read_text('utf8'))
            value.update(retired_r53=True, replacement='GeoFront lakeside', new_stops=[-535, TOP], street_approach_removed=True)
            atomic_replace(marker, encoded(value))
            battlefield = world / 'battlefield_r21.json'
            value = json.loads(battlefield.read_text('utf8'))
            retired = {tuple(r['pos']) for r in rows if r['pos'][1] >= 73}
            value['cells'] = [r for r in value['cells'] if tuple(r[:3]) not in retired]
            atomic_replace(battlefield, encoded(value))
            report.update(installed=True, actual_readback=True, generator_cells=count)
    (out / ('COMPLETE.json' if install else 'PLAN.json')).write_bytes(encoded(report))
    print(json.dumps(report, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args(); run(a.world, a.output, a.apply)
