"""Retire finite disconnected buried streets and support two entrance forecourts.

The active surface ring must already provide a measured half-step connection.
Original station rooms, native geometry, devices, houses and benches are retained.
"""
import argparse,json,os,shutil
from pathlib import Path
from collections import Counter,deque
import numpy as np
import nbtlib
from scipy.ndimage import label,binary_dilation
from author_hakone_lakefront import Editor
from query_blocks import AIR,iter_block_entities
from plan_ashi_landscape_r54 import SOIL
from verify_hakone_network_candidate import PAVEMENT
from hakone_earthworks import road_blocks
from repair_hakone_underbridge_clearance import health,save
from repair_hakone_fixture_bearings import reserves,conflict
from map_pipeline.launch_protection import load,check_candidate
from install_r53_carrier_trays import stopped_world


def journey(e,d,start,goal):
    x,z,X,Z=map(int,d['bounds']);good=np.zeros(d['walk'].shape,bool)
    for j,i in np.argwhere(d['walk']):
        h,slab=road_blocks(d['grade2'][j,i]);good[j,i]=all(health(e,(int(x+i),int(z+j)),int(h),slab,bool(d['road'][j,i])))
    a=start[0]-x,start[1]-z;b=goal[0]-x,goal[1]-z
    previous={a:None}if good[a[1],a[0]]else{};q=deque(previous)
    while q and b not in previous:
        i,j=q.popleft()
        for di,dj in((1,0),(-1,0),(0,1),(0,-1)):
            I,J=i+di,j+dj;v=I,J
            if 0<=I<good.shape[1]and 0<=J<good.shape[0]and good[J,I]and abs(int(d['grade2'][J,I])-int(d['grade2'][j,i]))<=1 and v not in previous:
                previous[v]=(i,j);q.append(v)
    path=[]
    if b in previous:
        p=b
        while p is not None:
            i,j=p;path.append([i+x,float(d['grade2'][j,i]/2+1),j+z]);p=previous[p]
        path.reverse()
    return path


