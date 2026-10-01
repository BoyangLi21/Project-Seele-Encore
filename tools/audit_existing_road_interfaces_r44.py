"""Generic new-component gate: preserve every effective old public 3D route."""
from pathlib import Path
from collections import Counter
import argparse,gzip,json,math,hashlib
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'

def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('output',type=Path);p.add_argument('--profiles',type=Path,default=ROOT/'artifacts/rebuild_r44/surface_network/road_complete_authority_stage3.columns.npz');p.add_argument('--authority',type=Path,action='append',default=[]);a=p.parse_args()
    assert not a.output.exists(),'Keep earlier interface failures and receipts'
    forward=a.plan/'forward.jsonl.gz'
    with gzip.open(forward,'rt',encoding='utf8') as f:rows=[json.loads(line) for line in f]
    proposed={tuple(r['pos']):r['after'] for r in rows};assert len(proposed)==len(rows)
    measured_before={tuple(r['pos']):r['before'] for r in rows}
    raw=np.load(a.profiles);c,f,g=raw['coordinates'],raw['actual_feet'],raw['flags']
    x0,z0=min(q[0] for q in proposed)-1,min(q[2] for q in proposed)-1;x1,z1=max(q[0] for q in proposed)+1,max(q[2] for q in proposed)+1
    selected=(c[:,0]>=x0)&(c[:,0]<=x1)&(c[:,1]>=z0)&(c[:,1]<=z1)&((g&7)==7)&np.isfinite(f)
    old={tuple(map(int,q)):(float(y),int(flags)) for q,y,flags in zip(c[selected],f[selected],g[selected])}
    declarations={}
    authority_sources=list(a.authority)+([a.plan/'road_authority.json'] if (a.plan/'road_authority.json').exists() else [])
    for authority in authority_sources:
        declarations.update({tuple(r['pos']):r.get('native_feet',r['height2']/2) for r in json.loads(authority.read_text('utf8'))['columns']})
    w=MeasuredWorld(WORLD)
    for (x,z),(foot,flags) in old.items():
        expected=declarations.get((x,z),foot);w.box((x,math.floor(min(foot,expected))-2,z),(x,math.ceil(max(foot,expected)+6),z))
    w.load();shape={canonical_state(s):boxes for s,boxes in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    def state(q):return proposed.get(q,w.block(q))
    def boxes(s):return [] if s in AIR else shape.get(s)
    errors=[];unknown=Counter();current_feet={};changed_floor=[]
    for (x,z),(foot,flags) in sorted(old.items()):
        expected=declarations.get((x,z),foot);candidates=[]
        for y in range(math.floor(expected)-2,math.ceil(expected)+1):
            bs=boxes(state((x,y,z)))
            if bs is None:unknown[state((x,y,z))]+=1;continue
            candidates.extend(y+b[4] for b in bs if b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and abs(y+b[4]-expected)<.01)
        if not candidates:errors.append(dict(pos=[x,foot,z],kind='OLD_PUBLIC_FLOOR_LOST_OR_UNDECLARED_DATUM',expected_after=expected));continue
        actual=min(candidates,key=lambda value:abs(value-expected));current_feet[x,z]=actual
        if abs(actual-foot)>.01:changed_floor.append(dict(pos=[x,z],before=foot,after=actual,explicit_authority_declared=(x,z) in declarations))
        height=1.8
        if flags&16:
            # Preserve the road's actual existing overhead capacity. A 5m
            # tunnel is not declared a collision bug solely by a 6m screen.
            height=6
            for yy in range(math.floor(foot),math.ceil(foot+6)):
                original=measured_before.get((x,yy,z),w.block((x,yy,z)));original_boxes=boxes(original)
                if original_boxes is None:unknown[original]+=1;continue
                for box in original_boxes:
                    if yy+box[4]>foot+.001 and yy+box[1]>foot+.001 and box[0]<.8 and box[3]>.2 and box[2]<.8 and box[5]>.2:height=min(height,yy+box[1]-foot)
        for y in range(math.floor(actual),math.ceil(actual+height)):
            bs=boxes(state((x,y,z)))
            if bs is None:unknown[state((x,y,z))]+=1;continue
            if any(y+b[4]>actual+.001 and y+b[1]<actual+height and b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 for b in bs):
                errors.append(dict(pos=[x,y,z],kind='OLD_VALID_PUBLIC_CLEARANCE_BLOCKED',old_feet=foot,effective_after_feet=actual,old_native_flags=flags,required_height=height,state=state((x,y,z)),new_component_here=(x,y,z) in proposed))
    directional_edges=0
    for (x,z),(before,flags) in old.items():
        for dx,dz in ((1,0),(0,1)):
            other=x+dx,z+dz
            if other not in old or abs(old[other][0]-before)>.501:continue
            directional_edges+=2
            first,last=current_feet.get((x,z)),current_feet.get(other)
            if first is None or last is None:continue
            if abs(first-last)>.501:errors.append(dict(pos=[x,first,z],to=[other[0],last,other[1]],kind='OLD_CONNECTED_PUBLIC_DIRECTION_NOW_HAS_UNDECLARED_STEP',before_step=abs(old[other][0]-before),after_step=abs(first-last)))
    result=dict(plan=str(a.plan.resolve()),source_forward_sha256=hashlib.sha256(forward.read_bytes()).hexdigest(),old_profile_sha256=hashlib.sha256(a.profiles.read_bytes()).hexdigest(),explicit_authorities=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in authority_sources],
        old_effective_public_columns=len(old),old_directed_orthogonal_connections=directional_edges,explicit_floor_successors=changed_floor,failures=errors,unknown_shapes=dict(unknown),passed=not errors and not unknown,
        world_written=False,native_original_directions_tested=False,turning_vehicle_sweeps_tested=False,
        rule='Each new block is judged against exact existing floor Y, native 1.8m pedestrian clearance or the actually available original vehicle-road clearance capped at the 6m engineering screen, all original widths and adjacent public directions. Five-metre roofs are not called vehicle collision bugs without permitted vehicle envelopes. A renamed road, black material or 2D same component cannot waive this gate. Retired routes need explicit replacement topology and actual native port/turn tests; this tool does not approve retirement.')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Old public interface gate',len(old),'columns',directional_edges,'directed edges','failures',len(errors),'unknown',dict(unknown),'PASS',result['passed'],flush=True)

if __name__=='__main__':main()
