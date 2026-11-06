"""Move the original R40 sign to the public corridor side of its real wall."""
import argparse,copy,json
import nbtlib
from query_blocks import read_box,iter_block_entities
from r52_spatial_plan import BASE
import regional_voxels as vox


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=BASE/'WORLD_R52';old=(124,77,280);back=(124,77,279);new=(124,77,282)
    measured=read_box(world,'projectseele:geofront',(124,76,278),(124,78,283));tags=dict(iter_block_entities(world,'projectseele:geofront',old,old))
    assert measured[old]=='projectseele:nerv_direction_panel[facing=south,wayfinding=true]'
    assert measured[new]=='minecraft:air'and measured[back]=='projectseele:nerv_wall_panel'
    assert measured[(124,77,281)]=='projectseele:nerv_wall_panel'
    assert all(measured[(124,y,279)]=='minecraft:air'for y in (76,78))
    tag=copy.deepcopy(tags[old]);assert str(tag['id'])=='projectseele:station_departure_board'
    for key,value in zip(('x','y','z'),new):tag[key]=nbtlib.Int(value)
    vox.WORLD=world;vox.OUT=BASE/'navigation_rebuild/surface_sign';vox.DIM='projectseele:geofront'
    p=vox.Painter(vertical_bounds=(-960,320));stage='original_board_on_actual_corridor_face'
    assert not list((vox.OUT/stage).glob('applied_*'))
    for q in(old,back):p.exact((*q,*q),measured[q],'minecraft:air','R52_retire_original_R40_board_and_its_single_backing_cube')
    p.exact((*new,*new),measured[new],measured[old],'R52_mount_existing_board_on_retained_corridor_wall');p.block_entities[new]=tag
    p.meta.update(root_author=True,original_board=old,new_board=new,retained_backing=[124,77,281],reason='Original sign was behind the solid corridor wall; retain its identity and mount on the reader side',native_verified=False)
    out=p.save_plan(stage)
    if args.apply:p.apply(stage)
    (out/'PLAN.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':main()
