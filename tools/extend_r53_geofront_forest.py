"""Extend the user's GeoFront forest on measured native ground, with roads retained."""
from pathlib import Path
import argparse, gzip, json, math, time
import numpy as np
from scipy.ndimage import binary_dilation
import survey_r52_original_complex as survey
import regional_voxels as vox
from prepare_continuous_upright_civil_r52 import cuboids
from query_blocks import chunk_statuses, iter_selected_sections


def tree_template(index):
    rng=np.random.default_rng(36100+index)
    height=13+index%6;radius=5+index%2
    cells={}
    # Overlapping irregular crowns use native persistent oak leaves.
    lobes=[(0,height-4,0,radius,4)]
    for i in range(4):
        a=i*math.pi/2+rng.uniform(-.4,.4)
        lobes.append((round(math.cos(a)*2),height-6+int(rng.integers(-1,2)),round(math.sin(a)*2),radius-1,3))
    for cx,cy,cz,rx,ry in lobes:
        for y in range(cy-ry,cy+ry+1):
            for z in range(cz-rx,cz+rx+1):
                for x in range(cx-rx,cx+rx+1):
                    d=((x-cx)/rx)**2+((z-cz)/rx)**2+((y-cy)/ry)**2
                    if d<=1 and not (d>.83 and rng.random()<.14):cells[x,y,z]=2
    for y in range(0,height-2):cells[0,y,0]=1
    return np.array([(*p,c) for p,c in sorted(cells.items())],np.int16)


