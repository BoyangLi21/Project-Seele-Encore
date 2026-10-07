"""Read measured underground grass, vegetation and construction for siting.

This does not generate terrain or write a world. All block decoding remains
inside query_blocks; source generator formulas are not permission to build.
"""
from pathlib import Path
from collections import Counter
import argparse,json
import numpy as np
from query_blocks import iter_selected_sections,chunk_statuses

ROOT=Path(__file__).resolve().parents[1]
NATURAL={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel',
    'minecraft:sand','minecraft:water','minecraft:air','minecraft:cave_air','minecraft:void_air',
    'minecraft:oak_log','minecraft:birch_log','minecraft:oak_leaves','minecraft:birch_leaves',
    'minecraft:azalea','minecraft:flowering_azalea','minecraft:azalea_leaves','minecraft:flowering_azalea_leaves',
    'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern',
    'minecraft:poppy','minecraft:dandelion','minecraft:allium','minecraft:oxeye_daisy','minecraft:cornflower'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r50/underground_airport');args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    x0,x1,z0,z1=-896,-192,-640,-64
    selected={(x,z):set(range(-35,-23)) for x in range(x0//16,x1//16+1) for z in range(z0//16,z1//16+1)}
    status=chunk_statuses(args.world,'projectseele:geofront',selected)
    shape=(z1-z0+1,x1-x0+1);soil=np.full(shape,-32768,np.int16);built=np.zeros(shape,np.int32);wood=np.zeros(shape,np.int16);states=Counter()
    for cx,cz,sy,pal,index in iter_selected_sections(args.world,'projectseele:geofront',selected,skip_unfinished=True):
        index=index.reshape(16,16,16)
        ix,iz=cx*16-x0,cz*16-z0
        ax0,ax1=max(0,ix),min(shape[1],ix+16);az0,az1=max(0,iz),min(shape[0],iz+16)
        sub=index[:,az0-iz:az1-iz,ax0-ix:ax1-ix]
        names=[s.split('[')[0]for s in pal]
        for state,n in zip(pal,np.bincount(sub.ravel(),minlength=len(pal))):states[state]+=int(n)
        grass=np.isin(sub,[i for i,s in enumerate(names)if s=='minecraft:grass_block'])
        levels=np.arange(16,dtype=np.int16)[:,None,None]+sy*16
        tops=np.max(np.where(grass,levels,-32768),axis=0)
        soil[az0:az1,ax0:ax1]=np.maximum(soil[az0:az1,ax0:ax1],tops)
        built[az0:az1,ax0:ax1]+=np.isin(sub,[i for i,s in enumerate(names)if s not in NATURAL]).sum(axis=0)
        wood[az0:az1,ax0:ax1]+=np.isin(sub,[i for i,s in enumerate(names)if s.endswith(('_log','_leaves'))]).sum(axis=0)
    np.savez_compressed(args.out/'northwest_floor_raster.npz',origin=np.array([x0,z0]),grass_top=soil,constructed_count=built,wood_count=wood)
    rows=[]
    for centre in [(-680,-350),(-520,-350),(-440,-270),(-670,-180)]:
        x,z=centre;xs=slice(x-90-x0,x+91-x0);zs=slice(z-80-z0,z+81-z0)
        h=soil[zs,xs];b=built[zs,xs];trees=wood[zs,xs];valid=h>-32768
        rows.append(dict(centre_xz=centre,apron_bounds=[[x-90,z-80],[x+90,z+80]],grass_columns=int(valid.sum()),
            measured_columns=int(h.size),grass_range=[int(h[valid].min()),int(h[valid].max())]if valid.any()else None,
            constructed_cells=int(b.sum()),constructed_columns=int((b>0).sum()),wood_cells=int(trees.sum()),
            grass_median=float(np.median(h[valid]))if valid.any()else None))
    report=dict(schema=50,source_world=str(args.world.resolve()),measured_xz_bounds=[[x0,z0],[x1,z1]],
        measured_y_bounds=[-560,-369],chunk_status=dict(Counter(status.values())),candidate_rectangles=rows,
        materials_census=dict(states),world_written=False,airport_approved=False,native_verified=False)
    (args.out/'northwest_floor_survey.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(report['chunk_status'],rows,flush=True)

if __name__=='__main__':main()
