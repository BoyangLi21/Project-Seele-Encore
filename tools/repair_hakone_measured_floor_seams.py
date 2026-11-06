"""Repair finite surveyed surface seams while retaining structural verge blocks.

The source is a union of explicitly captured FULL chunks, never a filled
rectangle. Missing chunks remain unknown and are not available to the editor.
"""
import argparse,json,os,shutil
from pathlib import Path
from collections import defaultdict,Counter,deque
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from query_blocks import AIR,iter_block_entities
from verify_hakone_network_candidate import PAVEMENT
from plan_ashi_landscape_r54 import SOIL
from repair_hakone_underbridge_clearance import health,save
from repair_hakone_fixture_bearings import reserves,conflict
from map_pipeline.launch_protection import load,check_candidate
from install_r53_carrier_trays import stopped_world


def merge_sources(sources,out):
    grouped=defaultdict(list);caps=[]
    for source in sources:
        cap=json.loads((source/'capture.json').read_text('utf8'))
        if cap['actors'] or cap['unavailable_chunks']:raise ValueError('Current FULL actor-free captures required')
        caps.append(cap)
        for p in (source/'source').glob('*.npz'):grouped[p.name].append(p)
    worlds={str(Path(c['world']).resolve()) for c in caps}
    if len(worlds)!=1:raise ValueError('Captures must share a world')
    for name,files in grouped.items():
        if len(files)==1:os.link(files[0],out/'source'/name);continue
        names=[];lookup={};blocks=[];coordinates=[];seen=set()
        for p in files:
            with np.load(p) as f:coords=f['coordinates'];values=f['blocks'];palette=f['palette']
            remap=[]
            for s in map(str,palette):
                if s not in lookup:lookup[s]=len(names);names.append(s)
                remap.append(lookup[s])
            for q in map(tuple,coords):
                if q in seen:raise ValueError(('Overlapping capture',q))
                seen.add(q)
            coordinates.append(coords);blocks.append(np.asarray(remap,np.uint16)[values])
        np.savez_compressed(out/'source'/name,coordinates=np.concatenate(coordinates),blocks=np.concatenate(blocks),palette=np.asarray(names))
    bounds=[min(c['bounds_xz'][0] for c in caps),min(c['bounds_xz'][1] for c in caps),max(c['bounds_xz'][2] for c in caps),max(c['bounds_xz'][3] for c in caps)]
    cap=dict(world=next(iter(worlds)),bounds_xz=bounds,captured_areas=[c['bounds_xz'] for c in caps],actors=[],unavailable_chunks=[],uncaptured_gaps_remain_unknown=True,world_written=False)
    save(out/'capture.json',cap);return Path(cap['world']),bounds


