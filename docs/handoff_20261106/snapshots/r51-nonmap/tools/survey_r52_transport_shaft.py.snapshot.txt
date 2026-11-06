"""Root transport shaft candidate survey; no excavation or runtime defaults."""
import argparse,json
from pathlib import Path
from collections import Counter
import numpy as np
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from query_blocks import iter_block_entities
import survey_r52_original_complex as survey

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);args=ap.parse_args()
    base=args.base.resolve();world=base/'WORLD';survey.WORLD=world
    assert(base/'BASELINE.json').exists()
    out=base/'air_transport_shaft';out.mkdir(exist_ok=True)
    lo=(-1234,-485,-826);hi=(-1006,270,-604)
    assert not(out/'SOURCE_EXTENDED.npz').exists(),'Reuse the measured source instead of replacing its authority'
    a,p=measure(lo,hi);np.savez_compressed(out/'SOURCE_EXTENDED.npz',origin=lo,states=a,palette=p)
    unnatural={s:int(np.count_nonzero(a==i))for i,s in enumerate(p)if not s.startswith('minecraft:')or any(k in s for k in ('concrete','barrier','glass','planks','bricks','rail'))};unnatural={s:n for s,n in unnatural.items()if n}
    devices=[dict(position=q,id=str(t['id']))for q,t in iter_block_entities(world,'projectseele:geofront',lo,hi)]
    soil=np.array([s.split('[')[0]in('minecraft:grass_block','minecraft:dirt','minecraft:stone','minecraft:sand')for s in p]);y=np.arange(lo[1],hi[1]+1)[:,None,None]
    surface=np.max(np.where(soil[a]&(y>0),y,-32768),axis=0);underground=np.max(np.where(soil[a]&(y< -350),y,-32768),axis=0)
    report=dict(world_written=False,world=str(world),centre_xz=[-1120,-720],bounds=[lo,hi],nonnatural=unnatural,devices=devices,
        surface_soil_min_max=[int(surface.min()),int(surface.max())],surface_soil_median=float(np.median(surface)),underground_soil_min_max=[int(underground.min()),int(underground.max())],
        intended='Large aircraft shaft remote from both launch banks and city; opening/pad checked against actual source geometry and terrain')
    (out/'SURVEY.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
