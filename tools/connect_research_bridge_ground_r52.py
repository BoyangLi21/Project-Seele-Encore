"""Reconnect the retained R09 research bridge to its measured ground approach."""
import argparse,copy,json
import nbtlib
import regional_voxels as vox
from query_blocks import read_box,iter_block_entities
from r52_spatial_plan import BASE


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=BASE/'WORLD_R52';lo=(143,-467,395);hi=(151,-454,403)
    measured=read_box(world,'projectseele:geofront',lo,hi)
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
    old=(148,-459,400);new=(149,-459,399)
    assert set(tags)=={old}
    assert all(measured[(x,-467,z)]=='minecraft:grass_block[snowy=false]'for x in range(143,150)for z in range(395,404))
    assert measured[(150,-462,399)]=='projectseele:nerv_floor_panel'
    desired={}
    for x in range(143,145):
        for z in range(395,404):desired[x,-467,z]='projectseele:nerv_floor_panel'
    for x in range(145,150):
        y=-466+(x-145)
        for z in range(395,404):
            for j in range(-467,y):desired[x,j,z]='projectseele:nerv_structural_panel'
            desired[x,y,z]='minecraft:smooth_quartz_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]'
        for z in(395,403):
            desired[x,y,z]='projectseele:nerv_structural_panel'
            desired[x,y+1,z]=measured[x,y+1,z] if measured[x,y+1,z]=='projectseele:nerv_wall_panel' else 'projectseele:clear_glass'
    # The existing header stays; the original device faces the stair approach.
    desired[old]='minecraft:air'
    for y in(-458,-457):
        assert measured[(148,y,400)]=='minecraft:chain[axis=y,waterlogged=false]'
        desired[148,y,400]='minecraft:air'
        desired[149,y,399]='minecraft:chain[axis=y,waterlogged=false]'
    desired[new]='projectseele:nerv_direction_panel[facing=west,wayfinding=true]'
    assert measured[149,-456,399]=='projectseele:nerv_structural_panel'
    tag=copy.deepcopy(tags[old])
    for k,n in zip(('x','y','z'),new):tag[k]=nbtlib.Int(n)
    tag['Station']=nbtlib.String('科研区 · 地表接驳')
    tag['Route']=nbtlib.String('科研连廊')
    for k,t in zip(('Row0','Row1','Row2'),('直行：科研区','身后下阶：地下地表','总部入口：沿地表导向')):tag[k]=nbtlib.String(t)
    # Geometric direction arrows are replaced after the actual graph rebuild.
    vox.WORLD=world;vox.OUT=BASE/'navigation_rebuild/research_interface';vox.DIM='projectseele:geofront'
    p=vox.Painter(vertical_bounds=(-960,320));stage='retained_research_bridge_ground_stair'
    assert not list((vox.OUT/stage).glob('applied_*'))
    changed={q:s for q,s in desired.items()if measured[q]!=s}
    for q,s in changed.items():
        assert q==old or measured[q]in{'minecraft:air','minecraft:grass_block[snowy=false]','minecraft:chain[axis=y,waterlogged=false]'},(q,measured[q])
        p.exact((*q,*q),measured[q],s,'R52_retained_research_bridge_ground_connection')
    p.block_entities[new]=tag
    p.meta.update(root_author=True,old_bridge_preserved=True,other_stations_and_rails_untouched=True,
                  approach_ground_top=-466,bridge_floor_top=-461,clear_stair_width=7,
                  source_review=str(BASE/'navigation_rebuild/research_interface_review/CURRENT.npz'),
                  original_sign=old,new_sign=new,native_verified=False)
    out=p.save_plan(stage)
    if args.apply:p.apply(stage)
    (out/'PLAN.json').write_text(json.dumps(dict(p.meta,changed_cells=len(changed),world_written=args.apply),ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(changed_cells=len(changed),world_written=args.apply,stage=str(out))))


if __name__=='__main__':main()
