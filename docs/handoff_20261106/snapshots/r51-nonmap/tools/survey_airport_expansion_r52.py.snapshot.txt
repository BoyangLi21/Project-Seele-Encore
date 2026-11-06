"""Root measured apron and full aircraft departure volume, read-only."""
import json
from collections import Counter
import numpy as np
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from query_blocks import iter_block_entities

out=BASE/'underground_airport_expansion';out.mkdir(exist_ok=True)
lo=(-940,-516,-365);hi=(-515,-330,-175)
states,palette=measure(lo,hi);np.savez_compressed(out/'SOURCE.npz',origin=lo,states=states,palette=palette)
names=[s.split('[')[0]for s in palette]
soil=np.isin(states,[i for i,s in enumerate(names)if s in ('minecraft:grass_block','minecraft:dirt','minecraft:stone')])
yy=np.arange(lo[1],hi[1]+1)[:,None,None];ground=np.max(np.where(soil,yy,-32768),axis=0)
constructed=[s for s in palette if not s.startswith('minecraft:')or s.startswith(('minecraft:barrier','minecraft:iron_block','minecraft:concrete'))]
mask=np.zeros_like(states,bool);mask[-479-lo[1]:-330-lo[1]+1,-350-lo[2]:-190-lo[2]+1,-930-lo[0]:-531-lo[0]+1]=True
counts={s:int(np.count_nonzero(mask&(states==palette.index(s))))for s in constructed};counts={s:n for s,n in counts.items()if n}
devices=[dict(position=p,id=str(t['id']))for p,t in iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',lo,hi)]
report=dict(world_written=False,bounds=[lo,hi],proposed_stands=[[-640,-464,-270],[-840,-464,-270]],
            original_stand_retained=[-440,-464,-270],new_apron_bounds=[[-930,-478,-350],[-531,-476,-190]],
            ground_range=[int(ground.min()),int(ground.max())],constructed_counts=counts,devices=devices)
(out/'SURVEY.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
