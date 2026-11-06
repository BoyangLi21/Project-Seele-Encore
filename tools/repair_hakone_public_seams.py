"""Restore only newly regressed, unchanged-grade public cells from their source.

The current capture must still match the installed candidate at every repair
cell. Existing regional defects and explicitly redesigned streets are excluded.
"""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from query_blocks import AIR,iter_block_entities
from verify_hakone_network_candidate import PAVEMENT
from install_r53_carrier_trays import stopped_world
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.rail_civil_geometry import columns

EMPTY=AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern'}


def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')


def audit(path):
    with np.load(path/'actual-routes.npz') as f:d={k:f[k] for k in f.files if k!='component'}
    return {(int(x),int(z),int(g)):(bool(full),bool(floor),bool(body)) for x,z,g,full,floor,body in
            zip(d['x'],d['z'],d['grade2'],d['full'],d['floor_ok'],d['body_ok'])}


def build(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);x,z,X,Z=cap['bounds_xz']
    if cap['actors'] or cap['unavailable_chunks']:raise ValueError('Requires FULL actor-free capture')
    before,after=audit(a.before_audit),audit(a.after_audit)
    targets=[]
    for key,value in after.items():
        old=before.get(key)
        if old and old[0] and value[0] and any(old[k] and not value[k] for k in (1,2)):
            if not(x<=key[0]<=X and z<=key[1]<=Z):raise ValueError(('Regression outside captured scope',key))
            targets.append(key)
    if not targets:raise ValueError('No newly regressed public columns')
    a.out.mkdir(exist_ok=False)
    for name in ('source','delta','plan'):(a.out/name).mkdir()
    for f in (a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    for name in ('native-curves.json','catalog.json'):shutil.copy2(a.authority/name,a.out/'plan'/name)
    for name in ('buildings.json','footways.json'):save(a.out/'plan'/name,[])
    with np.load(a.authority/'network.npz') as f:g={k:f[k] for k in f.files}
    gx,gz,_,_=map(int,g['bounds']);area=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1]
    d={k:(v[area].copy() if k!='bounds' else np.array([x,z,X,Z])) for k,v in g.items()};del g
    d['old_ground']=d['ground'].copy();np.savez_compressed(a.out/'plan/network.npz',**d)
    catalog=json.loads((a.authority/'catalog.json').read_text('utf8'))
    curves=json.loads((a.authority/'native-curves.json').read_text('utf8'))['trains']
    indices=[i for i,r in enumerate(curves) if any(x-4<=q[0]<=X+4 and z-4<=q[2]<=Z+4 and -128<=q[1]<310 for q in r['points'])]
    env=columns(curves,indices,max_vertical_spread=None)
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native')
        devices=dict(iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z)))
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](list(devices.values()))}).save(a.out/'captured-devices.dat',gzipped=True)
    launch=load(world);e=Editor(a.out);old=Editor(a.reference);installed=Editor(a.installed);edits=[]
    for px,pz,grade in targets:
        j,i=pz-z,px-x
        if not d['walk'][j,i] or int(d['grade2'][j,i])!=grade:raise ValueError('Authority differs from audited grade')
        floor,slab=road_blocks(grade);floor=int(floor)
        for yy in range(floor,floor+(5 if d['road'][j,i] else 3)):
            p=(px,yy,pz);state=e.state(*p);original=old.state(*p)
            okay=(state.split('[')[0] in PAVEMENT|{'projectseele:period_station_floor'} and ('type=bottom' in state)==bool(slab)) if yy==floor else state.split('[')[0] in EMPTY
            if okay:continue
            was_ok=(original.split('[')[0] in PAVEMENT|{'projectseele:period_station_floor'} and ('type=bottom' in original)==bool(slab)) if yy==floor else original.split('[')[0] in EMPTY
            if not was_ok:raise ValueError(('Pre-existing defect is not an owned regression',p))
            if state!=installed.state(*p) or original!=installed.state(*p,original=True):raise ValueError(('Repair is not the exact installed edit',p))
            if p in devices or launch.chunk_mask(px//16,pz//16)[yy+128,pz%16,px%16]:raise ValueError(('Protected native cell',p))
            if any(all(b[k]<=p[k]<=b[k+3] for k in range(3)) for b in (r['occupied_bounds'] for r in catalog)):raise ValueError(('Occupied parcel',p))
            rail=env.get((px,pz))
            if rail and rail['low']-2<=yy<=rail['high']+4.5:raise ValueError(('Rail reserve',p))
            if yy>floor and not state.split('[')[0].endswith('_leaves'):raise ValueError(('Unexpected new road obstruction',p,state))
            e.put(*p,original);edits.append(dict(pos=list(p),before=state,after=original,kind='floor' if yy==floor else 'foliage clearance'))
    patches=e.save();e.regions.clear()
    save(a.out/'seam-edits.json',edits)
    save(a.out/'manifest.json',dict(world=str(world),bounds_xz=[x,z,X,Z],regions=patches,cells=sum(r['cells'] for r in patches),world_written=False,preserve_native_members=True))
    save(a.out/'functional-check.json',dict(errors=[],regressed_columns=len(targets),edits=len(edits),reference=str(a.reference),installed=str(a.installed),before_audit=str(a.before_audit),after_audit=str(a.after_audit)))
    save(a.out/'launch-protection.json',check_candidate(launch,a.out))
    # Reopen the saved delta and check every declared column in the capture,
    # not just the repaired cells. Old defects remain explicitly counted.
    e=Editor(a.out);errors=[];floor_bad=[];body_bad=[];checked=0
    for j,i in np.argwhere(d['walk']):
        px,pz=int(i+x),int(j+z);h,slab=road_blocks(d['grade2'][j,i]);h=int(h);s=e.state(px,h,pz);checked+=1
        good_floor=s.split('[')[0] in PAVEMENT|{'projectseele:period_station_floor'} and ('type=bottom' in s)==bool(slab)
        good_body=all(e.state(px,yy,pz).split('[')[0] in EMPTY for yy in range(h+1,h+(5 if d['road'][j,i] else 3)))
        if not good_floor:floor_bad.append([px,pz])
        if not good_body:body_bad.append([px,pz])
        prev=before.get((px,pz,int(d['grade2'][j,i])))
        if prev and prev[0] and ((prev[1] and not good_floor) or (prev[2] and not good_body)):errors.append(['new public regression',px,pz])
        if (px,pz,int(d['grade2'][j,i])) in targets:
            if not good_floor or not good_body:errors.append(['repair remains obstructed',px,pz])
            for yy in (h-2,h-1):
                if e.state(px,yy,pz).split('[')[0] in AIR|{'minecraft:light','minecraft:water'}:errors.append(['repair lacks bearing',px,yy,pz])
    actual={}
    for path in (a.out/'delta').glob('*.npz'):
        with np.load(path) as f:q={k:f[k] for k in f.files}
        for n,(cx,cz) in enumerate(q['coordinates']):
            lo,hi=q['ranges'][n:n+2]
            for at,b,v in zip(q['indices'][lo:hi],q['before'][lo:hi],q['after'][lo:hi]):
                p=(int(cx*16+at%16),int(at//256)-128,int(cz*16+(at//16)%16));actual[p]=(str(q['palette'][b]),str(q['palette'][v]))
    if actual!={tuple(r['pos']):(r['before'],r['after']) for r in edits}:errors.append(['unexpected saved delta cells'])
    report=dict(errors=errors,declared_columns=checked,repaired_columns=len(targets),edits=len(edits),existing_floor_defects=floor_bad,existing_headroom_defects=body_bad,devices_preserved=len(devices),native_geometry_unchanged=True)
    save(a.out/'independent-check.json',report);print(json.dumps(report),flush=True)
    if errors:raise ValueError('Public seam verification failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','reference','installed','authority','before-audit','after-audit','out'):p.add_argument('--'+name,type=Path,required=True)
    build(p.parse_args())
