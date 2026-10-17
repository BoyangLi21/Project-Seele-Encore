"""Complete the explicitly requested lawn-side foot lighting and larger apex ring."""
from pathlib import Path
import argparse,gzip,json
from collections import Counter
import numpy as np
from scipy.ndimage import distance_transform_cdt,binary_dilation
import survey_r52_original_complex as survey
import regional_voxels as vox
from query_blocks import iter_block_entities

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--apply',action='store_true');a=ap.parse_args()
    out=a.base/'lighting370';out.mkdir(exist_ok=True);world=a.base/'client/saves/SEELE_R53_WORLD';survey.WORLD=world;rows=[]
    lo=(-50,-473,244);hi=(113,-459,411);grid,pal=survey.measure(lo,hi)
    air=np.array([s in {'minecraft:air','minecraft:cave_air'} for s in pal]);grass=np.array([s.startswith('minecraft:grass_block') for s in pal]);panel=pal.index('projectseele:nerv_pyramid_panel')
    for y in (-468,-467):
        plane=grid[y-lo[1]];dist=distance_transform_cdt(plane!=panel,metric='taxicab')
        # Follow the measured inner edge of the existing lawn, including the
        # original foundation setback; do not infer permission to fill it.
        mask=grass[plane]&(dist<=4)&binary_dilation(air[plane])&air[grid[y-lo[1]+1]]
        for iz,ix in np.argwhere(mask):rows.append(dict(pos=[int(ix+lo[0]),y,int(iz+lo[2])],before=pal[plane[iz,ix]],after='minecraft:sea_lantern',reason='pyramid_lawn_foot_lighting',before_nbt=None,after_nbt=None))
    lo2=(-98,-545,420);hi2=(-62,-528,456);g,p=survey.measure(lo2,hi2)
    yy,zz,xx=np.ogrid[lo2[1]:hi2[1]+1,lo2[2]:hi2[2]+1,lo2[0]:hi2[0]+1];r=np.maximum(abs(xx+.5+80),abs(zz+.5-438));floor=-545+np.floor(r*68/88).astype(int)
    for rad,old,new,reason in [(9,'minecraft:ochre_froglight[axis=y]','minecraft:black_concrete','replace_small_apex_ring'),(14,'minecraft:black_concrete','minecraft:ochre_froglight[axis=y]','enlarged_apex_ring')]:
        mask=(np.floor(r)==rad)&(yy==floor)&(g==p.index(old))
        for iy,iz,ix in np.argwhere(mask):rows.append(dict(pos=[int(ix+lo2[0]),int(iy+lo2[1]),int(iz+lo2[2])],before=old,after=new,reason=reason,before_nbt=None,after_nbt=None))
    positions={tuple(r['pos']) for r in rows}
    for bounds in [(lo,hi),(lo2,hi2)]:
        for pos,tag in iter_block_entities(world,'projectseele:geofront',*bounds):assert pos not in positions,('Device',pos)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0));report=dict(world=str(world),reasons=dict(Counter(r['reason'] for r in rows)),apex_ring_width_before=18,apex_ring_width_after=28,geometry_modified=False)
    (out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    if a.apply:
        vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-1344,320))
        for r in rows:painter.exact((*r['pos'],*r['pos']),r['before'],r['after'],r['reason'])
        report['receipt']=painter.apply('pyramid_foot_and_apex_lights')
        from finish_r53_shaft_core_and_emblem import install
        install(world,out,generators_only=True);(out/'INSTALLED.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
