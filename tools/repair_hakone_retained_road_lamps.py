"""Seat whole original R07 approach lamps beside the current saved road.

This follows an offline retirement candidate before recipes are generated.
Only uniquely identified complete light heads may move; every current light
state and surviving post member is retained. Missing air-only post members
are restored from the original six-block stem. No device/entity is touched.
"""
import argparse,gzip,json,collections
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree
from author_hakone_lakefront import Editor
from query_blocks import AIR,iter_block_entities
from plan_ashi_landscape_r54 import SOIL
from repair_hakone_surface_ownership import load_grid,sampled
from map_pipeline.launch_earthworks import ground
from map_pipeline.launch_protection import load,check_candidate
from install_r53_carrier_trays import stopped_world
from hakone_earthworks import road_blocks

def cells(b):
    return [(x,y,z)for x in range(b[0],b[3]+1)for y in range(b[1],b[4]+1)for z in range(b[2],b[5]+1)]

def run(a):
    C=a.candidate;cap=json.loads((C/'capture.json').read_text('utf8'));W=Path(cap['world']);x,z,X,Z=cap['bounds_xz'];e=Editor(C)
    with gzip.open(a.original,'rt',encoding='utf8')as f:ops=json.load(f)
    posts=[r for r in ops if r.get('owner')=='r07/port_road/lamp_post'];heads=[r for r in ops if r.get('owner')=='r07/port_road/lamp']
    with np.load(a.source/'measured.npz')as f:soil=f['top']
    d=load_grid(a.authority/'network.npz');zz,xx=np.mgrid[z:Z+1,x:X+1];road=sampled(d,'road',xx,zz).astype(bool);walk=sampled(d,'walk',xx,zz).astype(bool);g=sampled(d,'grade2',xx,zz)
    dist,near=distance_transform_edt(~road,return_indices=True);rail=json.loads((a.authority/'native-curves.json').read_text('utf8'));pts=np.concatenate([r['points']for r in rail['trains']]);tree=cKDTree(pts[:,[0,2]])
    launch=load(W);masks={};boxes=[]
    for r in json.loads((a.authority/'catalog.json').read_text('utf8')):
        if 'occupied_bounds'in r:boxes.append(r['occupied_bounds'])
    boxes+=json.loads((a.authority/'station-volumes.json').read_text('utf8'))
    with stopped_world(W):devices={p for p,t in iter_block_entities(W,'projectseele:geofront',(x,-128,z),(X,319,Z))}
    def guarded(p):
        px,py,pz=p
        if not(x<=px<=X and z<=pz<=Z and -128<=py<320):return True
        if p in devices or any(all(b[i]-1<=p[i]<=b[i+3]+1 for i in range(3))for b in boxes):return True
        key=px//16,pz//16
        if key not in masks:masks[key]=launch.chunk_mask(*key)
        if masks[key][py+128,pz%16,px%16]:return True
        distance,idx=tree.query([px+.5,pz+.5])
        if distance<6 and pts[idx,1]-5<=py<=pts[idx,1]+9:return True
        return any(abs(px-r['pos'][0])<8 and abs(pz-r['pos'][2])<8 and r['pos'][1]-4<=py<=r['pos'][1]+8 for r in cap['actors'])
    result=[];installed=[]
    for post in posts:
        b=post['box'];px,py,pz=b[:3]
        if not(x+16<=px<=X-16 and z+16<=pz<=Z-16):continue
        head=next(r for r in heads if r['box'][0]==px);source_pc=cells(b);source_hc=cells(head['box']);matches=[]
        # The later R07 roadside adjustment shifted lamps two blocks outward.
        # Admit only a unique COMPLETE light head in that small vicinity with
        # an unchanged or air-only stem. An isolated concrete match is rejected.
        for dx in range(-3,4):
            for dz in range(-3,4):
                pc=[(p[0]+dx,p[1],p[2]+dz)for p in source_pc];hc=[(p[0]+dx,p[1],p[2]+dz)for p in source_hc]
                original={p:e.state(*p)for p in pc+hc}
                if all(original[p].split('[')[0]==head['state']for p in hc)and all(original[p].split('[')[0]in AIR|{post['state']}for p in pc):matches.append((dx,dz,pc,hc,original))
        if len(matches)!=1:result.append(dict(original=[px,py,pz],action='retain later, incomplete or ambiguous fixture',complete_matches=len(matches)));continue
        dx,dz,pc,hc,original=matches[0];px+=dx;pz+=dz
        missing_posts=sum(original[p].split('[')[0]in AIR for p in pc)
        if any(guarded(p)for p in original):result.append(dict(original=[px,py,pz],action='retain current protected facility'));continue
        if missing_posts==0 and e.state(px,py-1,pz).split('[')[0]not in AIR:
            result.append(dict(original=[px,py,pz],action='retain currently supported fixture'));continue
        choices=[]
        for dz in range(-12,13):
            for dx in range(-12,13):
                q,r=px+dx,pz+dz;j,i=r-z,q-x;h=int(soil[j,i])
                if walk[j,i]or not(3<=dist[j,i]<=9)or not(-125<h<300):continue
                nj,ni=near[:,j,i];floor,slab=road_blocks(g[nj,ni]);floor=int(floor);feet=floor+(.5 if slab else 1)
                if abs(h+1-feet)>2:continue
                roadstate=e.state(int(ni+x),floor,int(nj+z))
                if roadstate.split('[')[0]not in {'minecraft:black_concrete','minecraft:white_concrete','projectseele:road_asphalt_slab','projectseele:road_marking_slab','minecraft:polished_blackstone_slab'}:continue
                if any(e.state(int(ni+x),floor+k,int(nj+z)).split('[')[0]not in AIR for k in range(1,5)):continue
                vx,vz=int(ni+x-q),int(nj+z-r)
                ax,az=(int(np.sign(vx)),0)if abs(vx)>abs(vz)else(0,int(np.sign(vz)))
                target={ (q,h+k,r):post['state']if original[pc[k-1]].split('[')[0]in AIR else original[pc[k-1]] for k in range(1,7)}
                # Keep all current light states; orient the three-block arm
                # toward the actual carriageway, above its vehicle clearance.
                for k,p in enumerate(sorted(hc,key=lambda p:abs(p[2]-pz))):target[q+ax*k,h+7,r+az*k]=original[p]
                if any(guarded(p)or(e.state(*p).split('[')[0]not in AIR and p not in original)for p in target):continue
                footing=[(q,y,r)for y in range(h-2,h+1)]
                if any(guarded(p)or e.state(*p).split('[')[0]not in SOIL for p in footing):continue
                choices.append((dx*dx+dz*dz+abs(h+1-feet)*4,(q,h,r),target,footing))
        if not choices:
            result.append(dict(original=[px,py,pz],action='retain for complete street reconstruction',reason='no unoccupied supported present roadside within 12 blocks'));continue
        _,base,target,footing=min(choices,key=lambda c:c[0])
        for p in original:e.put(*p,'minecraft:air')
        for p in footing:e.put(*p,'minecraft:polished_andesite')
        for p,s in target.items():e.put(*p,s)
        installed.append((base,target,footing));result.append(dict(original=[px,py,pz],action='relocate complete current fixture',base=list(base),delta=[base[0]-px,base[1]+1-py,base[2]-pz],original_cells=sum(s.split('[')[0]not in AIR for s in original.values()),reconstructed_missing_post_cells=missing_posts,fixture_cells=len(target),foundation_cells=len(footing)))
    regions=e.save();check=Editor(C);errors=[]
    for base,target,footing in installed:
        for p,s in target.items():
            if check.state(*p)!=s:errors.append(['lamp readback',p])
        for p in footing:
            if check.state(*p)!='minecraft:polished_andesite':errors.append(['lamp foundation',p])
    report=json.loads((C/'functional-check.json').read_text('utf8'));report['errors']+=errors;report['road_lamps']=result;report['complete_lamps_reseated']=len(installed);report['visual_verified']=False
    actual=ground(Editor(C),cap['bounds_xz'])
    with np.load(C/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    d['ground']=actual;np.savez_compressed(C/'plan/network.npz',**d)
    manifest=json.loads((C/'manifest.json').read_text('utf8'));manifest.update(regions=regions,cells=sum(r['cells']for r in regions))
    report.setdefault('retired_railway_cells',report['changed_cells']);report['changed_cells']=manifest['cells']
    for name,value in [('manifest.json',manifest),('functional-check.json',report),('launch-protection.json',check_candidate(launch,C)),('road-lamps.json',result)]:(C/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(cells=manifest['cells'],lamps=len(installed),decisions=result,errors=errors),ensure_ascii=False),flush=True)
    if errors:raise ValueError('Lamp verification failed')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('candidate','source','authority','original'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
