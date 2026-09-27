"""Whole-width interface walks and perpendicular tests of real public edges."""
from pathlib import Path
import json,gzip,hashlib
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41';WORLD=ROOT/'run/saves/SEELE_FIELD_R41_REVIEW'


def main():
    rows=json.loads((ART/'envelopes/findings.json').read_text('utf8'))['findings']
    with gzip.open(ART/'source_world_backup/nerv_routes_r24.json.gz','rt',encoding='utf8') as f:nav=json.load(f)
    public={tuple(n[:3]) for n in nav['nodes']}
    with gzip.open(WORLD/'nerv_routes_r24.json.gz','rt',encoding='utf8') as f:public.update(tuple(n[:3]) for n in json.load(f)['nodes'])
    edges=[r for r in rows if r['kind']=='unguarded_drop' and tuple(r['pos']) in public]
    w=MeasuredWorld(WORLD)
    for r in edges:w.around(r['pos'],3)
    w.load();shapes={canonical_state(s):v for s,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    def clear(q):
        for dy,height in [(0,1),(1,.8)]:
            s=w.get(q[0],q[1]+dy,q[2]);bs=shapes.get(s,[] if s and s.partition('[')[0] in AIR|{'minecraft:light'} else [[0,0,0,1,1,1]])
            if any(b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 and b[1]<height and b[4]>.001 for b in bs):return False
        return True
    def standing(q):
        if not clear(q):return False
        s=w.get(q[0],q[1]-1,q[2]);boxes=shapes.get(s,[] if s and s.partition('[')[0] in AIR|{'minecraft:light'} else [[0,0,0,1,1,1]])
        return any(b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 and b[4]>=.9 for b in boxes)
    cases=[];held=[]
    def walk(name,path):
        for suffix,points in [('',path),('/return',list(reversed(path)))]:cases.append(dict(id='r41/'+name+suffix,path=points))
    for z in (-269.5,-268.5):walk('hangar_port/'+str(z),[[81.5,-394,z],[90.5,-394,z]])
    for foot in (-434,-420,-406,-392):
        for x in (73.5,74.5):walk(f'east_junction/{foot}/{x}',[[x,foot,303.5],[x,foot,314.5]])
    for z in (724.5,725.5,727.5,728.5):walk('arrival_landing/'+str(z),[[-334.5,-466,z],[-331.5,-466,z]])
    for z in (-6246.5,-6245.5):walk('un_turn_landing/'+str(z),[[6469.5,77,z],[6472.5,77,z],[6472.5,77,-6244.5]])
    for x in (6418.5,6419.5,6421.5,6422.5):walk('un_through_port/'+str(x),[[x,77,-6230.5],[x,77,-6225.5]])
    walk('airport_restored_facade',[[325.5,81,38.5],[325.5,81,35.5],[385.5,73,35.5],[385.5,73,38.5],[385.5,73,44.5]])
    for r in edges:
        q=tuple(r['pos']);n=r['normal'];start=tuple(q[i]-n[i] for i in range(3))
        if q[1]==-329 and 16<=q[0]<=23 and 304<=q[2]<=310:
            held.append(dict(candidate=r,reason='Exterior commander-room roof; retain pyramid silhouette, not a personnel circulation edge'));continue
        if not standing(start):start=q
        if not standing(start):held.append(dict(candidate=r,reason='No supported clear probe start; inspect a real approach, do not count as passed'));continue
        axis=0 if n[0] else 2;plane=q[axis]+(1 if n[axis]>0 else 0)
        a=[start[0]+.5,start[1],start[2]+.5];b=[q[0]+n[0]*1.5+.5,q[1],q[2]+n[2]*1.5+.5]
        ident=hashlib.sha256(json.dumps([q,n]).encode()).hexdigest()[:12]
        case=dict(id='r41/edge/'+ident,path=[a,b],barrier=dict(axis='x' if axis==0 else 'z',plane=plane,maxGap=1.75),candidate=r)
        if any('ladder' in (w.get(q[0]+n[0],q[1]-dy,q[2]+n[2]) or '') for dy in (0,1,2)):
            case['climbablePort']=True;case['purpose']='Real vertical ladder access: native onClimbable must engage before a damaging drop'
        cases.append(case)
    (WORLD/'r41_walk_cases.json').write_text(json.dumps(cases,ensure_ascii=False),'utf8')
    out=ART/'native_spatial';out.mkdir(exist_ok=True)
    (out/'first_cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),'utf8')
    (out/'edge_approach_holds.json').write_text(json.dumps(held,ensure_ascii=False,indent=2),'utf8')
    state_path=WORLD/'regional_states.json';states=set(json.loads(state_path.read_text('utf8')))
    states.add('projectseele:retractable_building_core[armed=true]')
    state_path.write_text(json.dumps(sorted(states)),'utf8')
    print('Whole-width and edge probes:',len(cases),'unresolved probe approaches:',len(held),flush=True)


if __name__=='__main__':main()
