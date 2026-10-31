"""Retire superseded R20 finished road footprints, including later extensions.

The early transit road contract is not the final public-road catalogue. Keeping
only that first contract missed the repeated old east-west decks near Z=432.
"""
import argparse,json
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.ndimage import binary_dilation
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid,sampled
from query_blocks import AIR
from plan_ashi_landscape_r54 import NATURAL
from verify_hakone_network_candidate import PAVEMENT

def run(a):
    e=Editor(a.candidate);d=load_grid(a.plan/'network.npz');x0,z0,x1,z1=map(int,d['bounds'])
    zz,xx=np.mgrid[z0:z1+1,x0:x1+1];mask=np.zeros(xx.shape,bool);heights=np.full(xx.shape,-32768,np.int16)
    sources=[]
    for name in ('extension_contract_final.npz','road_contract_final.npz'):
        path=a.gis.parent/'world_rebuild_r20/road_actual'/name;v=load_grid(path);ox,oz=map(int,v['origin']);v['bounds']=[ox,oz,ox+v['mask'].shape[1]-1,oz+v['mask'].shape[0]-1]
        hit=sampled(v,'mask',xx,zz).astype(bool);mask|=hit;heights[hit]=(sampled(v,'height2',xx,zz)[hit]-1)//2;sources.append(str(path))
    replaced=((xx>=-1050)&(xx<=1350)&(zz>=-800)&(zz<=1400))|((xx>=896)&(xx<=2431)&(zz>=512)&(zz<=1407))
    protected=d['held']|d['core']|d['walk']|d['tunnel']
    # Airport runway/apron and its retained station connector are still in
    # service; this repair does not move their identities or facilities.
    protected|=(xx>=350)&(xx<=1350)&(zz>=-177)&(zz<=125)
    protected|=(xx>=400)&(xx<=1350)&(zz>=1400)
    for x,y,z in json.loads((a.gis.parent/'facility_r28/airport/civil/road_samples.json').read_text('utf8')):
        if x0<=x<=x1 and z0<=z<=z1:protected[z-z0,x-x0]=True
    raw=mask&replaced&~protected
    # Finish paving sides together; this includes guardrail/lamppost positions
    # two columns outside the old road, while keeping actual new street widths.
    selected=binary_dilation(raw,iterations=2)&~protected&replaced
    from scipy.ndimage import distance_transform_edt
    _,near=distance_transform_edt(~mask,return_indices=True);heights=heights[tuple(near)]
    native=defaultdict(dict)
    for r in json.loads((a.plan/'native-curves.json').read_text('utf8'))['trains']:
        for px,py,pz in r['points']:
            x,y,z=map(int,np.floor([px,py,pz]))
            for X in range(x-2,x+3):
                for Z in range(z-2,z+3):native[X//512,Z//512].setdefault((X,Z),set()).add(y)
    materials=PAVEMENT|{'minecraft:iron_bars','minecraft:stone_brick_wall','minecraft:sea_lantern','minecraft:polished_andesite'}
    materials-= {'minecraft:deepslate_bricks','minecraft:light_gray_concrete','projectseele:nerv_floor_panel'}
    count=0;columns=0;changed=set();regions=[];yy=np.arange(-128,320)[:,None,None]
    for file in sorted((a.candidate/'source').glob('*.npz')):
        rx,rz=map(int,file.stem.split('.')[1:])
        if rx*512>x1 or rx*512+511<x0 or rz*512>z1 or rz*512+511<z0:continue
        area=np.s_[max(0,rz*512-z0):min(selected.shape[0],rz*512+512-z0),max(0,rx*512-x0):min(selected.shape[1],rx*512+512-x0)]
        if not selected[area].any():continue
        r=e.region(rx*512,rz*512)
        for name in ('minecraft:air','minecraft:dirt','minecraft:grass_block[snowy=false]'):
            if name not in r['ids']:r['ids'][name]=len(r['names']);r['names'].append(name)
        mutable=np.array([s.split('[')[0]in materials for s in r['names']]);air,dirt,grass=[r['ids'][s]for s in('minecraft:air','minecraft:dirt','minecraft:grass_block[snowy=false]')]
        touched=False
        for(cx,cz),b in zip(r['coords'],r['after']):
            X,Z=int(cx)*16,int(cz)*16
            if not(x0<=X<=x1-15 and z0<=Z<=z1-15):continue
            ar=np.s_[Z-z0:Z-z0+16,X-x0:X-x0+16];sel=selected[ar];h=heights[ar];ground=d['ground'][ar]
            if not sel.any():continue
            hit=sel&(yy>=h-2)&(yy<=h+10)&mutable[b]
            for iz in range(16):
                for ix in range(16):
                    for y in native[rx,rz].get((X+ix,Z+iz),()):hit[max(0,y-3+128):min(448,y+9+128),iz,ix]=False
            replacement=np.where(yy>ground,air,np.where(yy==ground,grass,dirt));diff=hit&(b!=replacement)
            if diff.any():
                count+=int(diff.sum());columns+=int(diff.any(0).sum());b[diff]=np.broadcast_to(replacement,b.shape)[diff];changed.add((int(cx),int(cz)));touched=True
        if touched:regions.append(file.name)
        e.save();e.regions.clear()
    rows=e.save();meta=json.loads((a.candidate/'manifest.json').read_text('utf8'));meta.update(regions=rows,cells=sum(r['cells']for r in rows))
    (a.candidate/'manifest.json').write_text(json.dumps(meta,indent=2),'utf8')
    p=a.candidate/'transport-changed-chunks.json';changed|=set(map(tuple,json.loads(p.read_text('utf8'))));p.write_text(json.dumps(sorted(changed)),'utf8')
    report=dict(source_contracts=sources,removed_cells=count,columns=columns,changed_regions=regions,active_street_columns_changed=0)
    (a.candidate/'replaced-road-retirement.json').write_text(json.dumps(report,indent=2),'utf8');print(report,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('candidate','plan','gis'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
