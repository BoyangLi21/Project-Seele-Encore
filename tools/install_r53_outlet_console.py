"""Extend the measured existing three-unit command desk by its third target row."""
from pathlib import Path
import argparse,json
import regional_voxels as vox
from query_blocks import read_box

def main():
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--base',type=Path,required=True);a=p.parse_args()
    frame=json.loads((a.world/'r52/headquarters.json').read_text('utf8'))['translation'];assert frame==[0,-93,0]
    vox.WORLD=a.world;vox.DIM='projectseele:geofront';vox.OUT=a.base/'outlet-console'/a.world.name
    painter=vox.Painter(vertical_bounds=(-1440,320))
    before=read_box(a.world,vox.DIM,(32,-501,285),(33,-499,287));rows=[]
    for variant in range(3):
        z=287-variant;back=(33,-499,z);button=(32,-499,z)
        assert before[(33,-500,z)]=='projectseele:clear_glass'
        assert before[back]==before[button]=='minecraft:air'
        painter.exact((*back,*back),before[back],'projectseele:nerv_machine_panel','existing_command_desk_third_target_backing')
        painter.exact((*button,*button),before[button],'minecraft:birch_button[face=wall,facing=west,powered=false]','hakone_combined_prepare_launch')
        for row,target in enumerate(('geofront','surface','hakone')):rows.append(dict(variant=variant,target=target,position=[32,-501+row,z]))
    painter.meta.update(controls=rows,npc_physical_press=True)
    painter.apply('existing_command_desk_three_target_rows')
    after=read_box(a.world,vox.DIM,(32,-501,285),(33,-499,287))
    assert all('button[' in after[tuple(row['position'])] for row in rows)
    print(json.dumps(dict(world=str(a.world),controls=9,added_buttons=3,readback=True)))

if __name__=='__main__':main()
