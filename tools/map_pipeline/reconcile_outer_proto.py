"""Apply the final terrain consumer to saved, unfinished surface chunks.

Exact native density is sampled separately in detached chunks using the saved
seed. This tool preserves every generation status and never promotes a chunk.
"""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from map_pipeline.outer_surface_field import Sampler,CORE
from map_pipeline.launch_protection import load,check_candidate
from plan_ashi_landscape_r54 import SOIL,PLANTS
from query_blocks import AIR


def prepare(a):
    a.out.mkdir(parents=True,exist_ok=False)
    for sub in ('source','delta','surfaces','terrain-inputs'):(a.out/sub).mkdir()
    inputs={}
    for path in(a.field,a.blend):
        shutil.copy2(path,a.out/'terrain-inputs'/path.name)
        inputs['data/projectseele/worldgen/'+path.name]='terrain-inputs/'+path.name
    rows=np.loadtxt(a.native,delimiter=',',skiprows=1,dtype=np.int32)
    if len(rows)%256:raise ValueError('Native sampler did not complete all chunks')
    native={}
    for row in rows.reshape(-1,256,4):
        cx,cz=int(row[0,0])//16,int(row[0,1])//16
        xx,zz=np.meshgrid(np.arange(cx*16,cx*16+16),np.arange(cz*16,cz*16+16))
        if not(np.array_equal(row[:,0],xx.ravel())and np.array_equal(row[:,1],zz.ravel())):raise ValueError('Malformed native chunk samples')
        if(cx,cz)in native:raise ValueError('Repeated native chunk')
        native[cx,cz]=row[:,2].reshape(16,16).copy()
    del rows
    statuses={tuple(r[:2]):r[2]for p in(a.snapshot/'measure').glob('*.json')for r in json.loads(p.read_text())['statuses']}
    exact_native_chunks=len(native);fixed_core=[]
    if a.include_fixed_core:
        for (cx,cz),status in statuses.items():
            if status=='full'or(cx,cz)in native:continue
            if CORE[0]<=cx*16 and cx*16+15<=CORE[2]and CORE[1]<=cz*16 and cz*16+15<=CORE[3]:
                native[cx,cz]=np.zeros((16,16),np.int16);fixed_core.append((cx,cz))
    closures={}if not a.water_closures else {(r['x'],r['z']):r['water']for r in json.loads(a.water_closures.read_text())['columns']}
    used_closures=[]
    if any(statuses.get(q)not in('noise','surface','carvers','features','initialize_light','light','spawn')for q in native):
        raise ValueError('Requested chunk is not a captured saved generation stage')
    for path in(a.snapshot/'proto/source').glob('*.npz'):os.link(path,a.out/'source'/path.name)
    e=Editor(a.out);field=Sampler(a.out/'terrain-inputs'/a.field.name,a.out/'terrain-inputs'/a.blend.name);guard=load(a.world)
    yy=np.arange(-128,320)[:,None,None];errors=[];changed_statuses=[];seen=set();summary=[]
    for path in sorted((a.out/'source').glob('*.npz')):
        rx,rz=map(int,path.stem.split('.')[1:])
        if not any((cx//32,cz//32)==(rx,rz)for cx,cz in native):continue
        r=e.region(rx*512,rz*512)
        names=['minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]',
               'minecraft:gravel','minecraft:water[level=0]']
        for s in names:
            if s not in r['ids']:r['ids'][s]=len(r['names']);r['names'].append(s)
        air,stone,dirt,grass,gravel,water=[r['ids'][s]for s in names]
        soil=np.array([s.split('[')[0]in SOIL for s in r['names']])
        allowed=np.array([s.split('[')[0]in SOIL|PLANTS|AIR|{'minecraft:water'}for s in r['names']])
        wet=np.array([s.split('[')[0]=='minecraft:water'for s in r['names']])
        heights=[];waters=[];coords=[]
        for q,v in zip(r['coords'],r['after']):
            cx,cz=map(int,q)
            if (cx,cz)not in native:continue
            seen.add((cx,cz));zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16]
            target,level=field.sample(xx,zz,native[cx,cz])
            if(cx,cz)in fixed_core:
                alternate=field.sample(xx,zz,np.full((16,16),319))
                if not(np.array_equal(target,alternate[0])and np.array_equal(level,alternate[1])):
                    raise ValueError('Fixed core unexpectedly depends on native noise')
            for (px,pz),water_level in closures.items():
                if px//16==cx and pz//16==cz:
                    level[pz%16,px%16]=water_level;used_closures.append(dict(x=px,z=pz,water=water_level))
            old=np.where(soil[v],yy,-129).max(0);oldwater=np.where(wet[v]&(yy>old),yy,-32768).max(0)
            active=(old!=target)|(oldwater!=np.where(target<level,level,-32768))
            if not active.any():continue
            bottom=np.maximum(-128,np.minimum(old,target)-3)
            top=np.maximum.reduce([old,oldwater,target,level])
            band=active&(yy>=bottom)&(yy<=top)
            desired=np.where(yy>target,np.where(yy<=level,water,air),
                np.where(yy==target,np.where(level>target,gravel,grass),np.where(yy>=target-3,dirt,stone)))
            changed=band&(v!=desired)
            blocked=changed&(~allowed[v]|guard.chunk_mask(cx,cz))
            if blocked.any():
                for iy,iz,ix in np.argwhere(blocked)[:16]:
                    errors.append([cx*16+int(ix),int(iy)-128,cz*16+int(iz),r['names'][int(v[iy,iz,ix])]])
                continue
            v[changed]=desired[changed]
            if changed.any():
                changed_statuses.append([cx,cz,statuses[cx,cz]]);coords.append([cx,cz]);heights.append(target);waters.append(level)
        e.save();e.regions.clear()
        if coords:
            np.savez_compressed(a.out/'surfaces'/path.name,coordinates=coords,ground=heights,water=waters)
            summary.append([rx,rz,len(coords)]);print('Prepared pending terrain',summary[-1],flush=True)
    if seen!=native.keys():raise ValueError('Native columns lack captured proto source')
    rows=e.save()
    (a.out/'manifest.json').write_text(json.dumps(dict(world=str(a.world),regions=rows,cells=sum(r['cells']for r in rows),
        preserved_generation_statuses=changed_statuses,world_written=False,regions_prepared=summary,terrain_inputs=inputs,
        water_closures=used_closures,fixed_core_chunks=len(fixed_core)),indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=errors,visual_verified=False,
        progress_records_written=False,native_chunks=exact_native_chunks,fixed_core_chunks=len(fixed_core),unchanged_statuses=True),indent=2),'utf8')
    (a.out/'launch-protection.json').write_text(json.dumps(check_candidate(guard,a.out),indent=2),'utf8')
    if errors:raise ValueError(f'Terrain meets retained structure/launch cells: {errors[:16]}')
    print('Prepared',len(changed_statuses),'unfinished chunks;',sum(r['cells']for r in rows),'cells',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in ('snapshot','native','field','blend','world','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--include-fixed-core',action='store_true',help='Also reconcile captured core chunks whose field is independent of native noise')
    p.add_argument('--water-closures',type=Path,help='Finite shoreline columns persisted in final surface recipes')
    prepare(p.parse_args())
