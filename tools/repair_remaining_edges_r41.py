"""Finish connected surface paving and non-boarding station ends.

Keep airside movement areas, active track beds and closed exterior roofs distinct
from public circulation. Fixed station-end guards sit back from the train gauge.
"""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,json
import numpy as np
from scipy.spatial import cKDTree
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from aircraft_boarding_authority_r44 import AircraftBoardingAuthority

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41'
WORLD=ROOT/'run/saves/SEELE_FIELD_R41_REVIEW';OUT=ART/'remaining_edges'


def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    source=json.loads((ART/'regional_edges/decisions.json').read_text('utf8'))
    rows=[r for r in source if r['decision'] in {'retained_for_context_review','grade_boundary_preserved_pending_material_context','active_train_clearance_preserved'}]
    w=MeasuredWorld(WORLD)
    for r in rows:w.around(r['pos'],4)
    w.load();native=json.loads((WORLD/'native_transit_r28.json').read_text('utf8'))
    rail=np.asarray([p for c in native['curves'] if c['mode']=='TRAIN' for p in c['points']],float);tree=cKDTree(rail[:,[0,2]])
    def near_track(q,radius=3.1):
        return any(rail[i,1]-1.2<=q[1]<=rail[i,1]+7 for i in tree.query_ball_point([q[0]+.5,q[2]+.5],radius))
    shapes={v.canonical_state(k):b for k,b in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    def boxes(q):
        s=w.block(q)
        return shapes.get(s,[] if s and s.partition('[')[0] in AIR|{'minecraft:light'} else [[0,0,0,1,1,1]])
    def supported(q):return any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and .9<=b[4]<=1.01 for b in boxes(q))
    def blocked(q):return any(b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 and b[4]>.01 and b[1]<1 for b in boxes(q))
    def airside(q):
        x,y,z=q
        return y>0 and ((480<=x<=1260 and 1320<=z<=1540) or (-2180<=x<=-1400 and -80<=z<=80) or (6720<=x<=6820 and -6690<=z<=-5990))
    boarding=AircraftBoardingAuthority(WORLD)
    decisions=[];rails=defaultdict(set);changes={};names={(1,0,0):'east',(-1,0,0):'west',(0,0,1):'south',(0,0,-1):'north'}
    for r in rows:
        q=tuple(r['pos']);x,y,z=q;dx,_,dz=r['normal'];n=(x+dx,y,z+dz);state=w.block(q);why='';target=q
        if boarding.owner(q):why='native_aircraft_dynamic_stair_or_door_interface_preserved'
        elif supported((n[0],y-1,n[2])) or blocked(n):why='current_supported_floor_or_existing_boundary'
        elif y==-329:why='closed_commander_exterior_roof_not_public_circulation'
        elif airside(q):why='restricted_airside_graded_pavement_edge_keep_aircraft_clearance'
        elif any((w.get(x+dx*d,y,z+dz*d) or '').startswith(('mtr:apg_','mtr:psd_')) for d in (0,1,2)):
            why='native_boarding_gate_preserved'
        else:
            if near_track(q):
                # Fixed guards belong on pedestrian pavement, outside the
                # actual native train envelope, not on its approach ballast.
                options=[(x-dx*d,y,z-dz*d) for d in (1,2,3)]
                target=next((p for p in options if supported((p[0],p[1]-1,p[2])) and not blocked(p) and not near_track(p) and not boarding.owner(p)),None)
                if target is None:why='native_track_approach_bed_no_safe_pedestrian_guard_cell'
            if not why:
                old=w.block(target)
                if old in AIR or (old or '').startswith('projectseele:nerv_edge_rail['):
                    rails[target].update(k for k in names.values() if k+'=true' in old);rails[target].add(names[tuple(r['normal'])])
                    why='setback_nonboarding_end_guard' if target!=q else 'connected_public_paving_edge_guard'
                elif (old or '').startswith('minecraft:light[') and w.get(target[0],target[1]+3,target[2]) in AIR:
                    changes[(target[0],target[1]+3,target[2])]=(old,'retain_ceiling_illumination');rails[target].add(names[tuple(r['normal'])]);why='lit_public_paving_edge_guard'
                else:why='existing_fixture_or_closed_door_boundary_preserved'
        decisions.append({**r,'final_disposition':why,'guard_cell':target if 'guard' in why and why!='native_track_approach_bed_no_safe_pedestrian_guard_cell' else None})
    for q,sides in rails.items():
        after='projectseele:nerv_edge_rail['+','.join(k+'='+str(k in sides).lower() for k in ('east','north','south','west'))+']'
        if w.block(q)!=after:changes[q]=(after,'surface_and_station_end_boundary')
    by_chunk=defaultdict(list)
    for q in changes:by_chunk[q[0]//16,q[2]//16].append(q[1])
    for (cx,cz),ys in by_chunk.items():
        tags=dict(iter_block_entities(WORLD,v.DIM,(cx*16,min(ys),cz*16),(cx*16+15,max(ys),cz*16+15)))
        assert not set(tags)&set(changes),'Candidate intersects a block entity'
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter()
    for q,(after,why) in sorted(changes.items()):
        assert w.block(q).partition('[')[0] in AIR|{'minecraft:light','projectseele:nerv_edge_rail'},(q,w.block(q))
        p.match((*q,*q),w.block(q),after,'r41/'+why)
    p.meta.update(dispositions=dict(Counter(r['final_disposition'] for r in decisions)),rail_cells=len(rails),scope='Previously unclassified full measured floor components; no roof or track filling; actual train-gauge setback measured against current native curves')
    p.save_plan('remaining_connected_floor_perimeters')
    if apply:
        p.apply('remaining_connected_floor_perimeters');f=WORLD/'regional_states.json';s=set(json.loads(f.read_text('utf8')));s.update(v[0] for v in changes.values());f.write_text(json.dumps(sorted(s)),'utf8')
    (OUT/'dispositions.json').write_text(json.dumps(decisions,ensure_ascii=False,separators=(',',':')),'utf8')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8');print(p.meta,flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');main(a.parse_args().apply)
