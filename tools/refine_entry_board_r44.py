"""Attach the existing entry legend to a measured grounded post, with full-NBT preservation."""
from pathlib import Path
import argparse,copy
import nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/access/entry_board_stanchion'


def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    w=MeasuredWorld(WORLD);original=MeasuredWorld(ROOT/'artifacts/rebuild_r44/source_world_backup')
    for reader in (w,original):reader.box((230,79,301),(232,85,304));reader.load()
    tags=dict(iter_block_entities(WORLD,v.DIM,(230,79,301),(232,85,304)))
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter()
    for y in range(80,83):
        q=(231,y,303);assert w.block(q)=='projectseele:nerv_machine_edge' and q not in tags
        before_source=original.block(q)
        assert before_source==('projectseele:nerv_floor_panel' if y==80 else 'minecraft:air')
        p.match((*q,*q),w.block(q),before_source,'r44/access/retire_incomplete_pedestal')
    assert w.block((231,80,302))=='projectseele:nerv_floor_panel'
    for y in range(81,84):
        q=(231,y,302);assert w.block(q)=='minecraft:air' and q not in tags
        p.match((*q,*q),w.block(q),f'projectseele:nerv_sign_post[arm={str(y==83).lower()},facing=south]',
            'r44/access/continuous_grounded_board_mount')
    q=(231,83,303);before=tags[q];after=copy.deepcopy(before)
    after['Station']=nbtlib.String('地面联络口');after['Route']=nbtlib.String('NERV')
    for field,text in [('Row0','↓ 地下交通层'),('Row1','金字塔／机库'),('Row2','门旁刷卡')]:after[field]=nbtlib.String(text)
    p.update_block_entity(q,w.block(q),before,after,'r44/access/short_readable_legend')
    p.meta.update(scope='Existing entry sign mount, exact original floor restoration and continuous rear bracket',
        device_aperture_preserved=True,reader_and_exit_unchanged=True,full_board_nbt=True,
        evidence='Actual shader photo revealed the compact panel bottom sits above the old pedestal; shape has its back at Z303',
        visual_self_review='Pending new actual mounted-sign picture')
    if apply:p.apply('grounded_entry_legend')
    else:p.save_plan('grounded_entry_legend')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
