"""Give installed natural shores continuous, world-aligned sand/gravel patches.

Only sand and gravel already inside reviewed coastal footprints may change.
The exact solid shape, water, current heights and retained construction stay
unchanged. This does not claim completion of old structural support defects.
"""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
from scipy.ndimage import map_coordinates,distance_transform_edt
from author_hakone_lakefront import Editor
from install_r53_carrier_trays import stopped_world
from map_pipeline.launch_protection import load,check_candidate
from plan_ashi_landscape_r54 import SOIL
from query_blocks import AIR

YY=np.arange(-128,320)[:,None,None]
MATERIALS={'minecraft:sand','minecraft:gravel'}

def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')

def sand_pattern(bounds,ground):
    x,z,X,Z=map(int,bounds)
    if not(-16384<=x<=X<=16384 and -16384<=z<=Z<=16384):
        raise ValueError('Coastal material field exceeds its explicit world frame')
    zz,xx=np.mgrid[z:Z+1,x:X+1]
    # Fixed world frame and generator: separate captures sample the same field.
    # Two spatial scales avoid the former repeated rows of round sand spots.
    rng=np.random.default_rng(7112026)
    broad=map_coordinates(rng.random((513,513)),[(zz+16384)/64,(xx+16384)/64],order=3,mode='nearest')
    detail=map_coordinates(rng.random((2049,2049)),[(zz+16384)/16,(xx+16384)/16],order=1,mode='nearest')
    threshold=.60+.04*np.tanh((ground.astype(float)+82)/4)
    return .8*broad+.2*detail>threshold

def scope(bounds,coasts,authority,programme):
    x,z,X,Z=map(int,bounds);active=np.zeros((Z-z+1,X-x+1),bool)
    for C in coasts:
        with np.load(C/'beach-design.npz')as f:
            ox,oz,oX,oZ=map(int,f['bounds']);mask=f['active']
        if not(x<=ox<oX<=X and z<=oz<oZ<=Z):raise ValueError('Complete installed shore footprint required')
        active[oz-z:oZ-z+1,ox-x:oX-x+1]|=mask
    with np.load(authority/'network.npz')as f:
        ox,oz,oX,oZ=map(int,f['bounds'])
        if not(ox<=x<X<=oX and oz<=z<Z<=oZ):raise ValueError('Authority does not cover material scope')
        public=f['walk'][z-oz:Z-oz+1,x-ox:X-ox+1].copy()
    with np.load(programme/'watercourse-reference.npz')as f:
        ox,oz,oX,oZ=map(int,f['bounds']);river=f['river'][z-oz:Z-oz+1,x-ox:X-ox+1]
    zz,xx=np.mgrid[z:Z+1,x:X+1]
    port=(xx>=3040)&(xx<=3360)&(zz>=960)&(zz<=1216)
    active&=~public&~port&(distance_transform_edt(~river)>1)
    return active,public

def prepare(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);bounds=cap['bounds_xz']
    if cap['unavailable_chunks']:raise ValueError('Complete current FULL source required')
    with np.load(a.source/'measured.npz')as f:ground=f['top'];full=f['full']
    if not full.all():raise ValueError('Unknown material source columns')
    active,public=scope(bounds,a.coast,a.authority,a.programme);sand=sand_pattern(bounds,ground)
    x,z,X,Z=map(int,bounds);a.out.mkdir(parents=True,exist_ok=False)
    for folder in('source','delta'):(a.out/folder).mkdir()
    for f in(a.source/'source').glob('*.npz'):os.link(f,a.out/'source'/f.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native');guard=load(world)
    e=Editor(a.out)
    for file in sorted((a.out/'source').glob('*.npz')):
        rx,rz=map(int,file.stem.split('.')[1:])
        l,t,rgt,bt=max(x,rx*512),max(z,rz*512),min(X,rx*512+511),min(Z,rz*512+511)
        if not active[t-z:bt-z+1,l-x:rgt-x+1].any():continue
        r=e.region(rx*512,rz*512)
        for name in sorted(MATERIALS):
            if name not in r['ids']:r['ids'][name]=len(r['names']);r['names'].append(name)
        permitted=np.isin(np.asarray(r['names']),list(MATERIALS))
        for(cx,cz),v in zip(r['coords'],r['after']):
            q=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16]
            if not active[q].any():continue
            desired=np.where(sand[q],r['ids']['minecraft:sand'],r['ids']['minecraft:gravel'])
            use=active[q]&(YY<=ground[q])&(YY>=ground[q]-2)&permitted[v]
            change=use&(v!=desired)
            if np.any(change&guard.chunk_mask(int(cx),int(cz))):raise ValueError('Material change intersects retained launch volume')
            v[change]=np.broadcast_to(desired,v.shape)[change]
        e.save();e.regions.clear();print('Refined coastal materials',file.name,flush=True)
    records=e.save()
    np.savez_compressed(a.out/'material-design.npz',bounds=bounds,ground=ground,active=active,public=public,sand=sand)
    save(a.out/'manifest.json',dict(world=str(world),bounds_xz=bounds,regions=records,cells=sum(r['cells']for r in records),
        preserve_native_members=True,coastal_materials=dict(source=str(a.source),coasts=list(map(str,a.coast)),
        authority=str(a.authority),programme=str(a.programme),full_chunks=cap['chunk_statuses']['full'],
        eligible_columns=int(active.sum()),world_aligned_materials=True,geometry_change_allowed=False),world_written=False))
    save(a.out/'functional-check.json',dict(errors=['Independent coastal material verification pending'],world_written=False))
    save(a.out/'launch-protection.json',check_candidate(guard,a.out))
    print('Prepared material-only candidate:',sum(r['cells']for r in records),'cells; no world writes.',flush=True)

