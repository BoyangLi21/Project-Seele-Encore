"""Repair measured missing basin walls/floors and original escalator steps."""
from pathlib import Path
import argparse,gzip,json
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
from query_blocks import read_box,iter_block_entities

def repair(base,world):
    owner=json.loads((world/'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
    vox.WORLD=world;vox.DIM='projectseele:geofront';vox.OUT=base/'reported-wet-bay-repairs'/world.name
    painter=vox.Painter(vertical_bounds=(-1440,320));summary={};all_owned=set();closures=set()
    for u in owner['units']:
        layers=json.loads(gzip.decompress((world/u['lcl']['cells_file']).read_bytes()))
        owned={tuple(c['position']) for row in layers for c in row};all_owned.update(owned)
        # The immutable original fill volume defines its wetted faces. The
        # centre doorway retains its real moving controller; only its missing
        # side jambs and missing bottom liner are restored here.
        gate=next(g for g in owner['gates'] if g['resource']==f'bay_{u["variant"]}_front')
        front=int(gate['frame']['position'][2])
        table=gate['collision_steps']
        if isinstance(table,dict):table=json.loads(gzip.decompress((world/table['cells_file']).read_bytes()))
        door_cells={tuple(c['position']) for row in table for c in row if c['closed']!='minecraft:air'}
        bottom=min(p[1] for p in owned)-1
        for x,y,z in owned:
            if y==bottom+1:closures.add((x,bottom,z))
            if z==front+1 and (x,y,front) not in door_cells:closures.add((x,y,front))
    lo=(-40,-1094,275);hi=(102,-1019,360)
    survey.WORLD=world;a,palette=survey.measure(lo,hi)
    def actual(at):
        x,y,z=at;return palette[int(a[y-lo[1],z-lo[2],x-lo[0]])]
    seal_count=0;flow_count=0
    for at in sorted(closures):
        old=actual(at)
        if old=='minecraft:air' or old.startswith('projectseele:lcl'):
            new='projectseele:nerv_floor_panel' if at[1]==-1063 else 'projectseele:nerv_machine_panel'
            painter.exact((*at,*at),old,new,'complete_original_wet_basin_liner_and_fixed_jambs');seal_count+=1
    lcl_ids=[i for i,s in enumerate(palette) if s.startswith('projectseele:lcl')]
    for iy,iz,ix in np.argwhere(np.isin(a,lcl_ids)):
        at=(int(ix+lo[0]),int(iy+lo[1]),int(iz+lo[2]))
        if at in all_owned or at in closures:continue
        painter.exact((*at,*at),palette[int(a[iy,iz,ix])],'minecraft:air','escaped_hangar_lcl_only');flow_count+=1
    # Restore missing steps from the actual frozen source, including both
    # sides of the three original boarding galleries. Never fill their air.
    steps=0
    for cx in (-12,30,72):
        lo2=(cx-7,-1016,347);hi2=(cx+7,-1014,360)
        before=read_box(base/'WORLD',vox.DIM,lo2,hi2);now=read_box(world,vox.DIM,lo2,hi2)
        tags=dict(iter_block_entities(base/'WORLD',vox.DIM,lo2,hi2))
        for at,state in before.items():
            if not state.startswith('mtr:escalator_step'):continue
            current=now[at]
            damaged_end=(current.startswith('mtr:escalator_step[')
                         and 'orientation=flat' in state
                         and ('orientation=landing_top' in current or 'orientation=landing_bottom' in current))
            if current=='minecraft:air' or damaged_end:
                # Breaking a flat moving walk also converts its neighbouring
                # steps into end caps. Replacing just the missing cells leaves
                # those four rendered gaps in the otherwise complete tread.
                painter.exact((*at,*at),current,state,'original_boarding_escalator_complete_tread_state')
                if at in tags:painter.block_entities[at]=tags[at]
                steps+=1
    painter.meta.update(fixed_basin_cells=seal_count,escaped_lcl_removed=flow_count,original_escalator_steps=steps)
    if painter.ops:painter.apply('measured_three_wet_bays_and_escalators')
    # Verify actual delivery states, rather than treating the plan as applied.
    measured=read_box(world,vox.DIM,lo,hi)
    for at in closures:
        assert measured[at]!='minecraft:air' and not measured[at].startswith('projectseele:lcl'),at
    assert not any(s.startswith('projectseele:lcl') and at not in all_owned for at,s in measured.items())
    print(json.dumps(dict(world=str(world),seals=seal_count,escaped_lcl=flow_count,escalator=steps,readback=True)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--world',type=Path,required=True);a=p.parse_args();repair(a.base,a.world)
