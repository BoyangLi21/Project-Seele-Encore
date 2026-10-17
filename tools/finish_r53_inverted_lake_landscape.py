"""The authorized inverted lake, rooted groves and existing roof beacons.

Measurements use query_blocks through survey.measure. Only existing water is
filled in the basin; the pyramid's occupied underground rooms are not cut.
"""
from pathlib import Path
import argparse, json, math
import numpy as np
from scipy.ndimage import binary_dilation, label
import survey_r52_original_complex as survey
import regional_voxels as vox
from query_blocks import AIR, iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids

DIM='projectseele:geofront'
LO=(-530,-527,130); HI=(330,-388,840)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--apply',action='store_true');a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    survey.WORLD=a.world
    before,names=survey.measure(LO,HI);after=before.copy();ids={s:i for i,s in enumerate(names)}
    print('Measured current landscape',before.shape,flush=True)
    def code(s):
        if s not in ids:ids[s]=len(names);names.append(s)
        return ids[s]
    def put(x,y,z,s):after[y-LO[1],z-LO[2],x-LO[0]]=code(s)
    water=code('minecraft:water[level=0]');black=code('minecraft:black_concrete')
    warm=code('minecraft:ochre_froglight[axis=y]')
    yy,zz,xx=np.ogrid[LO[1]:HI[1]+1,LO[2]:HI[2]+1,LO[0]:HI[0]+1]
    xz=np.broadcast_to(xx[0],before.shape[1:]);zz2=np.broadcast_to(zz[0],before.shape[1:])
    inside=(xz>=-269)&(xz<=6)&(zz2>=348)&(zz2<=623)
    distance=np.minimum.reduce([xz+269,6-xz,zz2-348,623-zz2])
    floor=-477-np.floor(np.clip(distance,0,137)*46/137).astype(int)
    filled=(before==water)&inside[None,:,:]&(yy<=floor[None,:,:])
    after[filled]=black
    # Two embedded square contours, and the small floor-bottom square. They
    # occupy the real sloping floor, not a curve floating above the water.
    rings=[]
    for inset in (20,108,128):
        mask=inside&(distance==inset);iz,ix=np.where(mask);iy=floor[iz,ix]-LO[1]
        ok=after[iy,iz,ix]==black;after[iy[ok],iz[ok],ix[ok]]=warm
        rings.append(dict(inset=inset,y=int(-477-math.floor(inset*46/137)),cells=int(ok.sum())))
    # Rooted native trees on the explicitly requested lakeside lawns. The
    # entire crown must be clear of buildings, banks, roads and existing trees.
    natural={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:dandelion','minecraft:poppy','minecraft:azure_bluet','minecraft:oxeye_daisy','minecraft:cornflower'}
    air_ids=[i for i,n in enumerate(names) if n.split('[')[0] in natural]
    grass=code('minecraft:grass_block[snowy=false]')
    grassmask=before==grass
    ground=np.where(grassmask,yy,LO[1]-1).max(axis=0)
    clear=np.isin(before,air_ids)
    # Existing artificial structures have a generous plan setback, including
    # roofless approach floors. Natural ground never authorizes new passages.
    authored_ids=[i for i,n in enumerate(names) if n.startswith(('projectseele:','mtr:')) or n.split('[')[0] in {'minecraft:smooth_stone','minecraft:white_concrete','minecraft:gray_concrete','minecraft:black_concrete','minecraft:iron_block'}]
    artificial=(np.isin(before,authored_ids)&(yy>=ground[None,:,:])).any(axis=0)
    setback=binary_dilation(artificial,iterations=9)
    occupied=np.zeros(ground.shape,bool);rng=np.random.default_rng(20261018)
    trees=[];log='minecraft:spruce_log[axis=y]';leaf='minecraft:spruce_leaves[distance=1,persistent=true,waterlogged=false]'
    groves=[(-505,-295,200,805),(-290,-65,160,322),(-280,140,650,805),(170,300,345,730)]
    candidates=[]
    for x0,x1,z0,z1 in groves:
        for z in range(z0,z1,13):
            for x in range(x0,x1,13):candidates.append((x+int(rng.integers(-4,5)),z+int(rng.integers(-4,5))))
    rng.shuffle(candidates)
    for x,z in candidates:
        iz,ix=z-LO[2],x-LO[0];g=int(ground[iz,ix]);h=int(rng.integers(12,22));rad=int(rng.integers(4,7))
        if g<LO[1] or g+h+1>HI[1]:continue
        s=np.s_[iz-rad-2:iz+rad+3,ix-rad-2:ix+rad+3]
        if setback[s].any() or occupied[s].any():continue
        if ground[s].max()-ground[s].min()>4:continue
        cells={}
        for dy in range(4,h+1):
            radius=max(1,round(rad*(h+1-dy)/(h-3)))
            if dy%3==0:radius=max(1,radius-1)
            for dz in range(-radius,radius+1):
                for dx in range(-radius,radius+1):
                    if abs(dx)+abs(dz)>radius*1.65:continue
                    cells[x+dx,g+dy,z+dz]=leaf
        for y in range(g+1,g+h):cells[x,y,z]=log
        if any(not clear[y-LO[1],b-LO[2],c-LO[0]] for c,y,b in cells):continue
        for (c,y,b),state in cells.items():put(c,y,b,state)
        occupied[iz-rad-1:iz+rad+2,ix-rad-1:ix+rad+2]=True
        trees.append(dict(root=[x,g+1,z],height=h,radius=rad))
    print('Lake fill',int(filled.sum()),'native trees',len(trees),flush=True)
    # Roof beacons are placed on actual exposed full roof blocks, not on
    # mechanical hatches or inferred building volumes.
    roof_states={'projectseele:nerv_structural_panel','projectseele:nerv_floor_panel','projectseele:nerv_machine_panel','projectseele:nerv_wall_panel','minecraft:white_concrete','minecraft:gray_concrete','minecraft:smooth_stone'}
    solid=~np.isin(before,[i for i,n in enumerate(names) if n in AIR or n.startswith('minecraft:light[')])
    top=np.where(solid,yy,LO[1]-1).max(0);tz,tx=np.indices(top.shape)
    topcodes=before[np.clip(top-LO[1],0,before.shape[0]-1),tz,tx]
    roof=np.isin(topcodes,[ids[n] for n in roof_states if n in ids])&(top>=-460)&(top<HI[1]-3)
    groups,n=label(roof);beacons=[]
    for idx in range(1,n+1):
        zc,xc=np.where(groups==idx)
        if len(xc)<36:continue
        z0,z1=zc.min(),zc.max();x0,x1=xc.min(),xc.max()
        if max(x1-x0,z1-z0)<10:continue
        chosen=[]
        for px,pz in [(x0+1,z0+1),(x1-1,z0+1),(x1-1,z1-1),(x0+1,z1-1)]:
            j=np.argmin((xc-px)**2+(zc-pz)**2);ix,iz=int(xc[j]),int(zc[j]);g=int(top[iz,ix])
            if any((ix-u)**2+(iz-v)**2<64 for u,v in chosen):continue
            if not clear[g+1-LO[1]:g+3-LO[1],iz,ix].all():continue
            x,z=ix+LO[0],iz+LO[2]
            put(x,g+1,z,'projectseele:nerv_machine_edge')
            put(x,g+2,z,'projectseele:nerv_alert_light[hanging=false,lit=true]')
            beacons.append([x,g+2,z]);chosen.append((ix,iz))
    # No devices or original NBT may be changed by this landscaping pass.
    for (x,y,z),tag in iter_block_entities(a.world,DIM,LO,HI):
        assert before[y-LO[1],z-LO[2],x-LO[0]]==after[y-LO[1],z-LO[2],x-LO[0]],(x,y,z,str(tag['id']))
    changes=int((before!=after).sum())
    np.savez_compressed(a.out/'EXACT_BEFORE_AFTER.npz',origin=LO,palette=names,before=before,after=after)
    report=dict(world=str(a.world),changed_cells=changes,basin_fill=int(filled.sum()),basin_rings=rings,trees=trees,roof_beacons=beacons,original_devices_preserved=True)
    (a.out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    vox.WORLD=a.world;vox.OUT=a.out;vox.DIM=DIM;p=vox.Painter(vertical_bounds=(-1344,320))
    cuboids(p,LO,before,after,names,'authorized_inverted_basin_and_lakeside_landscape')
    if a.apply:
        report['receipt']=p.apply('inverted_basin_and_lakeside')
        report['installed']=True
        (a.out/'INSTALLED.json').write_text(json.dumps(report,indent=2),'utf8')
    else:p.save_plan('inverted_basin_and_lakeside')
    print(json.dumps(dict(changes=changes,trees=len(trees),roof_beacons=len(beacons),rings=rings)),flush=True)

if __name__=='__main__':main()
