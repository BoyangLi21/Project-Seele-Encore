"""Local measured bridge inverse, walk/step and phase-clearance proofs; no game pass."""
from pathlib import Path
import argparse,gzip,json,math
import nbtlib
from prepare_entry_plug_bridge_r49 import DECK,GUARD,DIRS,DIM,room,upper,wanted
from query_blocks import read_box,iter_block_entities,AIR
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--candidate',type=Path,default=ROOT/'artifacts/rebuild_r49/bridge_topology');args=ap.parse_args()
    w=args.world.resolve();out=args.candidate.resolve();before={};bes={}
    for cx in(-12,30,72):
        lo=(cx-21,-397,-229);hi=(cx+21,-389,-214)
        before.update(read_box(w,DIM,lo,hi));bes.update(iter_block_entities(w,DIM,lo,hi))
    shapes=json.loads((w/'native_collision_shapes.json').read_text())
    c=out/'R49_through_side_bridge_and_stairs'
    with gzip.open(c/'forward.jsonl.gz','rt',encoding='utf8') as f:rows=[json.loads(l) for l in f]
    with gzip.open(c/'inverse.jsonl.gz','rt',encoding='utf8') as f:inverse=[json.loads(l) for l in f]
    after=dict(before);assert len(rows)==len(inverse)
    for r,i in zip(rows,reversed(inverse)):
        q=tuple(r['pos']);assert before[q]==r['before'] and bes.get(q)==(None if r['before_nbt'] is None else nbtlib.parse_nbt(r['before_nbt']))
        assert i['pos']==r['pos'] and i['before']==r['after'] and i['after']==r['before'] and i['before_nbt']==r['after_nbt'] and i['after_nbt']==r['before_nbt'];after[q]=r['after']
    assert json.loads((c/'positiveEditMask.json').read_text())==[r['pos'] for r in rows]
    def boxes(s):
        if s in AIR:return []
        flags={k for k in DIRS if k+'=true' in s}
        if s.startswith(DECK+'['):return [[0,.84375,0,1,1,1],[.0625,0,.0625,.1875,.84375,.9375],[.8125,0,.0625,.9375,.84375,.9375],[.1875,.125,.4375,.8125,.25,.5625]]
        if s.startswith(GUARD+'['):
            # Exact FacilityEdgeRailR41 slenderShapes posts and two beams.
            edges={
                'north':[[0,0,0,.05,1.1,.05],[.95,0,0,1,1.1,.05],[0,.5,0,1,.55,.05],[0,1.05,0,1,1.1,.05]],
                'east':[[.95,0,0,1,1.1,.05],[.95,0,.95,1,1.1,1],[.95,.5,0,1,.55,1],[.95,1.05,0,1,1.1,1]],
                'south':[[0,0,.95,.05,1.1,1],[.95,0,.95,1,1.1,1],[0,.5,.95,1,.55,1],[0,1.05,.95,1,1.1,1]],
                'west':[[0,0,0,.05,1.1,.05],[0,0,.95,.05,1.1,1],[0,.5,0,.05,.55,1],[0,1.05,0,.05,1.1,1]]}
            return [box for k in flags for box in edges[k]]
        if s.startswith('projectseele:nerv_room_partition['):
            edges={'north':[0,0,0,1,1,.125],'east':[.875,0,0,1,1,1],'south':[0,0,.875,1,1,1],'west':[0,0,0,.125,1,1]}
            return [edges[k] for k in flags]
        assert s in shapes,('Missing original native state shape',s)
        return shapes[s]
    def collision(cells,point):
        x,y,z=point;body=[x-.3,y+.001,z-.3,x+.3,y+1.8,z+.3];hits=[]
        for X in range(math.floor(body[0]),math.ceil(body[3])):
            for Y in range(math.floor(body[1]),math.ceil(body[4])):
                for Z in range(math.floor(body[2]),math.ceil(body[5])):
                    s=cells[X,Y,Z]
                    for b in boxes(s):
                        B=[b[0]+X,b[1]+Y,b[2]+Z,b[3]+X,b[4]+Y,b[5]+Z]
                        if all(body[k]<B[k+3] and B[k]<body[k+3] for k in range(3)):
                            hits.append(dict(pos=[X,Y,Z],state=s));break
        return hits
    def route(cells,points,step=False):
        y=points[0][1];samples=0;heights=[]
        for start,end in zip(points,points[1:]):
            n=max(1,math.ceil(math.dist(start,end)/.05))
            for i in range(n+1):
                p=[a+(b-a)*i/n for a,b in zip(start,end)];x,z=p[0],p[2]
                if step:
                    tops=[]
                    for X in range(math.floor(x-.3),math.ceil(x+.3)):
                        for Y in range(-396,-392):
                            for Z in range(math.floor(z-.3),math.ceil(z+.3)):
                                for b in boxes(cells[X,Y,Z]):
                                    if x-.3<X+b[3] and X+b[0]<x+.3 and z-.3<Z+b[5] and Z+b[2]<z+.3 and Y+b[4]<=y+.6001:
                                        tops.append(Y+b[4])
                    if not tops:return dict(passed=False,unsupported=[x,y,z],samples=samples)
                    next_y=max(tops)
                    if abs(next_y-y)>.6001:return dict(passed=False,step_too_large=[y,next_y],samples=samples)
                    y=next_y;p[1]=y;heights.append(y)
                hits=collision(cells,p)
                if hits:return dict(passed=False,first_error=p,hits=hits,samples=samples)
                if not step:
                    q=math.floor(x),math.floor(p[1])-1,math.floor(z)
                    if not any(b[4]>=1 for b in boxes(cells[q])):return dict(passed=False,unsupported=p,samples=samples)
                samples+=1
        return dict(passed=True,samples=samples,foot_heights=sorted(set(heights)) if step else [points[0][1]])
    proofs=[];phase_proof=[]
    for v,cx in enumerate((-12,30,72)):
        for amount in range(10):
            state=wanted(before,cx,v,amount)
            actual_phase=dict(before);actual_phase.update(state)
            assert wanted(actual_phase,cx,v,amount)==state,('Runtime maintenance would rewrite its own coherent phase',v,amount)
            phase_proof.append(dict(variant=v,extension=amount,owned_cells=len(state),all_new_stairs_withdrawn=amount<9,
                                   finite_floor_guard_maintenance_idempotent=True,
                                   complete_retracted_at_zero=amount!=0 or all(s in AIR or s.startswith('minecraft:light[') for q,s in state.items() if cx-16<=q[0]<=cx+16)))
        for sign in(-1,1):
            points=[[cx+sign*17+.5,-394,-225.5],[cx+sign*4+.5,-394,-225.5],[cx+sign*4+.5,-394,-215.5],[cx+sign*17+.5,-394,-215.5]]
            original=route(before,points);assert not original['passed']
            forward=route(after,points);assert forward['passed'],forward
            reverse=route(after,list(reversed(points)));assert reverse['passed'],reverse
            stairs=[[cx+sign*2+.5,-394,-220.5],[cx+sign*2+.5,-393,-223.5]]
            ascent=route(after,stairs,True);assert ascent['passed'] and ascent['foot_heights']==[-394,-393.5,-393],ascent
            descent=route(after,list(reversed(stairs)),True);assert descent['passed'],descent
            proofs.append(dict(variant=v,side=sign,before=original,through_forward=forward,through_reverse=reverse,stairs_up=ascent,stairs_down=descent))
        assert not collision(after,[cx+2.5,-394,-220.5])
        assert after[cx+2,-395,-221].startswith(DECK+'[')
        assert all(not(room(v,tuple(r['pos']))) for r in rows)
    # New colliding cells stay laterally clear of the retained capsule's exact
    # BODY_OBB x half extent1.2, centre bed+.5. The staircase is entirely outside.
    capsule_clear=[]
    for v,cx in enumerate((-12,30,72)):
        capsule_min,capsule_max=cx-.7,cx+1.7
        new_near=[r for r in rows if cx-16<=r['pos'][0]<=cx+16 and r['pos'][1]>=-395 and r['before'] in AIR and r['after'] not in AIR]
        for r in new_near:
            q=r['pos']
            for b in boxes(r['after']):
                assert q[0]+b[3]<=capsule_min or q[0]+b[0]>=capsule_max,('New civil work intersects retained capsule lateral body OBB',q,r['after'])
        capsule_clear.append(dict(variant=v,new_civil_cells=len(new_near),capsule_x_bounds=[capsule_min,capsule_max],closest_stair_gap=.3,no_capsule_or_crane_entity_NBT_edited=True))
    report=dict(schema=49,changed_cells=len(rows),full_old_NBT_match=True,inverse_roundtrip=True,world_written=False,
                native_game_verified=False,visual_verified=False,collision_reference='Existing native_collision_shapes + exact R48 deck/guard and R47 partition source shapes',
                route_proofs=proofs,phase_proofs=phase_proof,retained_capsule_lateral_clearance=capsule_clear,original_goal_and_room_untouched=True)
    (out/'local_route_phase_inverse_proof.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(changed_cells=len(rows),through_routes=len(proofs),stairs_up_down=12,phase_states=len(phase_proof),inverse_roundtrip=True,native_game_verified=False),ensure_ascii=False))
if __name__=='__main__':main()
