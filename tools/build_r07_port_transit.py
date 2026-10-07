"""Build the P1 platforms, supported rail envelope and explicit pedestrian handoffs."""
import json,math
from dataclasses import replace
from collections import defaultdict
from pathlib import Path
import regional_voxels as vox
import quality_structures as qs
from build_r07_installations import ramp,CASES

OUT=vox.ROOT/'artifacts/world_expansion_r07';vox.OUT=OUT
if (vox.WORLD/'native_transit_r22.json').is_file():
    raise RuntimeError('The installed R22 through-service retired original P1. Do not rebuild its stations, approach, signs or piers; use the complete current R50 public reuse and active native transit source.')
p=vox.Painter()
plan=json.loads((OUT/'port_transit_plan.json').read_text(encoding='utf8'))
samples=json.loads((OUT/'port_native_transit/track_samples.json').read_text(encoding='utf8'))
bed=defaultdict(set);sweeps=set()
for rail in samples:
    for point in rail['points']:
        x,y,z=map(round,point);sweeps.add((x,y,z))
        for xx in range(x-3,x+4):
            for zz in range(z-3,z+4):bed[xx,zz].add(y)
for (x,z),levels in bed.items():
    y=min(levels);p.fill(x,y-3,z,x,y-1,z,'minecraft:gray_concrete','r07/P1/rail_bed')
for x,y,z in sorted(sweeps):
    p.fill(x-1,y,z-1,x+1,y+6,z+1,'minecraft:air','r07/P1/clearance')
    if x%24==0 and z==472:
        p.fill(x-1,32,z-2,x+1,y-4,z+2,'minecraft:polished_andesite','r07/P1/piers')
        for zz in (z-4,z+4):p.fill(x,y-1,zz,x,y+6,zz,'minecraft:gray_concrete','r07/P1/pole')
        p.fill(x,y+7,z-4,x,y+7,z+4,'minecraft:iron_block','r07/P1/catenary')
    if z%24==0 and x==576:p.fill(x-2,32,z-1,x+2,y-4,z+1,'minecraft:polished_andesite','r07/P1/depot_piers')
# New stations use the R06 finish vocabulary, retaining the verified MTR platform shapes.
qs.FLOOR='projectseele:nerv_floor_panel';qs.WALL='projectseele:nerv_wall_panel';qs.RED='projectseele:nerv_wall_datum';qs.LIGHT='projectseele:nerv_strip_light';qs.DARK='minecraft:gray_concrete'
for data in plan['platforms']:
    s=qs.Station(p,data);s.run()
    for u in (-s.half+1,s.half-1):
        for v in (-14,14):
            x,y,z=s.xyz(u,s.y-4,v);p.fill(x,32,z,x+1,y,z+1,'minecraft:polished_andesite','r07/P1/station_pier')
for i,op in enumerate(p.ops):
    if op.state.startswith('minecraft:polished_deepslate_stairs['):p.ops[i]=replace(op,state=op.state.replace('polished_deepslate','polished_andesite'))
    if op.state.startswith('minecraft:dark_oak_stairs['):
        facing=op.state.split('facing=')[1].split(',')[0];p.ops[i]=replace(op,state=f'another_furniture:dark_oak_chair[facing={facing},tucked=false,variant=1,waterlogged=false]')
# City walkway goes around the turnback buffer rather than over the live track.
for box in [(445,78,471,447,80,489),(446,78,488,516,80,490)]:
    p.fill(*box,'minecraft:gray_concrete','r07/P1/city_walk')
    x0,_,z0,x1,f,z1=box;p.fill(x0,f,z0,x1,f,z1,'projectseele:nerv_floor_panel','r07/P1/city_walk')
    p.fill(x0,f+1,z0,x1,f+3,z1,'minecraft:air','r07/P1/city_walk')
city=[[440.5,81,472.5],[446.5,81,472.5],[446.5,81,488.5],[512.5,81,488.5],[512.5,81,482.5]]
CASES.extend([dict(id='r07/P1/city_interchange',path=city),dict(id='r07/P1/city_interchange/return',path=city[::-1])])
# Harbor platform Y70 connects down to the Y68 yard by a real ramp.
p.fill(1180,67,488,1188,70,506,'minecraft:gray_concrete','r07/P1/port_walk')
p.fill(1180,70,488,1188,70,506,'projectseele:nerv_floor_panel','r07/P1/port_walk')
ramp(p,1184,1224,504,7,70,68,'P1/yard_ramp')
p.fill(1224,68,501,1270,68,507,'projectseele:nerv_floor_panel','r07/P1/yard_walk')
port=[[1184.5,71,482.5],[1184.5,71,504.5],[1224.5,69,504.5],[1264.5,69,504.5]]
CASES.extend([dict(id='r07/P1/port_interchange',path=port),dict(id='r07/P1/port_interchange/return',path=port[::-1])])
for case in qs.CASES:case['id']='r07/'+case['id']
all_cases=CASES+qs.CASES;p.meta.update(platforms=plan['platforms'],walk_cases=all_cases,native_source='port_native_transit/track_samples.json')
p.apply('port_transit_geometry');(OUT/'transit_walk_cases.json').write_text(json.dumps(all_cases,ensure_ascii=False,indent=2),encoding='utf8')
