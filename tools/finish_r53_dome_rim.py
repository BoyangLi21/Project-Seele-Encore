"""Finish exposed stone on the measured outer dome, including steep side faces."""
from pathlib import Path
import argparse,json,gzip
import numpy as np
import regional_voxels as vox
from query_blocks import iter_selected_sections,chunk_statuses
from finish_r53_cavern_armor import roof,PANEL,JOINT
from prepare_continuous_upright_civil_r52 import cuboids

AIR={'minecraft:air','minecraft:cave_air','minecraft:void_air'}
DIM='projectseele:geofront'

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('world',type=Path);ap.add_argument('out',type=Path)
    ap.add_argument('--apply',action='store_true');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    zz,xx=np.indices((16,16));owned={};selected={}
    for cx in range(-112,116):
        for cz in range(-95,132):
            x,z=xx+cx*16,zz+cz*16;r=np.hypot(x-30,z-296)
            active=(r>=1750)&(r<=1801)
            if not active.any():continue
            h=roof(x,z);top=np.maximum.reduce([h+3]+[roof(x+dx,z+dz)for dx,dz in ((1,0),(-1,0),(0,1),(0,-1))])
            owned[cx,cz]=(h,top,active)
            for dx,dz in ((0,0),(1,0),(-1,0),(0,1),(0,-1)):
                selected.setdefault((cx+dx,cz+dz),set()).update(range(-31,int(top[active].max())//16+1))
    statuses=chunk_statuses(a.world,DIM,selected);missing={p for p,s in statuses.items()if s!='full'}
    selected={p:s for p,s in selected.items()if p not in missing}
    sections={};air={}
    for cx,cz,sy,pal,ind in iter_selected_sections(a.world,DIM,selected):
        values=ind.reshape(16,16,16);sections[cx,cz,sy]=(list(pal),values)
        air[cx,cz,sy]=np.asarray([n in AIR for n in pal])[values]
    vox.WORLD=a.world;vox.DIM=DIM;vox.OUT=a.out;p=vox.Painter(vertical_bounds=(-1440,320));cells=0
    for (cx,cz,sy),(names,before)in sections.items():
        if (cx,cz)not in owned:continue
        h,top,active=owned[cx,cz];y=np.arange(sy*16,sy*16+16)[:,None,None]
        known=((cx+dx,cz+dz)not in missing for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)))
        if not all(known):continue
        around=np.zeros((18,18,18),bool);around[1:17,1:17,1:17]=air[cx,cz,sy]
        for dx,dz,axis,edge in ((1,0,2,17),(-1,0,2,0),(0,1,1,17),(0,-1,1,0)):
            neighbour=air.get((cx+dx,cz+dz,sy))
            if neighbour is None:continue
            if axis==2:around[1:17,1:17,edge]=neighbour[:,:,0 if dx>0 else -1]
            else:around[1:17,edge,1:17]=neighbour[:,0 if dz>0 else -1,:]
        below=air.get((cx,cz,sy-1))
        if below is not None:around[0,1:17,1:17]=below[-1]
        exposed=around[:-2,1:17,1:17]|around[1:17,:-2,1:17]|around[1:17,2:,1:17]|around[1:17,1:17,:-2]|around[1:17,1:17,2:]
        mask=active[None,:,:]&(y>h)&(y<=top)&exposed
        mask&=np.asarray([n=='minecraft:stone'for n in names])[before]
        if not mask.any():continue
        for n in (PANEL,JOINT):
            if n not in names:names.append(n)
        x,z=xx+cx*16,zz+cz*16
        joint=((x-30)%64==0)|((z-296)%64==0)|((y+478)%32==0)
        after=before.copy();after[mask]=np.broadcast_to(np.where(joint,names.index(JOINT),names.index(PANEL)),before.shape)[mask]
        cuboids(p,(cx*16,sy*16,cz*16),before,after,names,'R53_original_outer_dome_exposed_stone_finish');cells+=int(mask.sum())
    p.meta.update(root_author=True,cells=cells,geometry_unchanged=True,exposed_stone_only=True,missing_chunks_skipped=len(missing),
                  source='Original TvWorldPreviewTerrain roof, radius 1750..1801; actual air-side exposure')
    p.save_plan('dome_rim');print(p.meta,flush=True)
    if a.apply:p.apply('dome_rim')

if __name__=='__main__':main()
