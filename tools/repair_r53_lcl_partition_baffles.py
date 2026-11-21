"""Close the measured fluid path between adjacent original wet bays."""
from pathlib import Path
import argparse,json
import regional_voxels as vox
from query_blocks import read_box,iter_block_entities

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();world=args.base/'CANDIDATE'
    owner=json.loads((world/'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
    fronts=sorted((g for g in owner['gates'] if g['resource'].endswith('_front')),key=lambda g:g['frame']['position'][0])
    vox.WORLD=world;vox.DIM='projectseele:geofront';vox.OUT=args.base/'lcl-partition-baffles'
    painter=vox.Painter(vertical_bounds=(-1440,320));boxes=[]
    state='minecraft:gray_stained_glass_pane[east=false,north=true,south=true,waterlogged=false,west=false]'
    for left,right in zip(fronts,fronts[1:]):
        lx,y,z=left['frame']['position'];rx,ry,rz=right['frame']['position']
        assert y==ry and z==rz and rx-lx==42 and left['width']==right['width']==33
        outer=33/2+.15+33/8+.1
        centre=(lx+rx)/2
        assert centre-.0625-(lx+outer)>=.06 and rx-outer-(centre+.0625)>=.06
        x=int(centre);box=(x,int(y),int(z)-2,x,int(y)+43,int(z))
        before=read_box(world,vox.DIM,box[:3],box[3:])
        assert not list(iter_block_entities(world,vox.DIM,box[:3],box[3:]))
        assert set(before.values())=={'minecraft:air'}
        painter.exact(box,'minecraft:air',state,'original_shared_bay_partition_fluid_baffle')
        boxes.append(box)
    painter.meta.update(original_bay_positions_retained=True,door_cassette_clearance_metres=.0625,fluid_flow_around_shared_partition_closed=True)
    folder=painter.save_plan('two_shared_wet_bay_baffles')
    if args.apply:
        assert not list(folder.glob('applied_*'))
        painter.apply('two_shared_wet_bay_baffles')
        for box in boxes:assert set(read_box(world,vox.DIM,box[:3],box[3:]).values())=={state}
    print(json.dumps(dict(boxes=boxes,cells=264,world_written=args.apply,readback=args.apply)))

if __name__=='__main__':main()
