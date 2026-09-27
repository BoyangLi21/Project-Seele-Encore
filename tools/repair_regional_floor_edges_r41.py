"""Repair floor-opening families using their original building/civil ownership.

Retired station rail cuts become continuous ground-level forecourts. Stairwell
edges receive boundary rails without occupying the three-wide flights. Only
measured cells with exact inverse deltas are written; active rail and lift
volumes remain protected.
"""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,json,math
import numpy as np
from scipy.spatial import cKDTree
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41'
WORLD=ROOT/'run/saves/SEELE_FIELD_R41_REVIEW';OUT=ART/'regional_edges'


def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    rows=json.loads((ART/'floor_components/classification.json').read_text('utf8'))
    stations=json.loads((ROOT/'artifacts/world_rebuild_r20/transit/civil/viaduct_stations_and_streets/places.json').read_text('utf8'))['stations']
    stations+=json.loads((ROOT/'artifacts/access_r22/transit/civil/station_contract.json').read_text('utf8'))['stations']
    # Underground platform trenches still carry trains. This restoration is
    # limited to the known surface forecourt slabs, below today's viaducts.
    slabs=set()
    for st in stations:
        x,_,z=st['center'];g=st['ground'];h=st['half']
        if g<0:continue
        for u in range(-h,h+1):
            for t in range(-15,16):slabs.add((x+u,g,z+t) if st['horizontal'] else (x+t,g,z+u))
    failures=json.loads((ART/'native_spatial/expanded_results.json').read_text('utf8'))
    explicit=[r['candidate'] for r in failures if r['status']=='floor_gap' and r['candidate']['pos'][1]!=-369]
    w=MeasuredWorld(WORLD)
    for x,y,z in slabs:w.box((x,y-2,z),(x,y+2,z))
    for row in rows+explicit:w.around(row['pos'],4)
    w.load()
    native=json.loads((WORLD/'native_transit_r28.json').read_text('utf8'))
    points=np.asarray([p for c in native['curves'] if c['mode']=='TRAIN' for p in c['points']],float);tree=cKDTree(points[:,[0,2]])
    def track(q):
        near=tree.query_ball_point([q[0]+.5,q[2]+.5],2.35)
        return any(points[i,1]-1.2<=q[1]<=points[i,1]+7 for i in near)
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();changes={};rails=defaultdict(set);decisions=[]
    shapes={v.canonical_state(s):b for s,b in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    def state(q):return changes.get(tuple(q),(w.block(q),''))[0]
    def boxes(q):
        s=state(q)
        return shapes.get(s,[] if s and s.partition('[')[0] in AIR|{'minecraft:light'} else [[0,0,0,1,1,1]])
    def support(q):return any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and .9<=b[4]<=1.01 for b in boxes(q))
    def put(q,after,why,allowed):
        q=tuple(q);before=w.block(q)
        assert before is not None and before.partition('[')[0] in allowed,(q,before,why)
        if before!=after:changes[q]=(after,why)
    for x,g,z in sorted(slabs):
        if track((x,g,z)):continue
        # Existing shafts, stair flights, doors and machinery are not voids
        # to fill. A missing paving cell has air above and no stair below.
        if state((x,g,z)) not in AIR or not all(state((x,Y,z)) in AIR or (state((x,Y,z)) or '').startswith('minecraft:light[') for Y in (g+1,g+2)):continue
        if any(any(t in (state((x,Y,z)) or '') for t in ('stairs[','escalator','ladder','movingelevators')) for Y in range(g-2,g+3)):continue
        for Y in (g-2,g-1,g):
            if state((x,Y,z)) in AIR:put((x,Y,z),'minecraft:smooth_stone' if Y==g else 'minecraft:light_gray_concrete','surface_forecourt/retired_track_cut',AIR)
    names={(1,0,0):'east',(-1,0,0):'west',(0,0,1):'south',(0,0,-1):'north'}
    confirmed={'authored_building_floor_edge','un_gantry_stair_floor_edge','underground_facility_floor_edge','port_yard_or_quay_edge','authored_station_ground_pad'}
    for row in rows+[{**r,'classification':'native_failed_edge'} for r in explicit]:
        q=tuple(row['pos']);x,y,z=q;dx,_,dz=row['normal'];n=(x+dx,y,z+dz);category=row['classification'];decision='retained_for_context_review'
        if support((n[0],y-1,n[2])):decision='continuous_floor_or_restored_forecourt'
        elif category in ('central_city_one_metre_shoulder','one_metre_external_grade_change'):
            target=(n[0],y-1,n[2]);below=(n[0],y-2,n[2]);s=state(below) or ''
            if state(target) in AIR and support(below) and s.partition('[')[0] in {'minecraft:grass_block','minecraft:dirt','minecraft:stone','minecraft:gravel','minecraft:deepslate_bricks','minecraft:gray_concrete','minecraft:light_gray_concrete'} and not track(target):
                put(target,'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]','public_shoulder/half_metre_grade',AIR);decision='half_metre_shoulder'
            else:decision='grade_boundary_preserved_pending_material_context'
        elif category in confirmed or category=='native_failed_edge':
            old=state(q)
            if track(q):decision='active_train_clearance_preserved'
            elif old in AIR or (old or '').startswith(('minecraft:light[','projectseele:nerv_edge_rail[')):
                if old.startswith('minecraft:light['):
                    above=(x,y+3,z)
                    if state(above) in AIR:put(above,old,'retain_floor_light_above_headroom',AIR)
                    else:decisions.append({**row,'decision':'occupied_light_relocation_held'});continue
                rails[q].update(k for k in names.values() if k+'=true' in (old or ''))
                rails[q].add(names[tuple(row['normal'])]);decision='edge_mounted_rail'
            else:decision='existing_fixture_preserved'
        elif category in {'native_platform_boarding_port','vertical_ladder_port','compact_lift_swept_volume','dynamic_city_building_owned_geometry','measured_descending_stair_axis'}:decision=category+'_preserved'
        decisions.append({**row,'decision':decision})
    for q,sides in rails.items():
        after='projectseele:nerv_edge_rail['+','.join(k+'='+str(k in sides).lower() for k in ('east','north','south','west'))+']'
        put(q,after,'supported_public_floor_perimeter',AIR|{'minecraft:light','projectseele:nerv_edge_rail'})
    by_chunk=defaultdict(list)
    for q in changes:by_chunk[q[0]//16,q[2]//16].append(q[1])
    for (cx,cz),ys in by_chunk.items():
        tags=dict(iter_block_entities(WORLD,v.DIM,(cx*16,min(ys),cz*16),(cx*16+15,max(ys),cz*16+15)))
        assert not set(tags)&set(changes),'Public floor patch intersects a block entity'
    for q,(after,why) in sorted(changes.items()):p.match((*q,*q),w.block(q),after,'r41/'+why)
    p.meta.update(rail_cells=len(rails),decisions=dict(Counter(r['decision'] for r in decisions)),changes_by_reason=dict(Counter(r[1] for r in changes.values())),
                  original_civil_basis='R20/R22 named three-layer ground slabs; R02 measured retained buildings; original R07 port and UN stair cores',
                  protected=['Active native rail swept volumes','Lift and ladder interfaces','Retractable city payloads','Main command room layout'])
    p.save_plan('complete_public_floor_boundaries')
    if apply:
        p.apply('complete_public_floor_boundaries')
        f=WORLD/'regional_states.json';states=set(json.loads(f.read_text('utf8')));states.update(s for s,_ in changes.values());f.write_text(json.dumps(sorted(states)),'utf8')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8')
    (OUT/'decisions.json').write_text(json.dumps(decisions,ensure_ascii=False,separators=(',',':')),'utf8')
    print(json.dumps(p.meta,ensure_ascii=False),flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');main(a.parse_args().apply)
