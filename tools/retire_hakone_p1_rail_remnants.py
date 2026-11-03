"""Retire exact surviving R07 P1 railway members outside present facilities.

The discontinued line's original operation archive identifies finite members.
Current public plazas, buildings, stations, native curves and actors take
precedence. Later materials and all devices are retained. This is an offline
candidate, not an installer or a general material-based demolition pass.
"""
import argparse,collections,gzip,json,os,shutil
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt
from author_hakone_lakefront import Editor
from query_blocks import AIR,iter_block_entities
from install_r53_carrier_trays import stopped_world
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.launch_earthworks import ground
from repair_hakone_surface_ownership import load_grid,sampled
from hakone_earthworks import road_blocks

OWNERS={'r07/P1/'+s for s in ('rail_bed','piers','pole','catenary','depot_piers')}

def run(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);x,z,X,Z=cap['bounds_xz']
    with gzip.open(a.original,'rt',encoding='utf8')as f:ops=json.load(f)
    # Later original operations can reuse a rail member for station geometry.
    # Resolve operation order before admitting any obsolete member.
    expected={};owners={}
    for row in ops:
        if 'box'not in row:continue
        l,y,t,r,Y,b=row['box']
        for px in range(max(l,x),min(r,X)+1):
            for pz in range(max(t,z),min(b,Z)+1):
                for py in range(y,Y+1):
                    p=(px,py,pz)
                    if row['owner']in OWNERS:expected[p]=row['state'];owners[p]=row['owner']
                    elif p in expected:expected.pop(p);owners.pop(p)
    a.out.mkdir(parents=True,exist_ok=False)
    for n in ('source','delta','plan'):(a.out/n).mkdir()
    for f in (a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    with stopped_world(world):
        native=json.loads((world/'native_transit_r28.json').read_text('utf-8-sig'))
        if any(r['id']==-5325811690914780106 for r in native['platforms']):raise ValueError('P1 platform is still commissioned')
        shutil.copytree(world/'mtr',a.out/'preserved-native')
        devices={p for p,t in iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z))}
    with np.load(a.source/'measured.npz')as f:old=f['top']
    e=Editor(a.out);launch=load(world);masks={};kept=collections.Counter();removed=collections.Counter();changed=[]
    boxes=[]
    for r in json.loads((a.authority/'catalog.json').read_text('utf8')):
        if 'occupied_bounds'in r:
            b=r['occupied_bounds'];boxes.append([b[0]-2,-128,b[2]-2,b[3]+2,b[4]+2,b[5]+2])
    for b in json.loads((a.authority/'station-volumes.json').read_text('utf8')):boxes.append([b[0]-2,-128,b[2]-2,b[3]+2,b[4]+2,b[5]+2])
    for r in json.loads((a.authority/'installed-public-spaces.json').read_text('utf8')):
        b=r.get('finite_bounds',r.get('bounds'));boxes.append([b[0]-1,-128,b[2]-1,b[3]+1,b[4]+2,b[5]+1])
    # The current P1 deck has become a supported public plaza. Its complete
    # load path and street connection remain, including original track piers
    # which now carry the new beams.
    boxes.append([438,-128,449,558,115,505])
    for actor in cap['actors']:
        p=actor['pos'];boxes.append([p[0]-10,p[1]-4,p[2]-10,p[0]+10,p[1]+10,p[2]+10])
    curves=json.loads((a.authority/'native-curves.json').read_text('utf8'))
    points=np.concatenate([r['points']for r in curves['trains']]);tree=cKDTree(points[:,[0,2]])
    zz,xx=np.mgrid[z:Z+1,x:X+1];public=[]
    for C in a.accepted:
        d=load_grid(C/'plan/network.npz');walk=sampled(d,'walk',xx,zz).astype(bool);grade=sampled(d,'grade2',xx,zz)
        distance,near=distance_transform_edt(~walk,return_indices=True);level=grade[tuple(near)]/2
        public.append((distance<=3,level))
    # A removed pier should reveal the surrounding hill, not a narrow slot.
    # Estimate its soil datum outside the complete original footprint.
    footprint=np.zeros(old.shape,bool)
    for px,py,pz in expected:footprint[pz-z,px-x]=True
    _,near=distance_transform_edt(footprint,return_indices=True)
    fitted=old[tuple(near)]
    for p,before in expected.items():
        px,py,pz=p;actual=e.state(*p)
        if actual!=before:kept['later_or_already_retired_state']+=1;continue
        if p in devices:kept['device']+=1;continue
        if any(all(b[i]<=p[i]<=b[i+3]for i in range(3))for b in boxes):kept['present_building_or_public_bearing']+=1;continue
        dist,idx=tree.query([px+.5,pz+.5]);ry=points[idx,1]
        if dist<=7 and ry-12<=py<=ry+9:kept['native_train_swept_volume']+=1;continue
        if any(mask[pz-z,px-x]and h[pz-z,px-x]-5<=py<=h[pz-z,px-x]+8 for mask,h in public):kept['current_street']+=1;continue
        key=px//16,pz//16
        if key not in masks:masks[key]=launch.chunk_mask(*key)
        if masks[key][py+128,pz%16,px%16]:kept['launch_mechanism']+=1;continue
        h=int(fitted[pz-z,px-x]);after='minecraft:air'if py>h else'minecraft:grass_block[snowy=false]'if py==h else'minecraft:dirt'if py>=h-3 else'minecraft:stone'
        e.put(*p,after);changed.append(dict(pos=p,before=before,after=after,owner=owners[p]));removed[owners[p]]+=1
    regions=e.save();actual=ground(Editor(a.out),cap['bounds_xz']);empty=np.zeros(old.shape,bool)
    np.savez_compressed(a.out/'plan/network.npz',bounds=cap['bounds_xz'],ground=actual,old_ground=old,road=empty,walk=empty,grade2=np.zeros(old.shape,np.int16),marking=empty,tunnel=empty)
    report=dict(errors=[],original_platform_retired=True,original_operation_archive=str(a.original),admitted_original_cells=len(expected),changed_cells=len(changed),removed_by_owner=dict(removed),retained=dict(kept),present_plaza_and_station_bearings_preserved=True,actors_changed=0,devices_changed=0,visual_verified=False,remaining='later material changes, complete current street network and old harbour require separate reconstruction')
    for name,value in [('functional-check.json',report),('manifest.json',dict(world=str(world),bounds_xz=cap['bounds_xz'],regions=regions,cells=sum(r['cells']for r in regions),world_written=False,progress_files_written=[])),('launch-protection.json',check_candidate(launch,a.out))]:(a.out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')
    with gzip.open(a.out/'exact-retirements.json.gz','wt',encoding='utf8')as f:json.dump(changed,f,ensure_ascii=False)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if not changed:raise ValueError('No exact original retired members')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','authority','original','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--accepted',type=Path,action='append',required=True)
    run(p.parse_args())
