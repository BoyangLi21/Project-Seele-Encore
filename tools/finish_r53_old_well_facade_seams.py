"""Close the measured recessed facade joints between the three retained wells."""
from pathlib import Path
from collections import Counter
import argparse,gzip,json
import numpy as np
from query_blocks import read_box,iter_block_entities
from repair_r53_reported_landings import apply
import plan_r53_old_well_enclosure as envelope

def plan(world,source,out):
    rows=[]
    graph=json.loads(gzip.decompress((world/'r53_personnel_walking_graph.json.gz').read_bytes()))
    approaches=[n for n in graph['nodes'] if 5<=n[0]<=55 and -469<=n[1]<=74 and -54<=n[2]<=5]
    for z in (4,):
        lo=(6,-466,z);hi=(54,74,z)
        envelope.LO=np.asarray(lo);envelope.HI=np.asarray(hi)
        core,_,sources=envelope.envelopes(source)
        cells=read_box(world,'projectseele:geofront',lo,hi)
        tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
        for x in list(range(6,13))+list(range(48,55)):
            for y in range(-466,75):
                p=x,y,z
                assert not core[y+466,0,x-6],('Active motion envelope',p)
                assert p not in tags,('Persistent device',p)
                assert cells[p] in ('minecraft:air','minecraft:stone','projectseele:nerv_structural_panel','minecraft:black_concrete'),(p,cells[p])
                assert not any(abs(n[0]-x)<=1 and n[1]<=y<n[1]+3 and abs(n[2]-z)<=1 for n in approaches),('Personnel approach',p)
                if cells[p]!='minecraft:black_concrete':rows.append(dict(pos=p,before=cells[p],after='minecraft:black_concrete',before_nbt=None,after_nbt=None,reason='recessed_joint_between_old_well_exterior_panels'))
    out.mkdir(parents=True,exist_ok=True)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0))
    report=dict(world=str(world),cells=len(rows),before_states=dict(Counter(r['before']for r in rows)),complete_current_machine_core_clear=True,personnel_approaches_clear=True,devices_unchanged=True,source_envelopes=[str(s)for s in sources],changes_only_external_recessed_joints=True)
    (out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('world',type=Path);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args()
    apply(a.world,a.output)if a.apply else plan(a.world,a.source,a.output)
