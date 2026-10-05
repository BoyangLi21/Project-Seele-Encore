"""Complete emergency entrance assembly and public door latches, with exact inverse data."""
from pathlib import Path
import argparse,copy,json,zlib
import nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,AIR

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';OUT=ROOT/'artifacts/rebuild_r44/access'
def packed(q):
    x,y,z=q;a=((x&0x3ffffff)<<38)|((z&0x3ffffff)<<12)|(y&0xfff)
    return a if a<2**63 else a-2**64
def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    OUT.mkdir(exist_ok=True);w=MeasuredWorld(WORLD);w.box((220,79,298),(234,86,306));w.load()
    tags=dict(iter_block_entities(WORLD,v.DIM,(220,79,298),(234,86,306)));v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();changes={}
    def put(q,state,role):
        before=w.block(q);assert before is not None,q
        assert q not in tags or q==(226,83,304),('Existing device',q)
        changes[q]=(state,role)
    for x in (224,228):
        for y in range(81,86):put((x,y,302),'projectseele:nerv_machine_edge','jamb')
    for x in range(224,229):put((x,84,302),'projectseele:nerv_machine_edge','lintel')
    for x in (*range(221,224),*range(229,232)):
        for y in range(81,84):put((x,y,302),'projectseele:clear_glass','complete_side_wing_r47')
    for x in range(221,232):put((x,84,302),'projectseele:nerv_machine_edge','full_width_lintel_r47')
    for x in range(225,228):
        for y in range(81,84):put((x,y,302),'minecraft:barrier','complete_personnel_aperture')
    reader=(228,82,303);put(reader,'projectseele:nerv_access_reader[facing=south]','reader')
    exit=(224,82,301);put(exit,'minecraft:stone_button[face=wall,facing=north,powered=false]','safe_inside_exit')
    old=(226,83,304);new=(231,83,303);assert old in tags and new not in tags
    for y in range(81,84):put((231,y,302),f'projectseele:nerv_sign_post[arm={str(y==83).lower()},facing=south]','board_back_stanchion')
    put(old,'minecraft:air','retire_centreline_board');put(new,'projectseele:nerv_direction_panel[facing=south,wayfinding=true]','side_entry_header')
    for q,(state,role) in changes.items():p.match((*q,*q),w.block(q),state,'r44/emergency_access/'+role)
    board=copy.deepcopy(tags[old]);board['x']=nbtlib.Int(new[0]);board['y']=nbtlib.Int(new[1]);board['z']=nbtlib.Int(new[2]);board['Station']=nbtlib.String('NERV · 地下联络入口')
    board['Row0']=nbtlib.String('↓ 地下交通层 · 金字塔');board['Row1']=nbtlib.String('请在门旁刷卡');board['Row2']=nbtlib.String('入口保持畅通');p.block_entities[new]=board
    p.block_entities[reader]=nbtlib.Compound(dict(id=nbtlib.String('projectseele:nerv_access_reader'),x=nbtlib.Int(reader[0]),y=nbtlib.Int(reader[1]),z=nbtlib.Int(reader[2]),
        Gate=nbtlib.Long(packed((225,81,302))),Exit=nbtlib.Long(packed(exit)),Width=nbtlib.Int(3),Height=nbtlib.Int(3),Clearance=nbtlib.Int(1),Style=nbtlib.Int(1),
        DoorId=nbtlib.Int(zlib.crc32(b'nerv/emergency/r44')&0x7fffffff),AlongX=nbtlib.Byte(1),Linked=nbtlib.Byte(1),Label=nbtlib.String('NERV 地下联络入口'),SwipeAt=nbtlib.Long(-1)))
    p.meta.update(scope='Complete real front door, jambs, reader, inside release and relocated board; existing descent and lift untouched',
                  source='R40 frontage put an information panel on the centreline and an opaque upper fascia hid the stair. New aperture is before the real descent.',
                  reference='TV personnel checkpoint visual language; this small city pavilion is an original circulation solution',
                  gate=[[225,81,302],[227,83,302]],reader=list(reader),exit=list(exit),validation='After real card/door traversal, expiry/occupation and reload pending')
    p.save_plan('emergency_complete_port')
    if apply:p.apply('emergency_complete_port')
    print('Complete emergency entry assembly:',len(changes),'measured cells')

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');main(a.parse_args().apply)
