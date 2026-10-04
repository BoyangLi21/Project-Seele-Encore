"""H01 7-wide aperture/9-authored stair semantics; actual full-body evidence."""
from pathlib import Path
import json,math,sys,hashlib
sys.dont_write_bytecode=True
from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry
from prepare_b2_stair_component_r45 import full_body_status
ROOT=Path(__file__).resolve().parents[1];PYR=ROOT/'artifacts/rebuild_r45/pyramid_components_sol_v1';WORLD=ROOT/'artifacts/rebuild_r45/composition_candidates/R45_source_candidate_20261003_v4_01/world';OUT=PYR/'H01_complete_entry_body_v1'
def main():
    if OUT.exists():assert {p.name for p in OUT.iterdir()}=={'initial_nine_stair_assumption_failure.json'}
    else:OUT.mkdir()
    m=MeasuredWorld(WORLD);m.box((23,-472,432),(37,-457,448));m.load();assert all(s=='full'for s in m.status.values());g=ActualGeometry(m)
    def colliders(p):
        lo=[p[0]-.3,p[1]+1e-6,p[2]-.3];hi=[p[0]+.3,p[1]+1.8,p[2]+.3];result=[]
        for x in range(math.floor(lo[0]),math.floor(hi[0])+1):
            for y in range(math.floor(lo[1]),math.floor(hi[1])+1):
                for z in range(math.floor(lo[2]),math.floor(hi[2])+1):
                    boxes=g.boxes((x,y,z));assert boxes is not None
                    if any(all((x,y,z)[i]+b[i]<hi[i]and(x,y,z)[i]+b[i+3]>lo[i]for i in range(3))for b in boxes):result.append(dict(position=[x,y,z],state=m.block((x,y,z)),native_boxes=boxes))
        return result
    stairs=[];aperture=[]
    for x in range(26,35):
        for i in range(5):
            y,z=-462-i,437+i;state=m.block((x,y,z))
            if 27<=x<=33:assert state=='minecraft:polished_deepslate_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]'
            else:assert state in {'minecraft:smooth_stone','minecraft:air'}
            for phase,foot,dz in [('upper',1,.4),('lower',.5,.9)]:
                p=[x+.5,y+foot,z+dz];status=full_body_status(g,p);stairs.append(dict(lane_x=x,actual_cell=[x,y,z],actual_cell_state=state,current_actual_stair=27<=x<=33,feet=p,phase=phase,status=status,actual_colliders=colliders(p)if status!='CLEAR'else[]))
    for x in range(24,37):
        for y in range(-466,-461):aperture.append(dict(position=[x,y,442],state=m.block((x,y,442))))
    paths=[]
    for x in range(27,34):
        p=[[x+.5,-461,436.5]]
        for i in range(5):p.extend([[x+.5,-461-i,437.4+i],[x+.5,-461.5-i,437.9+i]])
        p.extend([[x+.5,-466,z+.5]for z in range(442,446)])
        clear=[full_body_status(g,q)for q in p];sweep=[full_body_status(g,a,b)for a,b in zip(p,p[1:])];assert all(s=='CLEAR'for s in clear+sweep)
        paths.append(dict(lane_x=x,points=p,full0_6x1_8_body=clear,higher_datum_sweeps=sweep,native_player_walk=False))
    assert sum(r['status']=='CLEAR'for r in stairs)==78 and sum(r['status']=='BODY_OBSTRUCTION'for r in stairs)==12
    summary=dict(source_world=str(WORLD),source_read_only=True,current_stair_width7_treads35_exact=True,current_outer_columns26_34_are_not_stairs=True,earlier_nine_stair_claim_falsified=True,true_aperture_x=[27,33],true_open_width7=True,aperture_y=[-466,-462],lower_floor_y=-467,upper_flat_floor_y=-462,all7_actual_direct_player_profiles_and_sweeps_STATIC_CLEAR=True,outer_non_stair_columns_x=[26,34],outside_stair_half_step_body_obstructions12=True,meaning='Current35 exact treads form7 complete usable public lanes and match7-wide true aperture. The old9-width guess included two NON-stair side columns of stone/air.12 outside-domain body probes hit actual enclosure. Retain wall/glass/thin light; no repair or all9-width PASS from this record. Original nine-width producer-intent classification belongs to City owner and is not inferred here.',repair_candidate=False,all9_full_width_pass=False,native_walk_pass=False,world_written=False,model_changed=False,stairs=stairs,aperture_complete_state=aperture,paths=paths,native_shape_sha256=hashlib.sha256((WORLD/'native_collision_shapes.json').read_bytes()).hexdigest())
    (OUT/'actual_aperture_stairs_body_and_colliders.json').write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print('H01:7 actual stair/aperture body lanes clear; old9 guess included2 NON-stair columns; no repair/world write.',flush=True)
if __name__=='__main__':main()
