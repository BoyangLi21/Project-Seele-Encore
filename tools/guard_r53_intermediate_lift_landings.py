"""Freeze and preview six edge guards on two authored rear-lift call landings.

This tool never installs into the supplied world. Only the single explicit
preview copy is changed; installation and native visual review are separate.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import msvcrt
import shutil
from pathlib import Path

import nbtlib

from audit_r53_intermediate_floors import load
from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry
from query_blocks import read_box, iter_block_entities, dimension_dir
from repair_r53_reported_landings import apply, DIM, FLOOR

LO, HI = (3, -522, 249), (17, -507, 265)
LEVELS = (-516, -512)
NAV = ('nerv_routes_r24.json.gz', 'r53_personnel_walking_graph.json.gz',
       'nearest_lift_paths_r44.json.gz')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    text = json.dumps(value, ensure_ascii=False, indent=2)
    if p.suffix == '.gz':
        p.write_bytes(gzip.compress(text.encode('utf8'), mtime=0))
    else:
        p.write_text(text+'\n', 'utf8')


def freeze(world, output):
    frozen = output/'frozen'
    frozen.mkdir()
    files = {dimension_dir(world, DIM)/'region/r.0.0.mca'}
    files.update(world/n for n in NAV+('personnel_lifts_r52.json',
        'native_collision_shapes.json', 'level.dat', 'level.dat_old',
        '.projectseele_lift_sliding_doors_r01.json'))
    for folder in ('r52', 'playerdata', 'data', 'dimensions/projectseele/geofront/data'):
        files.update(p for p in (world/folder).glob('*') if p.is_file()
                     and 'DistantHorizons' not in p.name)
    entity_region = dimension_dir(world, DIM)/'entities/r.0.0.mca'
    if entity_region.exists():
        files.add(entity_region)
    with (world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        data = dimension_dir(world, DIM)/'data'
        headers = list(data.glob('projectseele_city_rigid_topology_r45_*.dat'))
        assert len(headers) == 1
        cache = data/str(nbtlib.load(headers[0])['data']['GenerationFolder'])/'chunks/0_16.dat'
        if cache.exists():
            files.add(cache)
            wanted = {(x,y,z) for y in LEVELS for x,z in ((6,258),(6,259),(7,259))}
            for entry in nbtlib.load(cache)['Static']:
                n = int(entry['Pos']); x=n>>38; y=n&4095; z=(n>>12)&67108863
                if y>=2048: y-=4096
                if z>=33554432: z-=67108864
                assert (x,y,z) not in wanted, 'Maintained-static ownership must be resolved first'
        hashes = {}
        for p in sorted(files):
            rel = p.relative_to(world)
            q = frozen/rel
            q.parent.mkdir(parents=True, exist_ok=True)
            before = sha(p)
            shutil.copy2(p, q)
            assert sha(q) == before == sha(p), p
            hashes[str(rel)] = before
    (frozen/'session.lock').write_bytes(b'\x00\x00\x00')
    write(output/'FREEZE.json', dict(source=str(world.resolve()), bounds=[LO,HI],
        copied_sha256=hashes, maintained_static_touched_cells=0,
        scope='One terrain region; exact local cells/NBT; current navigation, lift ownership and nearby progress files',
        source_world_written=False))
    return frozen, hashes


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    frozen, hashes = freeze(args.world, args.output)
    cells = read_box(frozen, DIM, LO, HI)
    tags = dict(iter_block_entities(frozen, DIM, LO, HI))
    write(args.output/'LOCAL_BEFORE.json.gz', [dict(pos=p,state=s,nbt=tags[p].snbt() if p in tags else None)
          for p,s in sorted(cells.items())])
    report = load(args.audit)
    assert report['regression_passed']
    lift = next(r for r in load(frozen/'personnel_lifts_r52.json')['lifts']
                if r['id']=='s20-command-rear-x12-z253-v4')
    floors = [r for r in lift['floors'] if r['cabin'][1] in LEVELS]
    assert len(floors)==2 and all(r['exit']=='south' for r in floors)
    rows, expected = [], set()
    for floor in floors:
        y = floor['cabin'][1]
        assert floor['cabin']==[9,y,253] and floor['calls'][0]['position']==[6,y+1,258]
        assert cells[6,y+1,258]==floor['calls'][0]['state']
        assert all(cells[x,y,257]=='projectseele:lift_door_interlock_r53' for x in range(7,12))
        expected.update((((6,y,258),(5,y,258)),((6,y,259),(5,y,259)),
                         ((6,y,259),(6,y,260)),((7,y,259),(7,y,260))))
        for p,sides in (((6,y,258),('west',)),((6,y,259),('west','south')),((7,y,259),('south',))):
            assert cells[p]=='minecraft:air' and p not in tags
            assert cells[p[0],p[1]-1,p[2]]==FLOOR
            state='projectseele:nerv_edge_rail['+','.join(s+'='+str(s in sides).lower()
                  for s in ('east','north','south','west'))+']'
            rows.append(dict(pos=p,before=cells[p],after=state,before_nbt=None,after_nbt=None,
                reason='supported_outer_edge_of_existing_rear_lift_call_landing'))
    observed={(tuple(r['cell']),tuple(r['to'])) for level in report['levels']
              if level['feet_y'] in LEVELS for r in level['drops']
              if tuple(r['cell']) in {tuple(v['pos']) for v in rows}}
    assert observed==expected, 'Historical generic detector must show these exact failures'
    measured=MeasuredWorld(frozen); measured.box(LO,HI); measured.load()
    overrides={tuple(r['pos']):r['after'] for r in rows}
    class Candidate:
        world=frozen
        def block(self,q): return overrides.get(tuple(q),measured.block(q))
        def get(self,x,y,z): return self.block((x,y,z))
    before,after=ActualGeometry(measured),ActualGeometry(Candidate())
    def point(q): return(q[0]+.5,q[1],q[2]+.5)
    for a,b in expected:
        assert before.standing(point(a))=='STATIC_STANDING'
        assert before.standing(point(b))=='NO_FULL_DATUM_BEARING'
        assert before.clear(point(a),target=point(b))=='CLEAR'
        assert all(before.standing((b[0]+.5,b[1]-d,b[2]+.5))!='STATIC_STANDING'
                   for d in (.5,1,1.5,2,2.5,3))
        assert after.clear(point(a),target=point(b))=='ACTUAL_BODY_OBSTRUCTION'
    paths=[]
    for y in LEVELS:
        paths += [((x,y,z),(x+1,y,z)) for z in (258,259) for x in range(6,13)]
        paths += [((x,y,258),(x,y,259)) for x in range(6,14)]
    for a,b in paths:
        assert before.clear(point(a),target=point(b))==after.clear(point(a),target=point(b))=='CLEAR'
    nav=load(frozen/NAV[0]); walking=load(frozen/NAV[1]); nearest=load(frozen/NAV[2])
    assert nearest['graph_sha256']==sha(frozen/NAV[0])
    nodes=[tuple(r[:3]) for r in nav['nodes']]
    assert nodes==[tuple(r) for r in walking['nodes']]
    active={q for q,on in zip(nodes,nav['node_active']) if on}
    assert all(tuple(r['pos']) in active for r in rows)
    # Only transitions whose body sweep can intersect a new edge strip need
    # reevaluation. Unrelated stair and native doorway transitions are retained.
    near=lambda q:q[1] in LEVELS and 5<=q[0]<=8 and 257<=q[2]<=260
    local_nodes=[q for q in active if near(q)]
    changed_nodes=[q for q in local_nodes if before.standing(point(q))!=after.standing(point(q))]
    changed_edges=[]; checked_edges=0
    for i,j,*_ in walking['walking_edges']:
        a,b=nodes[i],nodes[j]
        if not(near(a) or near(b)) or a[1]!=b[1]: continue
        if max(abs(a[0]-b[0]),abs(a[2]-b[2]))>1: continue
        checked_edges+=1
        old=before.clear(point(a),target=point(b)); new=after.clear(point(a),target=point(b))
        if old!=new: changed_edges.append(dict(a=a,b=b,before=old,after=new))
    assert not changed_nodes and not changed_edges, (changed_nodes,changed_edges)
    assert not before.unknown and not after.unknown,(before.unknown,after.unknown)
    patch=args.output/'patch';patch.mkdir()
    inverse=[dict(r,before=r['after'],after=r['before'],before_nbt=None,after_nbt=None) for r in rows]
    for name,data in (('EXACT_DELTA.json.gz',rows),('INVERSE_DELTA.json.gz',inverse),
                      ('POSITIVE_EDIT_MASK.json.gz',[r['pos'] for r in rows])):
        write(patch/name,data)
    plan=dict(source=str(args.world.resolve()),frozen=str(frozen.resolve()),changed_cells=6,
        purpose='Existing main-command and rear-service lift call platforms, outside landing Z257 and cabin Z255 door planes',
        lift_id=lift['id'],floors=floors,audit_sha256=sha(args.audit),
        broad_audit_unknown_shapes_outside_local_proof=report['unknown_shapes'],
        before_unguarded_directions=8,after_unguarded_directions=0,
        retained_full_width_crossings=len(paths),navigation_nodes_checked=len(local_nodes),
        navigation_edges_checked=checked_edges,changed_navigation_nodes=changed_nodes,
        changed_navigation_edges=changed_edges,navigation_sha256={n:sha(frozen/n) for n in NAV},
        all_local_full_block_entity_nbt_preserved=True,door_button_controller_unchanged=True,
        maintained_static_touched_cells=0,source_world_written=False,native_visual_review_required=True)
    write(patch/'PLAN.json',plan)
    preview=args.output/'preview'
    shutil.copytree(frozen,preview)
    preview_receipt=args.output/'preview-receipt';preview_receipt.mkdir()
    shutil.copy2(patch/'EXACT_DELTA.json.gz',preview_receipt/'EXACT_DELTA.json.gz')
    apply(preview,preview_receipt)
    actual=read_box(preview,DIM,LO,HI)
    changed={p:(cells[p],s) for p,s in actual.items() if cells[p]!=s}
    assert changed=={tuple(r['pos']):(r['before'],r['after']) for r in rows}
    after_tags=dict(iter_block_entities(preview,DIM,LO,HI))
    assert {p:t.snbt() for p,t in tags.items()}=={p:t.snbt() for p,t in after_tags.items()}
    assert all(sha(preview/n)==sha(frozen/n) for n in NAV)
    assert all(sha(args.world/r)==h for r,h in hashes.items()),'Source changed; preview is not current'
    write(args.output/'PREVIEW_VERIFIED.json',dict(changed_cells=6,local_readback=True,
        unchanged_local_full_nbt_count=len(tags),source_frozen_hashes_unchanged=True,
        preview=str(preview.resolve()),patch=str(patch.resolve()),native_visual_review_required=True))
    print(json.dumps({k:plan[k] for k in ('changed_cells','before_unguarded_directions',
          'after_unguarded_directions','retained_full_width_crossings','navigation_edges_checked')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('world','audit','output'): p.add_argument('--'+name,type=Path,required=True)
    run(p.parse_args())
