"""Use the union of native rail samples so graded track beds cannot erase one another."""
from collections import defaultdict
import json
from regional_voxels import Painter,OUT
from regional_architecture import DARK,AIR,stairs

samples=json.loads((OUT/'transit2/track_samples.json').read_text(encoding='utf-8'))
bed=defaultdict(set);points=set()
for rail in samples:
    if rail['mode']!='TRAIN':continue
    for point in rail['points']:
        x,y,z=map(round,point);points.add((x,y,z))
        for xx in range(x-3,x+4):
            for zz in range(z-3,z+4):bed[xx,zz].add(y)
p=Painter()
for (x,z),ys in bed.items():
    ordered=sorted(ys);bottom=ordered[0]
    for before,after in zip(ordered,ordered[1:]):
        if after-before>6:
            p.fill(x,bottom-3,z,x,bottom-1,z,DARK,'rail/continuous_graded_bed','owned');bottom=after
    p.fill(x,bottom-3,z,x,bottom-1,z,DARK,'rail/continuous_graded_bed','owned')
for x,y,z in points:p.fill(x-1,y,z-1,x+1,y+5,z+1,AIR,'rail/final_native_sweep','owned')
stairs(p,30,441,-467,5,'north','hq/station_stair_last_handoff',7,'owned')
from regional_architecture import headquarters_arrival_stair_sides_r46
headquarters_arrival_stair_sides_r46(p)
p.apply('continuous_track_beds')
