"""Finish complete registered active R23 boarding slabs with equal native shapes."""
from pathlib import Path
import json, argparse
import regional_voxels as v
from query_blocks import iter_block_entities
from measure_world_r40 import MeasuredWorld
ROOT = v.ROOT
WORLD = ROOT/'run/saves/SEELE_R24_TV_REVIEW'
OUT = ROOT/'artifacts/facility_r24/materials'

def main(apply=False, world=WORLD, out=OUT, native_path=None):
    world, out = Path(world), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    v.WORLD, v.OUT = world, out
    p = v.Painter()
    native_path = Path(native_path) if native_path is not None else ROOT/'artifacts/rebuild_r45/transport_controls_agent/current_native_snapshot.json'
    native = json.loads(native_path.read_text(encoding='utf8'))
    platforms = {int(q['id']): q for q in native['platforms']}
    active = {int(q['platformId']) for r in native['routes'] for q in r['routePlatformData']}
    shapes = json.loads((world/'native_collision_shapes.json').read_text(encoding='utf8'))
    before, after = 'minecraft:smooth_stone', 'projectseele:period_station_floor'
    if shapes.get(before) != [[0,0,0,1,1,1]] or shapes.get(after) != shapes[before]:
        raise RuntimeError('Complete native floor shape equivalence is required')
    records = json.loads((ROOT/'artifacts/access_r22/transit/civil/station_contract.json').read_text(encoding='utf8'))['stations']
    changed, preserved = [], []
    for station in records:
        ids = [int(pid) for pid in station['platform_ids'] if int(pid) in active]
        if not ids:
            continue
        x,y,z = station['center']
        h, horizontal = station['half'], station['horizontal']
        axis, origin = ('z',z) if horizontal else ('x',x)
        offset = max(abs((platforms[pid]['position1'][axis]+platforms[pid]['position2'][axis])/2-origin) for pid in ids)
        edge = round(offset)+2
        mask = [(x+u,y,z+side*c) if horizontal else (x+side*c,y,z+u)
                for u in range(-h,h+1) for side in (-1,1) for c in range(edge,18)]
        w = MeasuredWorld(world)
        for q in mask:
            w.around(q,1)
        w.load()
        if not all(s == 'full' for s in w.status.values()):
            raise RuntimeError(('Incomplete registered station deck',station['station']))
        tags = {}
        for (cx,cz), sections in w.selected.items():
            tags.update(iter_block_entities(world,v.DIM,(cx*16,min(sections)*16,cz*16),(cx*16+15,max(sections)*16+15,cz*16+15)))
        count = 0
        for q in mask:
            state = w.block(q)
            if state == before and q not in tags:
                p.match((*q,*q),before,after,'r45/active_station/complete_original_boarding_deck_finish')
                count += 1
            else:
                preserved.append(dict(pos=q,state=state,full_nbt=tags[q].snbt() if q in tags else None))
        changed.append(dict(station=station['station'],line=station['line'],height=y,cells=count,complete_original_R23_boarding_mask=mask))
    p.meta.update(surfaces=changed, protected_devices_and_other_surfaces=preserved,
                  collision_unchanged_full_cube=True, original_ground_roads_track_ballast_and_tactile_untouched=True)
    p.save_plan('period_station_floor_finish')
    if apply:
        p.apply('period_station_floor_finish')
    (out/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8')
    print('New original boarding-deck floor material cells',sum(s['cells'] for s in changed))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply',action='store_true')
    ap.add_argument('--world',type=Path,default=WORLD)
    ap.add_argument('--out',type=Path,default=OUT)
    ap.add_argument('--native-snapshot',type=Path)
    a = ap.parse_args()
    main(a.apply,a.world,a.out,a.native_snapshot)
