"""Mount the four existing images on their measured walls; retain room geometry."""
from pathlib import Path
import argparse, nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R42_REVIEW'
OUT=ROOT/'artifacts/rebuild_r42/wall_art'
PANELS=[
    ((20,-415,258),(.5,.5,.015),'tree',9,10,0,(20,-415,257)),
    ((28,-402,273),(.5,0,.015),'nerv',5,4.5,0,(28,-402,272)),
    ((30,-322,312),(.5,0,.015),'nerv',15,11,0,(30,-322,311)),
    ((30,-322,339),(.5,0,.985),'tree',10,12,2,(30,-322,340)),
]


def packed(q):
    x,y,z=q; value=((x&0x3ffffff)<<38)|((z&0x3ffffff)<<12)|(y&4095)
    return value if value<2**63 else value-2**64


def main(apply=False):
    w=MeasuredWorld(WORLD)
    for q,offset,art,width,height,facing,back in PANELS:w.around(q,2)
    w.load();v.WORLD=WORLD;v.OUT=OUT;p=v.Painter()
    for q,offset,art,width,height,facing,back in PANELS:
        before=w.block(q);assert before in ('minecraft:air','projectseele:wall_artwork'),(q,before)
        assert w.block(back) not in (None,'minecraft:air'),('Missing mounting wall',back)
        existing=dict(iter_block_entities(WORLD,v.DIM,q,q)).get(q)
        assert before!='minecraft:air' or existing is None,('Existing device',q)
        tag=nbtlib.Compound(dict(id=nbtlib.String('projectseele:wall_artwork'),
            x=nbtlib.Int(q[0]),y=nbtlib.Int(q[1]),z=nbtlib.Int(q[2]),Artwork=nbtlib.String(art),
            Width=nbtlib.Float(width),Height=nbtlib.Float(height),Facing=nbtlib.Int(facing),Backing=nbtlib.Long(packed(back)),
            OffsetX=nbtlib.Double(offset[0]),OffsetY=nbtlib.Double(offset[1]),OffsetZ=nbtlib.Double(offset[2])))
        if before=='minecraft:air':
            p.match((*q,*q),before,'projectseele:wall_artwork','r42/wall_art_render_anchor');p.block_entities[q]=tag
        elif existing!=tag:p.update_block_entity(q,before,existing,tag,'r42/preserve_original_plate_dimensions')
    p.meta.update(reason='Depth-tested block-entity rendering replaces unanchored late world-pass quads',panels=PANELS,
                  collision='No collision added; original command room layout and feature walls retained')
    p.save_plan('wall_art_fit')
    if apply:
        from release_combat_r36 import guard
        guard();p.apply('wall_art_fit')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
