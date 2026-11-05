"""Reconcile a measured natural FULL surface with a verified geographic field.

Missing chunks stay missing. The detached native grid supplies only the future
runtime projection; it never substitutes for measured saved voxel ownership.
"""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from map_pipeline.outer_surface_field import Sampler
from map_pipeline.launch_protection import load,check_candidate
from plan_ashi_landscape_r54 import NATURAL,SOIL
from query_blocks import AIR

NO_WATER=-32768
YY=np.arange(-128,320)[:,None,None]

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')

def measured(v,names):
    base=[s.split('[')[0]for s in names]
    soil=np.asarray([s in SOIL for s in base]);wet=np.asarray([s=='minecraft:water'for s in base]);air=np.asarray([s in AIR for s in base])
    ground=np.where(soil[v],YY,-129).max(0)
    water=np.where(wet[v]&(YY>ground),YY,NO_WATER).max(0)
    highest=np.where(~air[v],YY,-129).max(0)
    return ground,water,highest

def desired_band(v,names,old_ground,old_water,target,level,protected,codes):
    ground,water,highest=measured(v,names)
    active=(old_ground!=target)|(old_water!=level)
    if np.any(active&((ground!=old_ground)|(water!=old_water))):
        raise ValueError('Saved active surface differs from the previous runtime field')
    bottom=np.maximum(-128,np.minimum(ground,target)-3)
    top=np.maximum.reduce([highest,target,level])
    band=active&(YY>=bottom)&(YY<=top)
    natural=np.asarray([s.split('[')[0]in NATURAL for s in names])
    if np.any(band&(~natural[v]|protected)):
        raise ValueError('Geographic grading intersects retained construction or launch volume')
    air,stone,dirt,grass,gravel,wet=codes
    desired=np.where(YY>target,np.where(YY<=level,wet,air),
        np.where(YY==target,np.where(level>target,gravel,grass),np.where(YY>=target-3,dirt,stone)))
    result=v.copy();result[band]=desired[band]
    final_ground,final_water,_=measured(result,names)
    if np.any(active&((final_ground!=target)|(final_water!=level))):
        raise ValueError('Candidate natural surface does not match its future field')
    return result,active

def prepare(a):
    capture=json.loads((a.source/'capture.json').read_text('utf8'))
    if Path(capture['world']).resolve()!=a.world.resolve()or capture['actors']:
        raise ValueError('Wrong source world or retained surface actors')
    if set(capture['chunk_statuses'])-{'full','missing'}:raise ValueError('Unfinished chunks require a separate generation-stage repair')
    with np.load(a.native/'native-grid.npz')as f:bounds=f['bounds'];native=f['ground']
    if list(map(int,bounds))!=capture['bounds_xz']:raise ValueError('Detached native grid and saved capture bounds differ')
    x,z,X,Z=map(int,bounds);zz,xx=np.mgrid[z:Z+1,x:X+1]
    old=Sampler(a.previous_field/'hakone_surface.bin.gz',a.previous_field/'hakone_surface_blend.bin.gz').sample(xx,zz,native)
    new=Sampler(a.field/'hakone_surface.bin.gz',a.field/'hakone_surface_blend.bin.gz').sample(xx,zz,native)
    oldwater=np.where(old[0]<old[1],old[1],NO_WATER);water=np.where(new[0]<new[1],new[1],NO_WATER)
    for axis in (0,1):
        for i in (0,-1):
            s=[slice(None),slice(None)];s[axis]=i;s=tuple(s)
            if any(not np.array_equal(v[s],w[s])for v,w in zip(old,new)):raise ValueError('Outer future seam changed')
    a.out.mkdir(parents=True,exist_ok=False)
    for name in ('source','delta','terrain-inputs'):(a.out/name).mkdir()
    inputs={}
    for name in ('hakone_surface.bin.gz','hakone_surface_blend.bin.gz'):
        shutil.copy2(a.field/name,a.out/'terrain-inputs'/name);inputs['data/projectseele/worldgen/'+name]='terrain-inputs/'+name
    for path in (a.source/'source').glob('*.npz'):os.link(path,a.out/'source'/path.name)
    e=Editor(a.out);guard=load(a.world);seen=np.zeros(native.shape,bool);active_count=0;chunks=0
    expected_ground=old[0].copy();expected_water=oldwater.copy()
    for path in sorted((a.out/'source').glob('*.npz')):
        rx,rz=map(int,path.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        material=['minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:gravel','minecraft:water[level=0]']
        for name in material:
            if name not in r['ids']:r['ids'][name]=len(r['names']);r['names'].append(name)
        codes=[r['ids'][name]for name in material]
        for (cx,cz),v in zip(r['coords'],r['after']):
            q=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16]
            if seen[q].any():raise ValueError('Duplicate captured chunk')
            seen[q]=True
            result,active=desired_band(v,r['names'],old[0][q],oldwater[q],new[0][q],water[q],guard.chunk_mask(int(cx),int(cz)),codes)
            v[:]=result;active_count+=int(active.sum());chunks+=1
            expected_ground[q],expected_water[q],_=measured(result,r['names'])
        e.save();e.regions.clear();print('Prepared geographic boundary',path.name,'chunks',chunks,flush=True)
    if chunks!=capture['chunk_statuses']['full']:raise ValueError('Incomplete captured FULL set')
    rows=e.save()
    np.savez_compressed(a.out/'surface-expectations.npz',bounds=bounds,full=seen,ground=expected_ground,water=expected_water,
        future_ground=new[0],future_water=water,previous_ground=old[0],previous_water=oldwater)
    save(a.out/'manifest.json',dict(world=str(a.world),bounds_xz=list(map(int,bounds)),regions=rows,cells=sum(r['cells']for r in rows),
        terrain_inputs=inputs,world_written=False,geographic_boundary=dict(source=str(a.source),native=str(a.native),field=str(a.field),
        previous_field=str(a.previous_field),full_chunks=chunks,active_columns=active_count,missing_chunks=capture['chunk_statuses'].get('missing',0))))
    save(a.out/'functional-check.json',dict(errors=['Independent boundary verification and future recipe replay pending'],visual_verified=False))
    save(a.out/'launch-protection.json',check_candidate(guard,a.out))
    print('Prepared boundary:',chunks,'FULL chunks;',active_count,'columns;',sum(r['cells']for r in rows),'cells',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('world','source','native','previous-field','field','out'):p.add_argument('--'+name,type=Path,required=True)
    prepare(p.parse_args())
