"""Read-only local before/after collision and inverse proofs, not a game pass."""
from pathlib import Path
import argparse,gzip,json,math
import nbtlib
from query_blocks import read_box,iter_block_entities,AIR

ROOT=Path(__file__).resolve().parents[1]
DIM='projectseele:geofront'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,default=ROOT/'artifacts/rebuild_r49/facilities');args=ap.parse_args()
    world=args.world.resolve();out=args.candidate.resolve()
    shapes=json.loads((world/'native_collision_shapes.json').read_text('utf8'))
    before={};after={};tags={};rows=[]
    for v in range(3):
        x=7+42*v;lo=(x-2,-395,-228);hi=(x+1,-392,-219)
        before.update(read_box(world,DIM,lo,hi));tags.update(iter_block_entities(world,DIM,lo,hi))
    lo=(12,-370,298);hi=(55,-354,330)
    before.update(read_box(world,DIM,lo,hi));tags.update(iter_block_entities(world,DIM,lo,hi));after.update(before)
    for folder in sorted(out.glob('F*')):
        with gzip.open(folder/'forward.jsonl.gz','rt',encoding='utf8') as f: forward=[json.loads(l) for l in f]
        with gzip.open(folder/'inverse.jsonl.gz','rt',encoding='utf8') as f: inverse=[json.loads(l) for l in f]
        assert len(forward)==len(inverse)
        for r,i in zip(forward,reversed(inverse)):
            q=tuple(r['pos']);assert before[q]==r['before'];old=None if r['before_nbt'] is None else nbtlib.parse_nbt(r['before_nbt'])
            assert tags.get(q)==old
            assert i['pos']==r['pos'] and i['after']==r['before'] and i['before']==r['after']
            assert i['after_nbt']==r['before_nbt'] and i['before_nbt']==r['after_nbt']
            after[q]=r['after'];rows.append(r)
        assert json.loads((folder/'positiveEditMask.json').read_text())==[r['pos'] for r in forward]
    assert len({tuple(r['pos']) for r in rows})==len(rows)

    def boxes(state):
        if state in AIR:return []
        if state.startswith('projectseele:nerv_room_partition['):
            # Explicit finite partition source geometry; cache predates R47.
            edges={'north':[0,0,0,1,1,.125],'east':[.875,0,0,1,1,1],
                   'south':[0,0,.875,1,1,1],'west':[0,0,0,.125,1,1]}
            return [v for k,v in edges.items() if k+'=true' in state]
        if state not in shapes:raise ValueError(('Missing actual collision/source shape',state))
        return shapes[state]
    def collision(cells,feet):
        x,y,z=feet;body=[x-.3,y+.001,z-.3,x+.3,y+1.8,z+.3];hits=[]
        for X in range(math.floor(body[0]),math.ceil(body[3])):
            for Y in range(math.floor(body[1]),math.ceil(body[4])):
                for Z in range(math.floor(body[2]),math.ceil(body[5])):
                    state=cells[X,Y,Z]
                    for b in boxes(state):
                        box=[b[0]+X,b[1]+Y,b[2]+Z,b[3]+X,b[4]+Y,b[5]+Z]
                        if all(body[k]<box[k+3] and box[k]<body[k+3] for k in range(3)):
                            hits.append(dict(pos=[X,Y,Z],state=state));break
        return hits
    def route(cells,points):
        samples=0
        for start,end in zip(points,points[1:]):
            length=math.dist(start,end);n=max(1,math.ceil(length/.05))
            for i in range(n+1):
                p=[a+(b-a)*i/n for a,b in zip(start,end)];hits=collision(cells,p)
                if hits:return dict(passed=False,first_error_feet=p,hits=hits,samples=samples)
                support=cells[math.floor(p[0]),math.floor(p[1])-1,math.floor(p[2])]
                if not any(b[1]<1 and b[4]>=1 for b in boxes(support)):
                    return dict(passed=False,first_error_feet=p,unsupported_state=support,samples=samples)
                samples+=1
        return dict(passed=True,samples=samples)
    marker=json.loads((out/'r49_facility_controls.json').read_text('utf8'));proofs=[]
    for door in marker['pilot_guard_doors']:
        closed=route(before,door['route']);assert not closed['passed']
        opened=dict(after)
        for y in (-394,-393):
            q=door['lower'][0],y,-223;opened[q]=opened[q].replace('open=false','open=true')
        result=route(opened,door['route']);assert result['passed'],result
        assert not route(after,door['route'])['passed']
        proofs.append(dict(kind='pilot_guard_door',variant=door['variant'],before=closed,after_open=result,after_closed_blocks=True))
    course=[[29,-364,314.5],[29,-364,316.5]]
    opened=dict(after)
    for x in (28,29):
        for y in (-364,-363):opened[x,y,315]=opened[x,y,315].replace('open=false','open=true')
    result=route(opened,course);assert result['passed'],result
    assert not route(after,course)['passed']
    proofs.append(dict(kind='seele_gate',after_open=result,after_closed_blocks=True,open_clear_width=1.625))
    # Side seal spans every full human height from floor to roof, never modifies
    # lift layer317 or cabin volume318..324. It does not touch any stair cells.
    assert all(after[x,y,316]=='minecraft:black_concrete' for x in (25,32) for y in range(-364,-355))
    assert all(after[x,-356,316]=='minecraft:black_concrete' for x in range(25,33))
    stairs=[(q,s) for q,s in before.items() if 'stairs[' in s or 'escalator_step[' in s]
    assert all(after[q]==s for q,s in stairs)
    nearby_stair_clearances=[]
    for q,s in stairs:
        # A collision result is recorded only for actual upper clear cells,
        # irrespective of whether a pre-existing external landing is occupied.
        feet=[q[0]+.5,q[1]+1,q[2]+.5]
        old=collision(before,feet);new=collision(after,feet)
        assert old==new
        nearby_stair_clearances.append(dict(pos=list(q),state=s,clearance_unchanged=True,clear_after=not new))
    report=dict(schema=49,world=str(world),unique_changed_cells=len(rows),full_old_NBT_match=True,
                inverse_roundtrip=True,finite_native_shape_cache_and_partition_source_only=True,
                proofs=proofs,adjacent_stairs=nearby_stair_clearances,
                lift317_and_cabin318_324_untouched=all(not(25<=r['pos'][0]<=31 and 317<=r['pos'][2]<=324) for r in rows),
                world_written=False,native_game_verified=False,visual_verified=False)
    (out/'local_collision_inverse_proof.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(unique_changed_cells=len(rows),inverse_roundtrip=True,door_routes=proofs,adjacent_stair_cells=len(stairs),native_game_verified=False),ensure_ascii=False))

if __name__=='__main__':main()
