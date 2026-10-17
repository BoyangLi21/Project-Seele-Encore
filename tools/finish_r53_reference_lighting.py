"""Install the approved reference lighting in the current saved GeoFront."""
from pathlib import Path
import argparse, json, gzip, math
from collections import Counter
import numpy as np
import survey_r52_original_complex as survey
import regional_voxels as vox
from query_blocks import iter_block_entities

PANEL='projectseele:nerv_pyramid_panel'
MARK='projectseele:nerv_pyramid_marking'
BLUE='minecraft:sea_lantern'
WARM='minecraft:ochre_froglight[axis=y]'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    out=args.base/'lighting364';out.mkdir(exist_ok=True)
    world=args.base/'client/saves/SEELE_R53_WORLD';survey.WORLD=world
    d=np.load(out/'MEASURED.npz');lo=d['origin'];before=d['before'];names=list(d['palette']);after=before.copy();ids={n:i for i,n in enumerate(names)}
    for n in (BLUE,MARK,WARM):
        if n not in ids:ids[n]=len(names);names.append(n)
    rows={};groups={}
    def put(pos,state,reason,allowed):
        x,y,z=pos;iy,iz,ix=y-lo[1],z-lo[2],x-lo[0];old=names[before[iy,iz,ix]]
        if old not in allowed:return
        if old==state:return
        after[iy,iz,ix]=ids[state];rows[pos]=dict(pos=pos,before=old,after=state,reason=reason,before_nbt=None,after_nbt=None)
    radius=lambda y:math.floor(120*(1-(y+559)/172)+.5)
    for y in (-405,-407):
        r=radius(y)
        for x in range(30-r,31+r):
            for z in (327-r,327+r):put((x,y,z),BLUE,'cyan_crown_band',{PANEL})
        for z in range(327-r+1,327+r):
            for x in (30-r,30+r):put((x,y,z),BLUE,'cyan_crown_band',{PANEL})
    for y in (-387,-421,-439,-457):
        r=radius(y)
        for x in (30-r,30+r):
            for z in (327-r,327+r):put((x,y,z),BLUE,'cyan_corner_marker',{PANEL})
    # Restore the two thin stems lost when the existing N was downsampled.
    for y in range(-449,-439):
        for x in (11,18):put((x,y,327+radius(y)),MARK,'repair_N_stems',{PANEL,MARK})
    yy,zz,xx=np.ogrid[lo[1]:lo[1]+before.shape[0],lo[2]:lo[2]+before.shape[1],lo[0]:lo[0]+before.shape[2]]
    r=np.maximum(abs(xx+.5+80),abs(zz+.5-438));floor=-545+np.floor(np.minimum(r,88)*68/88).astype(int)
    lake=(xx>=-168)&(xx<8)&(zz>=350)&(zz<526)
    outside=np.maximum(abs(xx-30),abs(zz-327))>np.floor(120*(1-(yy+559)/172)+.5)
    remove=lake&outside&(yy==floor)&np.isin(np.floor(r),[57,5])&(before==ids[WARM])
    add=lake&outside&(yy==floor)&(np.floor(r)==9)&(before==ids['minecraft:black_concrete'])
    for mask,state,reason in [(remove,'minecraft:black_concrete','retire_extra_underwater_rings'),(add,WARM,'warm_apex_outline')]:
        for iy,iz,ix in np.argwhere(mask):put((int(ix+lo[0]),int(iy+lo[1]),int(iz+lo[2])),state,reason,{names[before[iy,iz,ix]]})
    np.savez_compressed(out/'FACADE_AFTER.npz',origin=lo,palette=names,before=before,after=after)
    # Replace only existing paved edge cells adjacent to the measured lawn.
    ground_lo=(-184,-468,90);ground_hi=(170,-464,542)
    ground,pal=survey.measure(ground_lo,ground_hi);final=ground.copy()
    if BLUE not in pal:pal.append(BLUE)
    blue=pal.index(BLUE);paved=np.isin(ground[0],[i for i,n in enumerate(pal) if n in {'projectseele:nerv_floor_panel','projectseele:nerv_hazard_paving'}])
    lawn=np.isin(ground[0],[i for i,n in enumerate(pal) if n.startswith('minecraft:grass_block')])
    adjacent=np.zeros(lawn.shape,bool)
    adjacent[1:]|=lawn[:-1];adjacent[:-1]|=lawn[1:];adjacent[:,1:]|=lawn[:,:-1];adjacent[:,:-1]|=lawn[:,1:]
    clear=np.array([n in {'minecraft:air','minecraft:cave_air'} for n in pal])[ground[1:3]].all(0)
    edge=paved&adjacent&clear;edge[[0,-1],:]=False;edge[:,[0,-1]]=False
    for iz,ix in np.argwhere(edge):
        p=(int(ix+ground_lo[0]),-468,int(iz+ground_lo[2]));old=pal[ground[0,iz,ix]];final[0,iz,ix]=blue
        rows[p]=dict(pos=p,before=old,after=BLUE,reason='cyan_paving_lawn_border',before_nbt=None,after_nbt=None)
    np.savez_compressed(out/'GROUND_AFTER.npz',origin=ground_lo,palette=pal,before=ground,after=final)
    for bounds in [(tuple(lo),tuple(lo+np.array(before.shape)[[2,0,1]]-1)),(ground_lo,ground_hi)]:
        for p,tag in iter_block_entities(world,'projectseele:geofront',*bounds):assert p not in rows,('Device',p)
    values=list(rows.values());(out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(values).encode(),mtime=0))
    report=dict(changed_cells=len(values),reasons=dict(Counter(r['reason'] for r in values)),world=str(world),underwater_radii=[80,9],crown_levels=[-405,-407],native_cyan_material=BLUE,shape_unchanged=True)
    (out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    if args.apply:
        vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-1344,320))
        for r in values:p.exact((*r['pos'],*r['pos']),r['before'],r['after'],r['reason'])
        report['receipt']=p.apply('reference_lighting')
        from finish_r53_shaft_core_and_emblem import install
        install(world,out,generators_only=True)
        (out/'INSTALLED.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