def build(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);bounds=cap['bounds_xz'];x,z,X,Z=bounds
    if bounds!=[112,656,351,943]or cap['actors']or cap['unavailable_chunks']:raise ValueError('Current FULL South station capture required')
    with np.load(a.authority/'network.npz')as f:g={k:f[k]for k in f.files}
    gx,gz,_,_=map(int,g['bounds']);ar=np.s_[z-gz:Z-gz+1,x-gx:X-gx+1]
    d={k:(v[ar].copy()if k!='bounds'else np.array(bounds))for k,v in g.items()};del g
    old={k:v.copy()for k,v in d.items()}
    with np.load(a.source/'measured.npz')as f:soil=f['top']
    e=Editor(a.source);replacement=journey(e,d,(210,790),(250,861))
    if len(replacement)!=306:raise ValueError('Verified surface ring has changed')
    buried=d['walk']&(soil-d['grade2']/2>12);groups,n=label(buried,np.ones((3,3),int));retired=np.zeros(buried.shape,bool);retirements=[]
    for px,pz,count,bb in [(210,810,831,[204,791,250,861]),(240,682,278,[222,672,252,691]),(260,856,50,[255,854,266,859])]:
        k=int(groups[pz-z,px-x])
        if k==0:raise ValueError('Finite buried street seed changed')
        m=groups==k;jj,ii=np.nonzero(m);box=[int(ii.min()+x),int(jj.min()+z),int(ii.max()+x),int(jj.max()+z)]
        if len(ii)!=count or box!=bb:raise ValueError(('Buried footprint changed',box,len(ii)))
        if m[[0,-1],:].any()or m[:,[0,-1]].any():raise ValueError('Cannot retire cropped road')
        boundary=[]
        for j,i in zip(jj,ii):
            for dj in(-1,0,1):
                for di in(-1,0,1):
                    I,J=i+di,j+dj
                    if 0<=I<m.shape[1]and 0<=J<m.shape[0]and d['walk'][J,I]and not m[J,I]:boundary.append(abs(int(d['grade2'][J,I])-int(d['grade2'][j,i]))/2)
        if boundary and min(boundary)<=2:raise ValueError('Road still connects at a usable height')
        retired|=m;retirements.append(dict(bounds=bb,columns=count,minimum_boundary_height_gap=min(boundary)if boundary else None))
    catalog=json.loads((a.authority/'catalog.json').read_text('utf8'));volumes=json.loads((a.authority/'station-volumes.json').read_text('utf8'))
    for row in catalog:
        p=row.get('approach',row.get('door'))
        if p and x<=p[0]<=X and z<=p[2]<=Z and p[1]<155:
            i,j=round(p[0])-x,round(p[2])-z
            if retired[max(0,j-3):j+4,max(0,i-3):i+4].any():raise ValueError(('Retired road serves a catalog destination',row['id']))
    a.out.mkdir(exist_ok=False)
    for name in('source','delta','plan'):(a.out/name).mkdir()
    for f in(a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    for name in('native-curves.json','catalog.json'):shutil.copy2(a.authority/name,a.out/'plan'/name)
    for name in('buildings.json','footways.json'):save(a.out/'plan'/name,[])
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native');devices=dict(iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z)))
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound](list(devices.values()))}).save(a.out/'captured-devices.dat',gzipped=True)
    e=Editor(a.out);guard=load(world);env=reserves(a.authority,bounds);edits={};paved=np.zeros(retired.shape,bool);seats=[]
    def put(px,y,pz,state,kind):
        p=int(px),int(y),int(pz);before=e.state(*p,original=True)
        if state==before:return
        if p in devices or guard.chunk_mask(px//16,pz//16)[y+128,pz%16,px%16]:raise ValueError(('Protected device or launch volume',p))
        if conflict(p,env):raise ValueError(('Native clearance',p,conflict(p,env)))
        for box in volumes+[r['occupied_bounds']for r in catalog]:
            if all(box[k]<=p[k]<=box[k+3]for k in range(3)):raise ValueError(('Retained occupied volume',p))
        if before.split('[')[0]not in AIR|SOIL|PAVEMENT|{'minecraft:light'}:raise ValueError(('Retained structure',p,before))
        if p in edits and edits[p]['after']!=state:raise ValueError(('Overlapping design',p))
        edits[p]=dict(pos=list(p),before=before,after=state,kind=kind);e.put(*p,state)
    for j,i in np.argwhere(retired):
        px,pz=int(x+i),int(z+j);h,_=road_blocks(d['grade2'][j,i]);h=int(h)
        for y in range(h-1,h+5):
            s=e.state(px,y,pz).split('[')[0]
            if s in PAVEMENT|AIR|{'minecraft:light'}:put(px,y,pz,'minecraft:stone','backfill finite obsolete road')
            elif s not in SOIL:raise ValueError(('Unknown buried road object',px,y,pz,s))
    for key in('walk','road','marking','tunnel'):d[key][retired]=False
    for xa,za,xb,zb,h in[(215,757,218,765,159),(264,805,276,807,174)]:
        for px in range(xa,xb+1):
            for pz in range(za,zb+1):
                j,i=pz-z,px-x;paved[j,i]=True;floor=int(h);slab=(px==274 and pz==807)if h==174 else False
                # Adjacent existing footway retains its precise half-height.
                if old['walk'][j,i]and (px,pz)!=(274,807):
                    floor,slab=road_blocks(old['grade2'][j,i]);floor=int(floor)
                if floor-int(soil[j,i])>5:raise ValueError(('Forecourt requires a separate hillside design',px,pz,floor,int(soil[j,i])))
                for y in range(int(soil[j,i])+1,floor):put(px,y,pz,'minecraft:stone_bricks','continuous forecourt foundation')
                put(px,floor,pz,'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'if slab else'minecraft:smooth_stone','forecourt paving or half-step seam')
                # Seats retain their existing payload and are excluded from the
                # declared walking area. The walkable aisle passes in front.
                if all(e.state(px,y,pz).split('[')[0]in AIR|{'minecraft:light'}for y in(floor+1,floor+2)):
                    d['walk'][j,i]=True;d['grade2'][j,i]=floor*2-int(slab);d['road'][j,i]=False;d['marking'][j,i]=False;d['tunnel'][j,i]=False
                elif old['walk'][j,i]:raise ValueError(('Existing public space obstructed',px,pz))
                else:seats.append([px,floor+1,pz])
                d['ground'][j,i]=min(int(d['ground'][j,i]),floor-1)
    # The original rear public walk projects one metre past its retaining edge.
    # Keep its entire walking width. A continuous two-metre concrete cantilever
    # supports that walk and a guardrail just outside it, tied to the soil apron.
    for px in range(264,274):
        if d['walk'][809-z,px-x]or e.state(px,174,808)!='minecraft:smooth_stone':raise ValueError('Retained rear lip changed')
        if e.state(px,173,807).split('[')[0]in AIR:raise ValueError('Rear beam lacks measured landward bearing')
        for pz in(808,809):put(px,173,pz,'minecraft:stone_bricks','two-metre cantilever beam tied to forecourt foundation')
        put(px,174,809,'minecraft:stone_bricks','guardrail edge beam outside retained public walk')
        put(px,175,809,'minecraft:polished_andesite'if px in(264,273)else'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]','rear forecourt guardrail')
    patches=e.save();e.regions.clear();e=Editor(a.out)
    d['old_ground']=old['ground'].copy();np.savez_compressed(a.out/'plan/network.npz',**d)
    np.savez_compressed(a.out/'finite-authority.npz',bounds=bounds,retired=retired,editable=retired|paved,before_grade2=old['grade2'],before_walk=old['walk'])
    errors=[];before=Counter();after=Counter()
    for j,i in np.argwhere(old['walk']):
        h,s=road_blocks(old['grade2'][j,i]);p=int(x+i),int(z+j);v=health(e,p,int(h),s,bool(old['road'][j,i]),True)
        if retired[j,i]:continue
        h,s=road_blocks(d['grade2'][j,i]);w=health(e,p,int(h),s,bool(d['road'][j,i]))
        for k,name in enumerate(('floor','headroom')):
            before[name]+=not v[k];after[name]+=not w[k]
            if v[k]and not w[k]:errors.append(['public regression',name,*p])
    for j,i in np.argwhere(paved):
        px,pz=int(x+i),int(z+j);h=int(174 if px>=264 else 159)
        if old['walk'][j,i]and (px,pz)!=(274,807):h=int(road_blocks(old['grade2'][j,i])[0])
        for y in range(int(soil[j,i])+1,h):
            if e.state(px,y,pz).split('[')[0]in AIR:errors.append(['forecourt bearing gap',px,y,pz])
        if d['walk'][j,i]:
            h,slab=road_blocks(d['grade2'][j,i])
            if not all(health(e,(px,pz),int(h),slab,False)):errors.append(['forecourt path invalid',px,pz])
    paths=[]
    for name,start,end in [('retained surface ring',(210,790),(250,861)),('western bench aisle',(214,765),(215,759)),('southern bench aisle',(276,807),(269,806)),('southern front door approach',(276,807),(272,807))]:
        path=journey(e,d,start,end);paths.append(dict(name=name,path=path))
        if not path:errors.append(['surface journey disconnected',name])
    for p in devices:
        if e.state(*p)!=e.state(*p,original=True):errors.append(['device changed',*p])
    for p in seats:
        if e.state(*p)!=e.state(*p,original=True):errors.append(['bench or original furnishing changed',*p])
    for j,i in np.argwhere(retired):
        h,_=road_blocks(old['grade2'][j,i]);px,pz=int(x+i),int(z+j)
        if e.state(px,int(h),pz).split('[')[0]in PAVEMENT:errors.append(['obsolete street floor remains',px,pz])
    actual={}
    for f in(a.out/'delta').glob('*.npz'):
        with np.load(f)as q:v={k:q[k]for k in q.files}
        for n,(cx,cz)in enumerate(v['coordinates']):
            lo,hi=v['ranges'][n:n+2]
            for at,b,c in zip(v['indices'][lo:hi],v['before'][lo:hi],v['after'][lo:hi]):actual[(int(cx*16+at%16),int(at//256)-128,int(cz*16+at//16%16))]=(str(v['palette'][b]),str(v['palette'][c]))
    if actual!={p:(r['before'],r['after'])for p,r in edits.items()}:errors.append(['unexpected saved edits'])
    report=dict(errors=errors,cells=sum(p['cells']for p in patches),retired_columns=int(retired.sum()),retirements=retirements,forecourt_columns=int(paved.sum()),new_public_columns=int((d['walk']&~old['walk']).sum()),devices_preserved=len(devices),retained_public_before=dict(before),retained_public_after=dict(after),native_geometry_unchanged=True,whole_map_complete=False)
    for name,data in [('functional-check.json',report),('independent-check.json',report),('street-journeys.json',paths),('street-edits.json',list(edits.values())),('street-design.json',dict(retirements=retirements,forecourts=[[215,159,757,218,159,765],[264,174,805,276,174,807]],surface_ring_replacement=replacement)),('manifest.json',dict(world=str(world),bounds_xz=bounds,regions=patches,cells=report['cells'],world_written=False,preserve_native_members=True)),('launch-protection.json',check_candidate(guard,a.out))]:save(a.out/name,data)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if errors:raise ValueError('Street reconstruction failed independent checks')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','authority','out'):p.add_argument('--'+n,type=Path,required=True)
    build(p.parse_args())
