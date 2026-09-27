"""Paint the old fixed large-lift masonry as TV-style shaft steel, outside the cage sweep."""
import argparse,json
from pathlib import Path
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,WORLD,ROOT
OUT=ROOT/'artifacts/world_combat_r40/gateway_finish'

def main(apply=False):
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();w=MeasuredWorld();w.box((-369,-472,741),(-351,97,759));w.load();changed=[]
    for y in range(-472,98):
        for x in range(-369,-350):
            for z in range(741,760):
                if x not in (-369,-351) and z not in (741,759):continue
                q=x,y,z;s=w.block(q)
                if s!='minecraft:deepslate_tiles':continue
                after='projectseele:nerv_shaft_panel'
                if y%24 in (0,1):after='projectseele:nerv_machine_edge'
                p.match((*q,*q),s,after,'r40/fixed_gateway_shaft_finish');changed.append(q)
    p.meta.update(cells=len(changed),cage_volume_untouched=[-367,-468,743,-353,94,757],controller_and_sensors_unchanged=True,reference='TV industrial massing: painted continuous panels with sparse structural seams, not decorative stone brick')
    p.save_plan('fixed_shaft_steel')
    if apply:p.apply('fixed_shaft_steel')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Fixed shaft finish',len(changed))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');main(a.parse_args().apply)
