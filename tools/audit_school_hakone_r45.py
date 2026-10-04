"""Read-only exact/NBT, native-shape and full-floor review of agent candidates.

No static result is a native gameplay or art pass. Unknown native shapes and
position-dependent fixture parts remain explicit until root captures them.
"""
from pathlib import Path
from collections import Counter,deque
import argparse
import gzip
import json
import math

import nbtlib

from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from audit_facility_transit_r44 import Geometry
from school_hakone_patch_r45 import ROOT,ART,sha


class Ghost:
    def __init__(self,measured,rows,open_doors):
        self.world=measured.world
        self.measured=measured
        self.patch={tuple(r['pos']):r['after'] for r in rows}
        self.open_doors=open_doors

    def get(self,x,y,z):
        q=math.floor(x),math.floor(y),math.floor(z)
        st=self.patch.get(q,self.measured.block(q))
        if st and self.open_doors and st.startswith('projectseele:city_personnel_door['):return st.replace('open=false','open=true')
        return st


def full_floor(g,region):
    x,z,X,Z=region['bounds'];feet=region['feet']
    observed={}
    for xx in range(x,X+1):
        for zz in range(z,Z+1):observed[xx,zz]=g.standing((xx,feet,zz))
    valid={q for q,v in observed.items() if v['status']=='STATIC_STANDING'}
    groups=[]
    unseen=set(valid)
    while unseen:
        seed=min(unseen);unseen.remove(seed);todo=deque([seed]);cells=[]
        while todo:
            q=todo.popleft();cells.append(q)
            for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
                nxt=q[0]+dx,q[1]+dz
                if nxt in unseen and g.edge_clear((q[0],feet,q[1]),(nxt[0],feet,nxt[1])):
                    unseen.remove(nxt);todo.append(nxt)
        groups.append(cells)
    return dict(id=region['id'],feet=feet,total_columns=len(observed),statuses=dict(Counter(v['status'] for v in observed.values())),flat_walkable_components=[dict(columns=len(cells),bounds=[min(q[0] for q in cells),min(q[1] for q in cells),max(q[0] for q in cells),max(q[1] for q in cells)]) for cells in sorted(groups,key=len,reverse=True)],unknown_samples=[v for v in observed.values() if v['status']=='UNKNOWN'][:20])


