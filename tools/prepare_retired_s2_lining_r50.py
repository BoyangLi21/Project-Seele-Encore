"""Retire the full R02 S2 tunnel lining while preserving measured live bearing.

Candidate-only. The low concrete is an old Y105 tunnel, not a bridge chord.
Source-declared lining cells are the entire positive mask; later column cores,
natural caves, actor data, traffic and block-entity NBT are never reset.
"""
from pathlib import Path
from collections import Counter, deque, defaultdict
import argparse
import gzip
import hashlib
import json
import math

from prepare_facilities_r48 import Author
from prepare_battle_civil_r50 import complete_recipe

ROOT = Path(__file__).resolve().parents[1]
GRAY = 'minecraft:light_gray_concrete'
NATURAL = {'minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block'}
CONSTRUCTED = {GRAY, 'projectseele:nerv_machine_edge', 'minecraft:gravel'}
NAME = 'S2_whole_retired_105_tunnel_lining'


def physical_path(states, start, targets):
    queue = deque([start])
    seen = {start}
    previous = {}
    found = None
    while queue:
        p = queue.popleft()
        if p in targets:
            found = p
            break
        for d in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]:
            q = tuple(p[k]+d[k] for k in range(3))
            if q[1] < 113 or q in seen or states.get(q, '').split('[')[0] not in CONSTRUCTED:
                continue
            seen.add(q)
            previous[q] = p
            queue.append(q)
    assert found is not None, ('Live column has no actual current formation connection', start)
    path = []
    while True:
        path.append([*found, states[found]])
        if found == start:
            break
        found = previous[found]
    return list(reversed(path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--world', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=ROOT/'artifacts/rebuild_r49/surface_r50/retired_routes_r50/S2_tunnel_lining_candidate_r50')
    args = ap.parse_args()
    a = Author(args.world.resolve(), args.out.resolve())
    a.out.mkdir(parents=True, exist_ok=True)
    source = ROOT/'artifacts/world_quality_r02/estate_track_envelopes/ops.json.gz'
    ops = json.load(gzip.open(source, 'rt', encoding='utf8'))
    original = [r for r in ops if r['owner'] == 'rail/S2_city_street/tunnel']
    assert len(original) == 160
    cells = set()
    for r in original:
        assert r['state'] == GRAY
        b = r['box']
        assert (b[1], b[2], b[4], b[5]) == (102, 744, 112, 752)
        cells.update((x,y,z) for x in range(b[0],b[3]+1)
                     for y in range(102,113) for z in range(744,753))
    assert len(cells) == 327*11*9
    lining_cells = set(cells)
    assert min(x for x,y,z in cells) == -2292 and max(x for x,y,z in cells) == -1966
    pier_source = ROOT/'artifacts/world_rebuild_r20/transit/civil/viaduct_stations_and_streets/ops.json.gz'
    pier_ops = [r for r in json.load(gzip.open(pier_source,'rt',encoding='utf8'))
        if r['owner']=='r20/viaduct_pier' and r['box'][0]<=-1966 and r['box'][3]>=-2292
        and r['box'][2]<=752 and r['box'][5]>=744]
    assert len(pier_ops) == 11
    for r in pier_ops:
        b = r['box']
        cells.update((x,y,z) for x in range(b[0],b[3]+1)
                     for y in range(b[1],b[4]+1) for z in range(b[2],b[5]+1))
    a.read((-2304,48,736),(-1954,145,760))
    assert not any(p in a.t for p in cells), 'Original device NBT overlaps lining; explicit review required'
    native = json.loads((a.world/'native_transit_r22.json').read_text('utf8'))
    targets = set()
    formation = defaultdict(set)
    for r in native['curves']:
        if r['mode'] != 'TRAIN':
            continue
        for px,py,pz in r['points']:
            x,y,z = map(math.floor,(px,py,pz))
            if not (-2304 <= x <= -1954 and 733 <= z <= 763):
                continue
            for dx in range(-3,4):
                for dz in range(-3,4):
                    X,Z = x+dx,z+dz
                    formation[X,Z].add(y-3)
                    for dy in (-3,-2,-1):
                        p = X,y+dy,Z
                        if a.s.get(p,'').split('[')[0] in CONSTRUCTED:
                            targets.add(p)
    # Preserve the whole three-wide later structural interface. Seven actual
    # column cores continue outside the retired source volume and connect by
    # a real upper transverse frame to the current native formation.
    retained_xz = {(x,z) for x in range(-2099,-2096) for z in range(747,750)}
    proofs = []
    for x,z in sorted(retained_xz):
        if a.s[x,101,z] == GRAY and a.s[x,113,z] == GRAY:
            proofs.append(dict(column=[x,z], actual_path=physical_path(a.s,(x,113,z),targets)))
    assert len(proofs) == 7
    bearing = []
    for (x,z),ys in formation.items():
        if (x,112,z) not in cells or a.s[x,112,z] != GRAY:
            continue
        floor = min(ys)
        solid = NATURAL | CONSTRUCTED
        if all(a.s.get((x,y,z),'').split('[')[0] in solid for y in range(113,floor+1)):
            bearing.append([x,z,floor])
    assert bearing == [[-2292,752,116]], bearing
    desired = {}
    kinds = Counter()
    gray_columns = defaultdict(list)
    for p in cells:
        if a.s[p] == GRAY and (p[0],p[2]) not in retained_xz:
            gray_columns[p[0],p[2]].append(p[1])
    embedded_positions = set()
    for (x,z),ys in gray_columns.items():
        ys.sort()
        runs = []
        for y in ys:
            if runs and runs[-1][-1]+1 == y:
                runs[-1].append(y)
            else:
                runs.append([y])
        for run in runs:
            # Preserve the original solid geometry of an embedded roof/wall or
            # pier cap, including a roof over an already measured old cavity.
            # Natural material immediately above the whole actual gray run is
            # evidence of cover, not an inferred room or terrain datum.
            if a.s[x,run[-1]+1,z].split('[')[0] in NATURAL:
                embedded_positions.update((x,y,z) for y in run)
    assert (-2292,112,752) in embedded_positions
    for p in sorted(cells):
        x,y,z = p
        before = a.s[p]
        after = before
        reason = 'Full old R02 S2 Y105 tunnel source; actual unrelated natural cells and retained later structure are preserved'
        if before == GRAY and (x,z) not in retained_xz:
            if p in embedded_positions:
                cap = min((Y for Y in range(113,146) if a.s[x,Y,z].startswith('minecraft:grass_block')), default=1000)
                after = 'minecraft:dirt' if cap-3 <= y < cap else 'minecraft:stone'
                reason = 'Restore embedded retired lining to actual enclosing natural soil; retain full current western formation bearing'
                kinds['embedded_concrete_to_natural_soil'] += 1
            else:
                after = 'minecraft:air'
                reason = 'Complete retirement of obsolete R02 S2 Y105 exposed tunnel lining; original route is no longer current native railway'
                kinds['exposed_retired_lining_to_air'] += 1
        elif before == GRAY:
            kinds['actual_later_live_column_concrete_retained'] += 1
        desired[p] = after, reason, None
    # A new source must not erase its actual transverse column/formation path.
    for proof in proofs:
        assert all(tuple(row[:3]) not in desired for row in proof['actual_path'])
    objects = dict(source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        source_owner='rail/S2_city_street/tunnel', original_source_ops=160,
        full_source_bounds=[[-2292,102,744],[-1966,112,752]],
        original_track_y=105, old_route_replaced_by_current_curved_R1=True,
        source_kind='old tunnel lining; not a current bridge lower chord',
        counts=dict(kinds), retained_later_interface=[[-2099,102,747],[-2097,112,749]],
        seven_actual_current_column_paths=proofs, current_formation_bearing=bearing,
        enclosing_natural_columns=len({(x,z)for x,y,z in embedded_positions}),
        original_R20_piers_source=str(pier_source),
        original_R20_piers_source_sha256=hashlib.sha256(pier_source.read_bytes()).hexdigest(),
        original_R20_pier_complete_boxes=[r['box'] for r in pier_ops],
        original_R20_piers_11_mostly_already_absent=True,
        remaining_old_pier_cap_cells_outside_lining=sum(a.s[p]==GRAY for p in cells-lining_cells),
        current_personnel_purpose_catalogue_intersections=[],
        no_proximity_as_structural_evidence=True,
        natural_cave_and_original_non_lining_states_preserved=True,
        all_actor_inventory_traffic_and_progress_files_untouched=True)
    a.emit(NAME, desired, objects)
    a.full_desired = desired
    complete_recipe(a)
    contract_path = a.out/NAME/'contract.json'
    contract = json.loads(contract_path.read_text('utf8'))
    contract.update(schema='projectseele.r50.retired-s2-source-candidate.v1',
                    authorization='Root-relayed user full surface reconstruction, remaining item40 S2')
    contract_path.write_text(json.dumps(contract,ensure_ascii=False,indent=2),'utf8')
    (a.out/'manifest.json').write_text(json.dumps(dict(schema=50,source_world=str(a.world),
        components=[contract],changed_cells=len(a.all),complete_generation_cells=len(desired),
        world_written=False,native_verified=False,visual_verified=False,
        full_state_NBT_inverse_and_mask=True,metadata_operations=[]),ensure_ascii=False,indent=2),'utf8')
    (a.out/'metadata_patch.json').write_text(json.dumps(dict(schema=50,operations=[],world_written=False),indent=2),'utf8')
    print(dict(kinds), len(a.all), 'changed;', len(desired),'complete source cells; no world writes',flush=True)


if __name__ == '__main__':
    main()