def verify(C):
    m=json.loads((C/'manifest.json').read_text('utf8'));spec=m['coastal_materials']
    with np.load(C/'material-design.npz')as f:d={k:f[k]for k in f.files}
    active,public=scope(d['bounds'],list(map(Path,spec['coasts'])),Path(spec['authority']),Path(spec['programme']))
    errors=[]
    if not np.array_equal(active,d['active'])or not np.array_equal(public,d['public']):errors.append(['changed-scope'])
    if np.any(active&public):errors.append(['public-intersection'])
    x,z,X,Z=map(int,d['bounds']);e=Editor(C);cells=chunks=columns=changed_chunks=0
    for file in sorted((C/'source').glob('*.npz')):
        if not(C/'delta'/file.name).exists():
            with np.load(file)as f:chunks+=len(f['coordinates'])
            continue
        rx,rz=map(int,file.stem.split('.')[1:]);r=e.region(rx*512,rz*512);names=np.asarray(r['names'])
        base=np.asarray([n.split('[')[0]for n in names]);permitted=np.isin(names,list(MATERIALS));soil=np.isin(base,list(SOIL))
        water_lookup=base=='minecraft:water';air_lookup=np.isin(base,list(AIR))
        for(cx,cz),before,after in zip(r['coords'],r['before'],r['after']):
            q=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16];changed=before!=after
            cells+=int(changed.sum());chunks+=1;columns+=int(changed.any(0).sum())
            if not changed.any():continue
            changed_chunks+=1
            if np.any(changed&(~active[q]|(YY>d['ground'][q])|(YY<d['ground'][q]-2))):errors.append(['unauthorized-cell',int(cx),int(cz)])
            if np.any(changed&(~permitted[before]|~permitted[after])):errors.append(['non-material-change',int(cx),int(cz)])
            desired=np.where(d['sand'][q],r['ids']['minecraft:sand'],r['ids']['minecraft:gravel'])
            if np.any(changed&(after!=desired)):errors.append(['material-design-differs',int(cx),int(cz)])
            for state in(before,after):
                ground=np.where(soil[state],YY,-129).max(0)
                if not np.array_equal(ground,d['ground'][q]):errors.append(['ground-changed',int(cx),int(cz)])
            if not np.array_equal(water_lookup[before],water_lookup[after]):
                errors.append(['water-changed',int(cx),int(cz)])
            if not np.array_equal(air_lookup[before],air_lookup[after]):
                errors.append(['air-volume-changed',int(cx),int(cz)])
        e.regions.clear();print('Verified coastal materials',file.name,flush=True)
    if cells!=m['cells']or chunks!=spec['full_chunks']:errors.append(['incomplete-material-review',cells,chunks])
    report=dict(errors=errors,full_chunks=chunks,changed_chunks=changed_chunks,changed_cells=cells,changed_columns=columns,
        eligible_columns=int(active.sum()),ground_air_water_and_full_cube_geometry_exact=not errors,
        existing_support_geometry_unchanged=not errors,declared_public_intersections=0,
        previous_structural_defects_not_repaired_by_material_pass=True,world_written=False)
    for name in('coastal-materials-check.json','independent-check.json'):save(C/name,report)
    save(C/'functional-check.json',dict(errors=errors,coastal_materials_verified=not errors,world_written=False))
    if errors:raise ValueError(errors[:12])
    print(json.dumps(report),flush=True)

def require_verified(C):
    m=json.loads((C/'manifest.json').read_text('utf8'))
    if 'coastal_materials'not in m:return
    check=json.loads((C/'coastal-materials-check.json').read_text('utf8'))
    ready=json.loads((C/'coastal-materials-release-check.json').read_text('utf8'))
    if check['errors']or check['changed_cells']!=m['cells']or check['full_chunks']!=m['coastal_materials']['full_chunks']:
        raise ValueError('Incomplete coastal material proof')
    if not check['ground_air_water_and_full_cube_geometry_exact']:raise ValueError('Coastal material edit changes physical geometry')
    if not all(ready[k]for k in('production_recipe_replay_passed','identity_snapshot_ready','exact_voxel_views_reviewed','negative_fault_checks_passed')):
        raise ValueError('Unfinished coastal material release checks')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare')
    for name in('source','authority','programme','out'):a.add_argument('--'+name,type=Path,required=True)
    a.add_argument('--coast',type=Path,action='append',required=True)
    a=sub.add_parser('verify');a.add_argument('--candidate',type=Path,required=True)
    args=p.parse_args();prepare(args)if args.command=='prepare'else verify(args.candidate)