def measured_tile(lo,hi):
    names=['unmeasured:held'];lookup={names[0]:0};data=np.zeros((hi[1]-lo[1]+1,hi[2]-lo[2]+1,hi[0]-lo[0]+1),np.uint16)
    selected={(x,z):set(range(lo[1]//16,hi[1]//16+1)) for x in range(lo[0]//16,hi[0]//16+1) for z in range(lo[2]//16,hi[2]//16+1)}
    status=chunk_statuses(survey.WORLD,vox.DIM,selected);selected={k:v for k,v in selected.items() if status.get(k)=='full'}
    for cx,cz,sy,pal,idx in iter_selected_sections(survey.WORLD,vox.DIM,selected):
        mapping=[]
        for state in pal:
            if state not in lookup:lookup[state]=len(names);names.append(state)
            mapping.append(lookup[state])
        d=np.array(mapping,np.uint16)[idx].reshape(16,16,16);x,y,z=cx*16,sy*16,cz*16
        aa=(max(x,lo[0]),max(y,lo[1]),max(z,lo[2]));bb=(min(x+15,hi[0]),min(y+15,hi[1]),min(z+15,hi[2]))
        data[aa[1]-lo[1]:bb[1]-lo[1]+1,aa[2]-lo[2]:bb[2]-lo[2]+1,aa[0]-lo[0]:bb[0]-lo[0]+1]=d[aa[1]-y:bb[1]-y+1,aa[2]-z:bb[2]-z+1,aa[0]-x:bb[0]-x+1]
    return data,names


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--apply',action='store_true');a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True);survey.WORLD=a.world;vox.WORLD=a.world;vox.OUT=a.out;vox.DIM='projectseele:geofront'
    states=['minecraft:air','minecraft:oak_log[axis=y]','minecraft:oak_leaves[distance=1,persistent=true,waterlogged=false]']
    templates=[tree_template(i) for i in range(12)]
    np.savez_compressed(a.out/'TREE_TEMPLATES.npz',**{f'tree_{i}':t for i,t in enumerate(templates)})
    navpath=a.world/'nerv_routes_r24.json.gz'
    if not navpath.exists():navpath=next(a.world.rglob('nerv_routes_r24.json.gz'))
    with gzip.open(navpath,'rt',encoding='utf8') as f:nav=json.load(f)
    nodes=np.array([n[:3] for n,active in zip(nav['nodes'],nav['node_active']) if active],dtype=np.int32);del nav
    plants={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:dandelion','minecraft:poppy','minecraft:azure_bluet','minecraft:oxeye_daisy','minecraft:cornflower'}
    roots={'minecraft:grass_block','minecraft:podzol','minecraft:coarse_dirt','minecraft:rooted_dirt'}
    existing=json.loads((a.out/'PLAN.json').read_text()) if (a.out/'PLAN.json').exists() else {};trees=existing.get('trees',[]);tiles=existing.get('tiles',[]);done={(t['lo'][0]+8,t['lo'][2]+8) for t in tiles};start=time.time()
    for z0 in range(-768,1280,256):
        for x0 in range(-1024,1024,256):
            if (x0,z0) in done:continue
            lo=(x0-8,-512,z0-8);hi=(x0+263,-289,z0+263)
            before,names=measured_tile(lo,hi);after=before.copy();ids={v:i for i,v in enumerate(names)}
            for state in states[1:]:
                if state not in ids:ids[state]=len(names);names.append(state)
            base=[v.split('[')[0] for v in names];yy=np.arange(lo[1],hi[1]+1)[:,None,None]
            ground=np.where(np.isin(before,[i for i,v in enumerate(base) if v in roots]),yy,lo[1]-1).max(0)
            allowed=np.isin(after,[i for i,v in enumerate(base) if v in plants or v.endswith('_leaves')])
            authored=[i for i,n in enumerate(names) if not vox.natural(n)]
            artificial=(np.isin(before,authored)&(yy>=ground[None,:,:])).any(0)
            held=binary_dilation(artificial,iterations=10)
            local=nodes[(nodes[:,0]>=lo[0])&(nodes[:,0]<=hi[0])&(nodes[:,2]>=lo[2])&(nodes[:,2]<=hi[2])]
            if len(local):
                iz=local[:,2]-lo[2];ix=local[:,0]-lo[0];keep=(local[:,1]>=ground[iz,ix]-1)&(local[:,1]<=ground[iz,ix]+3);path=np.zeros(ground.shape,bool);path[iz[keep],ix[keep]]=True;held|=binary_dilation(path,iterations=5)
            rng=np.random.default_rng(361+(x0+1024)*2048+z0+768)
            tiletrees=[]
            for z in range(z0+4,z0+253,13):
                for x in range(x0+4,x0+253,13):
                    x1=x+int(rng.integers(-3,4));z1=z+int(rng.integers(-3,4));ix=x1-lo[0];iz=z1-lo[2];g=int(ground[iz,ix])
                    if g<lo[1] or held[iz,ix]:continue
                    # Main base apron, lake banks and explicit facility approaches.
                    if -299<=x1<=35 and 320<=z1<=652:continue
                    if -125<=x1<=185 and 165<=z1<=480:continue
                    k=int(rng.integers(0,len(templates)));t=templates[k];tx=t[:,0]+ix;ty=t[:,1]+g+1-lo[1];tz=t[:,2]+iz
                    if ty.max()>=after.shape[0] or tx.min()<0 or tx.max()>=after.shape[2] or tz.min()<0 or tz.max()>=after.shape[1]:continue
                    if held[tz,tx].any() or not allowed[ty,tz,tx].all():continue
                    # Trunks cannot replace pre-existing foliage or structures.
                    tr=t[:,3]==1
                    if not np.isin(after[ty[tr],tz[tr],tx[tr]],[i for i,v in enumerate(base) if v in plants]).all():continue
                    after[ty,tz,tx]=np.where(t[:,3]==1,ids[states[1]],ids[states[2]])
                    allowed[ty[tr],tz[tr],tx[tr]]=False
                    tiletrees.append(dict(root=[x1,g+1,z1],template=k))
            if tiletrees:
                painter=vox.Painter(vertical_bounds=(-1344,320));count=cuboids(painter,lo,before,after,names,'authorized_continuous_geofront_forest')
                receipt=painter.apply(f'forest_{x0}_{z0}') if a.apply else str(painter.save_plan(f'forest_{x0}_{z0}'))
                trees+=tiletrees;tiles.append(dict(lo=lo,hi=hi,trees=len(tiletrees),changed=count,receipt=receipt))
                (a.out/'PLAN.json').write_text(json.dumps(dict(world=str(a.world),trees=trees,tiles=tiles,states=states,navigation_preserved=True,installed=a.apply),indent=2),'utf8')
            print('FOREST',x0,z0,'trees',len(tiletrees),'total',len(trees),'seconds',round(time.time()-start),flush=True)
    print('FOREST COMPLETE',len(trees),sum(t['changed'] for t in tiles),flush=True)

if __name__=='__main__':main()