def build(a):
    design=json.loads(a.design.read_text('utf8'));sources=list(map(Path,design['sources']))
    a.out.mkdir(exist_ok=False)
    for name in ('source','delta','plan'):(a.out/name).mkdir()
    world,bounds=merge_sources(sources,a.out);x,z,X,Z=bounds
    with np.load(a.authority/'network.npz') as f:g={k:f[k] for k in f.files}
    gx,gz,_,_=map(int,g['bounds']);ar=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1]
    d={k:(v[ar].copy() if k!='bounds' else np.array(bounds)) for k,v in g.items()};old={k:v.copy() for k,v in d.items()};del g
    for name in ('catalog.json','native-curves.json'):shutil.copy2(a.authority/name,a.out/'plan'/name)
    for name in ('buildings.json','footways.json'):save(a.out/'plan'/name,[])
    catalog=json.loads((a.authority/'catalog.json').read_text('utf8'))
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native');devices={}
        for source in sources:
            c=json.loads((source/'capture.json').read_text('utf8'));l,t,r,b=c['bounds_xz']
            devices.update(iter_block_entities(world,'projectseele:geofront',(l,-128,t),(r,319,b)))
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](list(devices.values()))}).save(a.out/'captured-devices.dat',gzipped=True)
    e=Editor(a.out);known=np.zeros(d['walk'].shape,bool);env=[]
    for source in sources:
        c=json.loads((source/'capture.json').read_text('utf8'));l,t,r,b=c['bounds_xz'];known[t-z:b-z+1,l-x:r-x+1]=True;env.extend(reserves(a.authority,[l,t,r,b]))
    retired=np.zeros_like(known);editable=np.zeros_like(known);paved=set();edits={};guard=load(world);guard_cache={}
    def put(px,y,pz,state,reason):
        p=int(px),int(y),int(pz);j,i=pz-z,px-x;before=e.state(*p,original=True)
        if before==state:return
        if not known[j,i]:raise ValueError(('Uncaptured column',p))
        if before.split('[')[0] not in AIR|SOIL|PAVEMENT:raise ValueError(('Unreviewed object',p,before))
        if p in devices:raise ValueError(('Device',p))
        key=px//16,pz//16
        if key not in guard_cache:guard_cache[key]=guard.chunk_mask(*key)
        if guard_cache[key][y+128,pz%16,px%16] or conflict(p,env):raise ValueError(('Mechanical or native route',p))
        if any(all(b[k]<=p[k]<=b[k+3] for k in range(3)) for b in (r['occupied_bounds'] for r in catalog)):raise ValueError(('Occupied parcel',p))
        e.put(*p,state);edits[p]=dict(pos=list(p),before=before,after=state,reason=reason)
    for row in design['retired']:
        px,h,pz=row['pos'];j,i=pz-z,px-x
        if not old['walk'][j,i] or int(old['grade2'][j,i])!=row['grade2'] or e.state(px,h,pz)!=row['state']:raise ValueError(('Retirement precondition',row))
        for c in catalog:
            q=c.get('approach',c.get('door'))
            if q and abs(q[0]-px)<=3 and abs(q[2]-pz)<=3 and abs(q[1]-(row['grade2']/2+1))<=2:raise ValueError(('Retirement near entrance',c.get('id'),row))
        retired[j,i]=True;editable[j,i]=True
        for key in ('walk','road','marking','tunnel'):d[key][j,i]=False
    for row in design['restore']:
        px,h,pz=row['pos'];j,i=pz-z,px-x
        if not old['walk'][j,i] or int(old['grade2'][j,i])!=row['grade2'] or e.state(px,h,pz)!=row['state']:raise ValueError(('Floor precondition',row))
        paved.add((px,pz));editable[j,i]=True
    for row in design.get('landscape',[]):
        px,y,pz=row['pos'];j,i=pz-z,px-x
        if not retired[j,i] or e.state(px,y,pz)!=row['before']:raise ValueError(('Finite retired paving differs',row))
        put(px,y,pz,row['after'],'restore soil on an isolated road fragment with no destination')
    # One shared junction plane replaces two overlapping, differently levelled
    # stamps. A half-block rise is distributed over five horizontal blocks.
    l,t,r,b=design['junction_box']
    for pz in range(t-10,b+11):
        for px in range(l-10,r+11):
            j,i=pz-z,px-x
            if not d['walk'][j,i]:continue
            distance=max(l-px,0,px-r)+max(t-pz,0,pz-b);target=160-int(np.ceil(distance/5))
            if target>int(d['grade2'][j,i]):d['grade2'][j,i]=target;paved.add((px,pz));editable[j,i]=True
    for px,pz in sorted(paved):
        j,i=pz-z,px-x;h,slab=road_blocks(d['grade2'][j,i]);h=int(h);prior_h=int(road_blocks(old['grade2'][j,i])[0])
        if d['road'][j,i]:material=('projectseele:road_marking_slab' if d['marking'][j,i] else 'projectseele:road_asphalt_slab')+'[type=bottom,waterlogged=false]' if slab else ('minecraft:white_concrete' if d['marking'][j,i] else 'minecraft:black_concrete')
        else:material='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]' if slab else 'minecraft:smooth_stone'
        # Each repaired wearing course has its own continuous bearing; no
        # orphan slab is accepted merely because a nearby cell is supported.
        bearing=next((yy for yy in range(h-1,h-7,-1) if e.state(px,yy,pz).split('[')[0] in SOIL|PAVEMENT and 'type=bottom' not in e.state(px,yy,pz)),None)
        if bearing is None:raise ValueError(('No measured direct bearing',px,pz,h))
        for yy in range(bearing+1,h):put(px,yy,pz,'minecraft:stone','continuous road base')
        put(px,h,pz,material,'measured wearing course or shared junction plane')
        if h<prior_h:raise ValueError('This finite repair never lowers retained structures')
        for yy in range(h+1,h+(5 if d['road'][j,i] else 3)):
            if e.state(px,yy,pz).split('[')[0] not in AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern'}:raise ValueError(('Paving would lose headroom',px,yy,pz))
    patches=e.save();e.regions.clear();d['old_ground']=old['ground'].copy()
    np.savez_compressed(a.out/'plan/network.npz',**d)
    np.savez_compressed(a.out/'finite-authority.npz',bounds=bounds,retired=retired,editable=editable,before_walk=old['walk'],before_grade2=old['grade2'])
    save(a.out/'floor-seam-design.json',design);save(a.out/'floor-seam-edits.json',list(edits.values()))
    save(a.out/'manifest.json',dict(world=str(world),bounds_xz=bounds,regions=patches,cells=sum(r['cells'] for r in patches),world_written=False,preserve_native_members=True))
    save(a.out/'launch-protection.json',check_candidate(guard,a.out))
    # Reopen persisted arrays; check every declared captured street, every
    # edited material, and actual paths from the repaired cells to old streets.
    e=Editor(a.out);errors=[];before=Counter();after=Counter();valid={};old_valid=set();car=set();old_car=set()
    for j,i in np.argwhere(known&(old['walk']|d['walk'])):
        px,pz=int(x+i),int(z+j);h,slab=road_blocks(old['grade2'][j,i]);aa=health(e,(px,pz),int(h),slab,bool(old['road'][j,i]),True)
        for k,key in enumerate(('floor','headroom')):before[key]+=not aa[k]
        if all(aa):old_valid.add((px,pz))
        if all(aa) and old['road'][j,i]:old_car.add((px,pz))
        if retired[j,i]:continue
        hh,ss=road_blocks(d['grade2'][j,i]);bb=health(e,(px,pz),int(hh),ss,bool(d['road'][j,i]))
        for k,key in enumerate(('floor','headroom')):
            after[key]+=not bb[k]
            if aa[k] and not bb[k]:errors.append(['public regression',key,px,pz])
        if all(bb):valid[px,pz]=int(d['grade2'][j,i])
        if all(bb) and d['road'][j,i]:car.add((px,pz))
    def paths(nodes,original,targets,label):
        seen=set();results=[]
        for seed in sorted(targets):
            if seed in seen:continue
            if seed not in nodes:errors.append([label,'invalid authored cell',seed]);continue
            q=deque([seed]);prev={seed:None}
            while q:
                px,pz=q.popleft()
                for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                    v=px+dx,pz+dz
                    if v in nodes and v not in prev and abs(valid[v]-valid[px,pz])<=1:prev[v]=(px,pz);q.append(v)
            seen.update(prev);anchors=(set(prev)&original)-paved
            if len(anchors)<20:errors.append([label,'no substantial old street connection',seed,len(anchors)])
            else:
                goal=min(anchors,key=lambda v:abs(v[0]-seed[0])+abs(v[1]-seed[1]));path=[];p=goal
                while p is not None:path.append([p[0],valid[p]/2+1,p[1]]);p=prev[p]
                results.append(dict(name=label+' '+str(seed),path=path[::-1],retained_connected_columns=len(anchors)))
        return results
    journeys=paths(valid,old_valid,paved,'public')
    car_targets={p for p in paved if d['road'][p[1]-z,p[0]-x]};vehicle=paths(car,old_car,car_targets,'vehicle')
    for row in edits.values():
        if e.state(*row['pos'])!=row['after'] or e.state(*row['pos'],original=True)!=row['before']:errors.append(['finite material readback',row['pos']])
    for p in devices:
        if e.state(*p)!=e.state(*p,original=True):errors.append(['device changed',p])
    for row in design['retired']:
        if not row.get('landscaped') and e.state(*row['pos'])!=row['state']:errors.append(['retained structural verge changed',row['pos']])
    for row in design.get('landscape',[]):
        if e.state(*row['pos'])!=row['after']:errors.append(['retired fragment readback',row['pos']])
    for px,pz in paved:
        h=int(road_blocks(d['grade2'][pz-z,px-x])[0]);s=e.state(px,h-1,pz)
        if s.split('[')[0] not in SOIL|PAVEMENT or 'type=bottom'in s:errors.append(['surface lacks direct bearing',px,h,pz,s])
    report=dict(errors=errors,cells=sum(r['cells'] for r in patches),surveyed_floor_failures=len(design['restore'])+sum(r.get('was_failed',True) for r in design['retired']),restored_surveyed_columns=len(design['restore']),paved_columns=len(paved),retired_false_public_columns=int(retired.sum()),captured_public_columns=int((known&old['walk']).sum()),road_defects_before=dict(before),road_defects_after=dict(after),devices_unchanged=len(devices),new_surface_columns_with_direct_bearing=len(paved),vehicle_journeys=len(vehicle),native_geometry_unchanged=True,world_written=False,whole_map_complete=False)
    for name,value in [('functional-check.json',report),('independent-check.json',report),('street-journeys.json',journeys+vehicle)]:save(a.out/name,value)
    print(json.dumps(report),flush=True)
    if errors:raise ValueError('Finite floor seams failed independent readback')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('authority','design','out'):p.add_argument('--'+n,type=Path,required=True)
    build(p.parse_args())
