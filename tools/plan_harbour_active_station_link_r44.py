"""Connect the real harbour street to the operating S1 entrance, retire two stale QA cases."""
from pathlib import Path
from collections import deque, Counter
import argparse, gzip, hashlib, json, math
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR, iter_block_entities
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
ART=ROOT/'artifacts/rebuild_r44';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);a=parser.parse_args()
    assert not a.output.exists(),'Keep earlier measured candidates'
    profiles=ART/'surface_network/road_complete_authority_stage3.columns.npz'
    raw=np.load(profiles);nodes={tuple(map(int,q)):float(f) for q,f,g in zip(raw['coordinates'],raw['actual_feet'],raw['flags'])
        if 274<=q[0]<=600 and 190<=q[1]<=530 and g&7==7 and not g&256 and np.isfinite(f)}
    start,finish=(440,472),(386,229);assert nodes[start]==nodes[finish]==81
    queue=deque([start]);prior={start:None}
    while queue and finish not in prior:
        x,z=queue.popleft()
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            q=x+dx,z+dz
            if q in nodes and q not in prior and abs(nodes[q]-nodes[x,z])<=.501:prior[q]=(x,z);queue.append(q)
    assert finish in prior,'The existing authored street is disconnected; do not fabricate a station arrival'
    route=[];q=finish
    while q is not None:route.append([q[0]+.5,nodes[q],q[1]+.5]);q=prior[q]
    route.reverse()
    walks=ART/'facility_transit_r44/station_walk_cases_v2/station_walk_cases.json'
    entry=next(r for r in json.loads(walks.read_text('utf8')) if r['id']=='r23/station/-1611773670322478178/ground_entrance_1')
    assert entry['path']==[[378.5,81,229.5],[372.5,81,229.5],[372.5,81,230.5]]
    route.extend([[x+.5,81,229.5] for x in range(385,371,-1)]);route.append([372.5,81,230.5])
    w=MeasuredWorld(WORLD)
    for point in route:w.around(point,1)
    lo,hi=(377,77,227),(388,85,231);w.box(lo,hi);w.load()
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    shapes={canonical_state(s):b for s,b in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    changes={};held=[];preserved_station_threshold=[];allow={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:smooth_stone','minecraft:light_gray_concrete','projectseele:period_station_floor'}
    for x in range(378,387):
        for z in range(228,231):
            q=x,80,z;s=w.block(q);support=w.get(x,79,z)
            if s is None or s.split('[')[0] not in allow or q in tags or support is None or support in AIR:
                held.append(dict(pos=q,state=s,support=support,nbt=tags[q].snbt() if q in tags else None,reason='Complete public sidewalk formation is not proven'));continue
            if s=='projectseele:period_station_floor':preserved_station_threshold.append(dict(pos=q,state=s));continue
            if s!='minecraft:smooth_stone':changes[q]='minecraft:smooth_stone'
    def after(q):return changes.get(q,w.block(q))
    failures=[];unknown=Counter()
    # Actual collision shape under each full player envelope, including turns.
    footprints={(math.floor(p[0]),math.floor(p[2]),p[1]) for p in route}
    footprints.update((x,z,81) for x in range(378,387) for z in range(228,231))
    for x,z,feet in sorted(footprints):
        y=math.floor(feet-.001);s=after((x,y,z));bs=shapes.get(s)
        if bs is None:unknown[str(s)]+=1;continue
        if not any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and abs(y+b[4]-feet)<.001 for b in bs):failures.append(dict(pos=[x,feet,z],kind='CURRENT_NATIVE_FLOOR_DIFFERS'))
        for yy in range(math.floor(feet),math.ceil(feet+1.8)):
            s=after((x,yy,z));bs=[] if s in AIR else shapes.get(s)
            if bs is None:unknown[str(s)]+=1;continue
            if any(b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 and yy+b[1]<feet+1.8 and yy+b[4]>feet+.001 for b in bs):failures.append(dict(pos=[x,yy,z],kind='CURRENT_NATIVE_PLAYER_ENVELOPE_BLOCKED',state=s))
    rows=[dict(pos=q,before=w.block(q),after=s,before_nbt=None,after_nbt=None,owner='r44/active_s1_harbour_approach',reason='Founded three-metre sidewalk joins the existing harbour public street to the named operating S1 bayward ground entrance; no retired P1 platform is recreated') for q,s in sorted(changes.items())]
    a.output.mkdir(parents=True)
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as stream:
            for row in rows:
                v=dict(row)
                if inverse:v['before'],v['after']=row['after'],row['before']
                stream.write(json.dumps(v)+'\n')
    source=WORLD/'quality_walk_cases.json';old=json.loads(source.read_text('utf8'));removed=[r for r in old if r['id'] in {'r07/P1/city_interchange','r07/P1/city_interchange/return'}]
    assert len(removed)==2
    new=[dict(id='r44/harbour_street_to_operating_s1',path=route,source_platform=-1611773670322478178),dict(id='r44/harbour_street_to_operating_s1/return',path=route[::-1],source_platform=-1611773670322478178)]
    remaining=[r for r in old if r not in removed];candidate=remaining+new
    assert len(candidate)==len(old) and candidate[:-2]==remaining and not set(r['id'] for r in new)&set(r['id'] for r in old)
    before=a.output/'quality_walk_cases.before.json';before.write_bytes(source.read_bytes())
    future=a.output/'quality_walk_cases.after.json';future.write_text(json.dumps(candidate,ensure_ascii=False,indent=2),'utf8')
    (a.output/'native_cases.json').write_text(json.dumps(new,ensure_ascii=False,indent=2),'utf8')
    gate=dict(world=str(WORLD),changed_cells=len(rows),full_sidewalk_columns=27,route_points=len(route),
        operating_station='湾岸防卫区 / S1',active_platform=-1611773670322478178,source_entrance_case=entry,
        sources=[dict(path=str(p),sha256=sha(p)) for p in [profiles,walks,source]],preserved_station_threshold=preserved_station_threshold,held=held,static_failures=failures,unknown_shapes=dict(unknown),
        ready=not held and not failures and not unknown,world_written=False,metadata_written=False,native_walk_passed=False,visual_passed=False,
        metadata=dict(target=str(source),before=str(before.resolve()),after=str(future.resolve()),before_sha256=sha(before),after_sha256=sha(future),
            removed=removed,added=new,preserved_cases=len(remaining),policy='Root applies block candidate, tests both complete new journeys through the actual active entrance, and only then installs this exact two-case metadata replacement. Exact before bytes are the inverse.'),
        scope='The old P1 city-walk physical component and subsequent plinth ownership remain separate retirement work. This candidate only establishes its real operating station successor; it does not delete other walk cases, stations, MTR SavedData or traffic progress.')
    (a.output/'audit.json').write_text(json.dumps(gate,ensure_ascii=False,indent=2),'utf8')
    print('Active S1 link',len(rows),'edits',len(route),'points; held',len(held),'fails',len(failures),'unknown',dict(unknown),'ready',gate['ready'])


if __name__=='__main__':main()
