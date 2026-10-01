"""Whole public datum design against actual streets and actual entrance ports.

This emits a private design field, never a world patch. Building floors remain
fixed; raised foundations and gardens require a separate complete construction
plan. It is not permission to cut an existing building or transport structure.
"""
from pathlib import Path
import argparse
import hashlib
import heapq
import json


def envelope(nodes, seeds):
    distance = dict(seeds)
    queue = [(height, q) for q, height in seeds.items()]
    heapq.heapify(queue)
    while queue:
        height, (x, z) = heapq.heappop(queue)
        if distance[x, z] != height:
            continue
        for dx, dz in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            q = x + dx, z + dz
            if q in nodes and height + 1 < distance.get(q, 10**9):
                distance[q] = height + 1
                heapq.heappush(queue, (height + 1, q))
    return distance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('plan', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    assert not args.output.exists()
    args.output.mkdir(parents=True)
    district = json.loads((args.plan / 'new_district.json').read_text('utf8'))
    parcel = json.loads((args.plan / 'parcel_components.json').read_text('utf8'))
    road = json.loads((args.plan / 'road_authority.json').read_text('utf8'))['columns']
    court = {tuple(r['pos']): r for r in parcel['full_court_columns']}
    seeds = {tuple(r['pos']): round(r['native_feet'] * 2) for r in road}
    original = dict(seeds)
    original.update({q: round(r['native_feet'] * 2) for q, r in court.items()})
    nodes = set(original)
    fixed_ports = []
    for b in district['buildings']:
        x, y, z = b['door']
        bx, bz, bX, bZ = b['bounds']
        facing = b.get('facing') or ('north' if z == bz else 'south' if z == bZ else 'west' if x == bx else 'east')
        dx, dz = {'north': (0, -1), 'south': (0, 1), 'west': (-1, 0), 'east': (1, 0)}[facing]
        for depth in range(1, 4):
            for side in [-1, 0, 1]:
                q = x + dx * depth - dz * side, z + dz * depth + dx * side
                if q not in court:
                    continue
                value = round(y * 2)
                assert q not in seeds or seeds[q] == value, ('Entrance/street datum conflict', b['id'], q)
                seeds[q] = value
                fixed_ports.append(dict(pos=list(q), feet=y, owner=b['id']))
    upper = envelope(nodes, seeds)
    negative = envelope(nodes, {q: -h for q, h in seeds.items()})
    lower = {q: -h for q, h in negative.items()}
    infeasible = [dict(pos=list(q), lower=lower.get(q, 10**9)/2,
                       upper=upper.get(q, -10**9)/2) for q in nodes
                  if q not in upper or q not in lower or lower[q] > upper[q]]
    if infeasible:
        (args.output / 'infeasible.json').write_text(json.dumps(infeasible, indent=2), 'utf8')
        raise RuntimeError(f'{len(infeasible)} public columns need an explicit architectural transition; no result promoted')
    initial = {q: max(lower[q], min(upper[q], value)) for q, value in original.items()}
    solved = envelope(nodes, initial)
    assert all(solved[q] == height for q, height in seeds.items()), 'Actual entrance or street moved'
    assert all(lower[q] <= solved[q] <= upper[q] for q in nodes)
    edges = sum(1 for x, z in nodes for dx, dz in [(1, 0), (0, 1)] if (x + dx, z + dz) in nodes)
    assert all(abs(solved[x, z] - solved[x+dx, z+dz]) <= 1
               for x, z in nodes for dx, dz in [(1, 0), (0, 1)] if (x+dx, z+dz) in nodes)
    changes = [dict(pos=list(q), before_feet=original[q]/2, proposed_feet=solved[q]/2,
                    owner=court[q]['owner'], purpose=court[q].get('purpose'))
               for q in court if original[q] != solved[q]]
    result = dict(source=str(args.plan.resolve()), source_parcel_sha256=hashlib.sha256((args.plan/'parcel_components.json').read_bytes()).hexdigest(),
                  half_metre_constraint_edges=edges, fixed_street_columns=len(road), fixed_entrance_ports=fixed_ports,
                  changed_public_columns=changes, solved_columns=[dict(pos=list(q), feet=h/2) for q, h in sorted(solved.items())],
                  all_declared_cross_component_steps_at_most_half_metre=True,
                  building_floors_unchanged=True, world_written=False, construction_ready=False,
                  pending=['Full exposed building foundations and drainage', 'Garden and retaining interfaces including actual wetland culverts',
                           'Exact whole-state and full-NBT patch/inverse', 'Complete natural headroom/collision and actual imagery'])
    (args.output/'public_datum_design.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf8')
    print('Whole public datum field', len(nodes), 'columns;', len(changes), 'regraded; all actual street/entrance datums fixed; PRIVATE DESIGN ONLY', flush=True)


if __name__ == '__main__':
    main()