def main():
    p=argparse.ArgumentParser()
    p.add_argument('plan',type=Path)
    p.add_argument('--world',type=Path,default=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW')
    p.add_argument('--name',default='static_audit')
    a=p.parse_args()
    contract=json.loads((a.plan/'contract.json').read_text('utf8'))
    rows=[json.loads(s) for s in gzip.open(a.plan/'forward.jsonl.gz','rt',encoding='utf8')]
    back=[json.loads(s) for s in gzip.open(a.plan/'inverse.jsonl.gz','rt',encoding='utf8')]
    assert len(rows)==len(back)==len({tuple(r['pos']) for r in rows})
    for r,b in zip(rows,back):
        assert r['pos']==b['pos'] and (r['before'],r['after'],r['before_nbt'],r['after_nbt'])==(b['after'],b['before'],b['after_nbt'],b['before_nbt'])
        if r['after_nbt'] is not None:
            n=nbtlib.parse_nbt(r['after_nbt']);assert [int(n[k]) for k in ['x','y','z']]==r['pos']
    lo,hi=tuple(contract['bounds'][:3]),tuple(contract['bounds'][3:])
    w=MeasuredWorld(a.world);w.box(lo,hi);w.load()
    tags={q:t.snbt() for q,t in iter_block_entities(a.world,'projectseele:geofront',lo,hi)}
    preconditions=[]
    for r in rows:
        q=tuple(r['pos'])
        if w.block(q)!=r['before'] or tags.get(q)!=r['before_nbt']:
            preconditions.append(dict(pos=r['pos'],actual=w.block(q),expected=r['before'],nbt_matches=tags.get(q)==r['before_nbt']))
    preserved=json.loads((a.plan/'preserved_block_entities.json').read_text('utf8'))
    changed_original=[]
    target={tuple(r['pos']):r for r in rows}
    for b in preserved:
        q=tuple(b['pos'])
        if q in target or w.block(q)!=b['state'] or tags.get(q)!=b['snbt']:
            changed_original.append(q)
    ghost=Ghost(w,rows,True);g=Geometry(ghost)
    regions=json.loads((a.plan/'floor_regions.json').read_text('utf8'))
    floors=[full_floor(g,r) for r in regions]
    cases=json.loads((a.plan/'native_cases.json').read_text('utf8'))
    results=[]
    for case in cases:
        points=case.get('path') or [case.get('start'),case.get('end')]
        if not points or points[0] is None:continue
        if any(not all(lo[k]<=math.floor(q[k])<=hi[k] for k in range(3)) for q in points):
            results.append(dict(id=case['id'],status='INHERITED_ROUTE_OUTSIDE_FINITE_STATIC_SCOPE'));continue
        special=case.get('requires_actual_APG_open') or case.get('interaction') or any(t in case['id'] for t in ['ground_entrance','pool/from_school_north_port'])
        if special or any(abs(a[1]-b[1])>.01 for a,b in zip(points,points[1:])):
            results.append(dict(id=case['id'],status='NATIVE_DEVICE_OR_VERTICAL_MOTION_REQUIRED'));continue
        failures=[];unknown=[]
        for first,last in zip(points,points[1:]):
            steps=max(1,math.ceil(math.dist(first,last)*2));prev=None
            for i in range(steps+1):
                point=[first[k]+(last[k]-first[k])*i/steps for k in range(3)]
                q=tuple(math.floor(v) for v in point)
                if not all(lo[k]<=q[k]<=hi[k] for k in range(3)):continue
                s=g.standing(q)
                if s['status']=='UNKNOWN':unknown.append(s)
                elif s['status']!='STATIC_STANDING':failures.append(s)
                if prev is not None and prev!=q and not g.edge_clear(prev,q):
                    if not unknown:failures.append(dict(position=q,status='SWEPT_BODY_OBSTRUCTION'))
                prev=q
        results.append(dict(id=case['id'],status='STATIC_FLAT_PATH' if not failures and not unknown else 'UNKNOWN_NATIVE_SHAPE' if unknown else 'STATIC_OBSTRUCTION',failures=failures[:8],unknown=unknown[:4]))
    pool=None
    components=json.loads((a.plan/'components.json').read_text('utf8'))
    for c in components:
        if c.get('kind')=='complete_swimming_facility':
            x,y,z,X,Y,Z=c['water_bounds'];fail=[]
            for xx in range(x,X+1):
                for zz in range(z,Z+1):
                    for yy in range(y,Y+1):
                        st=ghost.get(xx,yy,zz)
                        if st not in ['minecraft:water[level=0]','minecraft:white_concrete','minecraft:blue_concrete','minecraft:quartz_stairs[facing=east,half=bottom,shape=straight,waterlogged=true]','minecraft:ladder[facing=south,waterlogged=true]']:
                            fail.append([xx,yy,zz,st])
            perimeter=[]
            for xx in range(x-1,X+2):perimeter.extend([(xx,72,z-1),(xx,72,Z+1)])
            for zz in range(z,Z+1):perimeter.extend([(x-1,72,zz),(X+1,72,zz)])
            leaks=[list(q) for q in perimeter if ghost.get(*q) in AIR or ghost.get(*q).startswith('minecraft:water')]
            pool=dict(water_length=X-x+1,water_width=Z-z+1,volume_cells=(X-x+1)*(Z-z+1)*(Y-y+1),containment_failures=leaks,unplanned_water_volume_states=fail,swim_motion_native_verified=False)
    report=dict(plan=str(a.plan.resolve()),world=str(a.world.resolve()),forward_sha256=sha(a.plan/'forward.jsonl.gz'),inverse_verified=True,precondition_errors=preconditions,preserved_full_NBT_count=len(preserved),changed_original_BE=changed_original,full_floor_regions=floors,flat_case_status=dict(Counter(r['status'] for r in results)),flat_cases=results,unknown_native_shapes=sorted(g.unknown),pool=pool,world_written=False,native_gameplay_passed=False,visual_passed=False,release_ready=False)
    (a.plan/(a.name+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('exact errors',len(preconditions),'original BE changed',len(changed_original),'floor regions',len(floors),'flat cases',report['flat_case_status'],'unknown native shapes',len(g.unknown),flush=True)
    print('static obstruction IDs',[r['id'].encode('unicode_escape').decode() for r in results if r['status']=='STATIC_OBSTRUCTION'],flush=True)


if __name__=='__main__':main()
