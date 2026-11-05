"""Grade a finite natural lowland beach and shallows from current saved voxels.

Ports, river mouths, public surfaces, buildings, actors and non-natural blocks
remain protected. Existing sea levels and high coastal cliffs are retained.
"""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt,binary_dilation
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import NATURAL,SOIL
from query_blocks import AIR
from install_r53_carrier_trays import stopped_world
from map_pipeline.launch_protection import load,check_candidate

SEA=-82
YY=np.arange(-128,320)[:,None,None]
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')

def prepare(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);x,z,X,Z=cap['bounds_xz']
    if cap['unavailable_chunks']:raise ValueError('A complete current FULL capture is required')
    with np.load(a.source/'measured.npz')as f:g=f['top'];full=f['full']
    if not full.all():raise ValueError('Unmeasured coast')
    with np.load(a.programme/'watercourse-reference.npz')as f:
        ox,oz,oX,oZ=map(int,f['bounds'])
        if not(ox<=x<X<=oX and oz<=z<Z<=oZ):raise ValueError('Missing geographical coast context')
        q=np.s_[z-oz:Z-oz+1,x-ox:X-ox+1];sea=f['sea'][q];river=f['river'][q]
    inland,nearest_land=distance_transform_edt(sea,return_indices=True);offshore=distance_transform_edt(~sea)
    low_coast=(g[tuple(nearest_land)]>=SEA-12)&(g[tuple(nearest_land)]<=SEA+4)
    wet_zone=sea&(inland<=40)&low_coast;dry_zone=~sea&(offshore<=24)&(g>=SEA-12)&(g<=SEA+4)
    proposal=g.copy();proposal[wet_zone]=np.maximum(g[wet_zone],SEA-1-np.floor(np.maximum(0,inland[wet_zone]-1)/5).astype(np.int16))
    # A dry land cell below the sea cannot be left facing a vertical water wall.
    # Form a natural crest with one block of freeboard, tapering inland at 1:4.
    bank=SEA+1-np.ceil(np.maximum(0,offshore-4)/4).astype(np.int16)
    proposal[dry_zone]=np.maximum(g[dry_zone],bank[dry_zone])
    high_beach=dry_zone&(offshore<=8)&(g>=SEA)
    proposal[high_beach]=np.minimum(proposal[high_beach],SEA+np.maximum(1,np.ceil(offshore[high_beach]/4)).astype(np.int16))
    zz,xx=np.mgrid[z:Z+1,x:X+1];edge=np.minimum.reduce([xx-x,X-xx,zz-z,Z-zz])
    blocked=(distance_transform_edt(~river)<=24)|(edge<16)
    # The retained port box includes complete ship hulls and their apron.
    blocked|=(xx>=3008)&(xx<=3392)&(zz>=928)&(zz<=1248)
    for actor in cap['actors']:
        px,_,pz=actor['pos'];blocked|=(abs(xx-px)<=64)&(abs(zz-pz)<=64)
    with np.load(a.authority/'network.npz')as f:
        ox,oz,oX,oZ=map(int,f['bounds'])
        if not(ox<=x<X<=oX and oz<=z<Z<=oZ):raise ValueError('Coast exceeds current authority')
        public=f['walk'][z-oz:Z-oz+1,x-ox:X-ox+1].copy()
    # Preserve the exact public columns. Their surrounding natural soil still
    # needs a bank; an arbitrary five-block exclusion left exposed water walls.
    blocked|=public
    for row in json.loads((a.authority/'catalog.json').read_text('utf8')):
        b=row['occupied_bounds'];blocked|=(xx>=b[0]-4)&(xx<=b[3]+4)&(zz>=b[2]-4)&(zz<=b[5]+4)
    water=np.full(g.shape,-32768,np.int16);foreign=np.zeros(g.shape,bool)
    for path in sorted((a.source/'source').glob('*.npz')):
        with np.load(path)as f:coords=f['coordinates'];blocks=f['blocks'];names=[s.split('[')[0]for s in map(str,f['palette'])]
        natural=np.asarray([s in NATURAL for s in names]);wet=np.asarray([s=='minecraft:water'for s in names])
        for(cx,cz),v in zip(coords,blocks):
            q=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16]
            water[q]=np.where(wet[v]&(YY>g[q]),YY,-32768).max(0)
            foreign[q]=((~natural[v])&(YY>=np.minimum(g[q],proposal[q])-3)).any(0)
        print('Measured coast ownership',path.name,flush=True)
    blocked|=foreign
    wet_zone&=(water==SEA)&(g<SEA);dry_zone&=water==-32768
    taper=np.clip(distance_transform_edt(~blocked)/16,0,1)
    target=g+np.rint((proposal.astype(float)-g)*taper).astype(np.int16)
    active=(wet_zone|dry_zone)&~blocked;target[~active]=g[~active]
    shore=active&dry_zone&binary_dilation(water==SEA)&(g<SEA+1)
    target[shore]=np.maximum(target[shore],SEA+1)
    # Near a preserved foundation or old cliff, relax only our own edits.
    # Nothing outside the authored beach becomes a smoothing variable.
    refinements=0
    for iteration in range(128):
        changes=0
        for axis in (0,1):
            l=[slice(None),slice(None)];r=l.copy();l[axis]=slice(None,-1);r[axis]=slice(1,None);l,r=tuple(l),tuple(r)
            # At a wet/dry boundary compare the visible sea/land surfaces.
            # The submerged bed is not a vertical obstruction above water.
            crossing=(water[l]>g[l])!=(water[r]>g[r])
            P=np.where(crossing,np.maximum(target[l],water[l]),target[l]);Q=np.where(crossing,np.maximum(target[r],water[r]),target[r])
            oldP=np.where(crossing,np.maximum(g[l],water[l]),g[l]);oldQ=np.where(crossing,np.maximum(g[r],water[r]),g[r])
            bad=(np.abs(P.astype(int)-Q)>np.maximum(2,np.abs(oldP.astype(int)-oldQ)))
            for j,i in np.argwhere(bad):
                P=(int(j),int(i));Q=(int(j+(axis==0)),int(i+(axis==1)));sign=np.sign(int(target[P])-int(target[Q]));choices=[]
                for p,direction in ((P,sign),(Q,-sign)):
                    delta=int(target[p])-int(g[p])
                    if delta*direction>0:choices.append((abs(delta),p))
                if not choices:continue
                _,p=max(choices);target[p]-=int(np.sign(int(target[p])-int(g[p])));changes+=1
        refinements+=changes
        if not changes:break
    else:raise ValueError('Coastal slope relaxation did not converge')
    if np.any(active&public):raise ValueError('Beach intersects an installed public surface')
    a.out.mkdir(parents=True,exist_ok=False)
    for name in ('source','delta'):(a.out/name).mkdir()
    for p in(a.source/'source').glob('*.npz'):os.link(p,a.out/'source'/p.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    with stopped_world(world):shutil.copytree(world/'mtr',a.out/'preserved-native')
    e=Editor(a.out);guard=load(world)
    sand=(np.sin(xx*.17+np.cos(zz*.09))*np.cos(zz*.21+xx*.03))>.65
    for path in sorted((a.out/'source').glob('*.npz')):
        rx,rz=map(int,path.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        materials=('minecraft:air','minecraft:stone','minecraft:gravel','minecraft:sand','minecraft:water[level=0]')
        for name in materials:
            if name not in r['ids']:r['ids'][name]=len(r['names']);r['names'].append(name)
        air,stone,gravel,sandy,wet=(r['ids'][n]for n in materials);base=[s.split('[')[0]for s in r['names']];natural=np.asarray([s in NATURAL for s in base]);empty=np.asarray([s in AIR for s in base])
        for(cx,cz),v in zip(r['coords'],r['after']):
            q=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16];use=active[q]
            if not use.any():continue
            high=np.where(~empty[v],YY,-129).max(0);bottom=np.minimum(g[q],target[q])-3;band=use&(YY>=bottom)&(YY<=np.maximum(high,target[q]))
            desired=np.where(YY>target[q],np.where(YY<=water[q],wet,air),np.where(YY>=target[q]-2,np.where(sand[q],sandy,gravel),stone))
            delta=band&(v!=desired)
            if np.any(delta&(~natural[v]|guard.chunk_mask(int(cx),int(cz)))):raise ValueError('Beach grading reaches retained construction or launch volume')
            v[delta]=desired[delta]
        e.save();e.regions.clear();print('Prepared coast',path.name,flush=True)
    records=e.save();np.savez_compressed(a.out/'beach-design.npz',bounds=cap['bounds_xz'],active=active,wet=wet_zone&active,dry=dry_zone&active,ground=target,old_ground=g,water=water,blocked=blocked,public=public)
    save(a.out/'manifest.json',dict(world=str(world),bounds_xz=cap['bounds_xz'],regions=records,cells=sum(r['cells']for r in records),preserve_native_members=True,
        natural_beach=dict(source=str(a.source),authority=str(a.authority),programme=str(a.programme),full_chunks=cap['chunk_statuses']['full'],
        active_columns=int(active.sum()),wet_columns=int((active&wet_zone).sum()),dry_columns=int((active&dry_zone).sum()),slope_refinements=refinements,
        original_sea_level_retained=SEA,river_mouth_buffer_blocks=24,regional_field_unchanged=True,exact_future_recipes_required=True),world_written=False))
    save(a.out/'functional-check.json',dict(errors=['Independent beach verification pending'],visual_verified=False,world_written=False))
    save(a.out/'launch-protection.json',check_candidate(guard,a.out))
    print('Prepared natural coast:',int(active.sum()),'columns;',sum(r['cells']for r in records),'cells; no world writes.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','programme','authority','out'):p.add_argument('--'+n,type=Path,required=True)
    prepare(p.parse_args())
