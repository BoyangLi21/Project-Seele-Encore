"""Large arrival labels at the two photographed decision points, ceiling supported."""
import argparse,nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,WORLD,ROOT
from query_blocks import iter_block_entities

OUT=ROOT/'artifacts/world_combat_r40/arrival_headers'


def main(apply=False):
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();w=MeasuredWorld()
    w.box((-363,-462,738),(-338,-459,742));w.box((-344,-463,732),(-339,-459,738));w.load()
    boards=[((-360,-461,740),'north','B1 地下都市',['大直梯 · 地面 NERV 入口','← 车站 · 总部换乘','持证进入地面设施']),
            ((-342,-462,735),'west','地下都市入口站',['↑ 站台 · 线路图','↑ 前往 NERV 总部','↓ 大直梯 · 地面入口'])]
    changes={};tags=dict(iter_block_entities(WORLD,v.DIM,(-363,-463,732),(-338,-459,742)))
    for q,face,title,rows in boards:
        normal=(0,-1) if face=='north' else (-1,0)
        for offset in (-1,0,1):
            x=q[0]+(offset if normal[1] else 0);z=q[2]+(offset if normal[0] else 0)
            bx,bz=x-normal[0],z-normal[1]
            for y in range(q[1],-459):
                changes[bx,y,bz]='projectseele:nerv_wall_panel'
            assert w.get(bx,-459,bz)=='projectseele:nerv_structural_panel'
        changes[q]=f'projectseele:station_departure_board[facing={face},wayfinding=true]'
        tag=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'Station':nbtlib.String(title),'Route':nbtlib.String('入构设施'),'Wayfinding':nbtlib.Byte(1),'PlatformCentre':nbtlib.Long(0)})
        for i,text in enumerate(rows):tag['Row'+str(i)]=nbtlib.String(text)
        if q in tags:
            assert tags[q]==tag,('Changed arrival sign',q)
        else:p.block_entities[q]=tag
    assert not (set(changes).intersection(tags)-{q for q,_,_,_ in boards}),'Existing device in header volume'
    for q,after in sorted(changes.items()):
        before=w.block(q)
        if before==after:continue
        assert before=='minecraft:air',(q,before)
        p.match((*q,*q),before,after,'r40/arrival/large_ceiling_supported_identification')
    p.meta.update(boards=[dict(position=q,facing=f,title=t,rows=r) for q,f,t,r in boards],minimum_walk_clearance=4,
                  visual_reason='Native photograph showed the small lift display was unreadable from the foyer; retain local controls and add destination-scale headers')
    p.save_plan('large_headers')
    if apply:p.apply('large_headers')


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');main(a.parse_args().apply)
