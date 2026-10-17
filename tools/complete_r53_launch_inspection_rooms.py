"""Nine connected viewing rooms and paired native escalators, current save only."""
from pathlib import Path
from collections import Counter
import argparse,copy,gzip,json
import nbtlib
from query_blocks import read_box,iter_block_entities,AIR
from repair_r53_reported_landings import apply

DIM='projectseele:geofront';FLOOR='projectseele:nerv_floor_panel';WALL='projectseele:nerv_wall_panel';EDGE='projectseele:nerv_structural_panel'

def plan(world,out):
    cells={};tags={};wanted={};newtags={};reasons={}
    def read(a,b):cells.update(read_box(world,DIM,a,b));tags.update(iter_block_entities(world,DIM,a,b))
    def put(p,s,why):
        assert p in cells,p
        assert p not in tags,('Retained device',p)
        wanted[p]=s;reasons[p]=why
    def box(a,b,s,why):
        for x in range(a[0],b[0]+1):
            for z in range(a[2],b[2]+1):
                for y in range(a[1],b[1]+1):put((x,y,z),s,why)
    def sign(p,lines):
        put(p,'minecraft:oak_wall_sign[facing=west,waterlogged=false]','room_wayfinding')
        face=nbtlib.Compound({'messages':nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':s},ensure_ascii=False)) for s in lines]),'color':nbtlib.String('black'),'has_glowing_text':nbtlib.Byte(1)})
        newtags[p]=nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(p[0]),'y':nbtlib.Int(p[1]),'z':nbtlib.Int(p[2]),'front_text':face,'back_text':copy.deepcopy(face),'is_waxed':nbtlib.Byte(1)})
    read((-53,-1032,10),(-29,-1024,142));read((-53,-1032,342),(-39,-1010,369))
    rooms=[]
    for bank,centre in ((1,124),(2,76),(3,28)):
        for index,dz in enumerate((-12,0,12)):
            z=centre+dz;why=f'bank_{bank}_connected_viewing_room_{index+1}'
            box((-46,-1031,z-4),(-29,-1024,z+4),WALL,why)
            box((-45,-1030,z-3),(-30,-1025,z+3),'minecraft:air',why)
            box((-46,-1031,z-4),(-29,-1031,z+4),FLOOR,why)
            box((-46,-1030,z-1),(-46,-1027,z+1),'minecraft:air',why)
            box((-29,-1029,z-3),(-29,-1026,z+3),'minecraft:light_gray_stained_glass',why)
            for y in (-1030,-1025):box((-29,y,z-4),(-29,y,z+4),EDGE,why)
            for x in range(-43,-31):put((x,-1024,z),'projectseele:nerv_strip_light[lit=true]',why)
            for x in range(-43,-36):put((x,-1030,z+3),'minecraft:polished_andesite_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]',why)
            label=('轨道观察室','发射装置观察室','夹具检修观察室')[index]
            sign((-47,-1028,z+3),[f'{bank}号发射区',label,'入口 →','主梯沿廊道向南'])
            rooms.append(dict(bank=bank,purpose=label,entry=[-46,-1030,z],window=[-29,-1028,z],accessible=True))
    # The measured void between the gallery and the sealed LCL wall receives
    # a two-way escalator. It joins the actual -1030 and -1014 landings.
    for n in range(20):
        z=365-n;y=-1031+max(0,min(16,n-1))
        shape='landing_bottom' if n==0 else 'transition_bottom' if n==1 else 'slope' if n<=16 else 'transition_top' if n==17 else 'flat' if n==18 else 'landing_top'
        for x in range(-46,-39):
            for yy in range(-1031,y+6):
                s=EDGE if yy<y else FLOOR if yy==y else WALL if x in (-46,-40) or yy==y+5 else 'minecraft:air'
                put((x,yy,z),s,'inspection_to_boarding_escalator')
        for start,direction in ((-45,True),(-42,False)):
            for lane in (0,1):
                x=start+lane;side='left' if lane==0 else 'right'
                put((x,y,z),f'mtr:escalator_step[direction={str(direction).lower()},facing=north,orientation={shape},side={side},status=true]','paired_native_escalator')
                put((x,y+1,z),f'mtr:escalator_side[facing=north,orientation={shape},side={side}]','paired_native_escalator')
        put((-43,y,z),'minecraft:polished_andesite_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]' if shape in ('slope','transition_top') else FLOOR,'central_manual_stair')
    for z in (366,367):
        for x in range(-46,-39):
            put((x,-1031,z),FLOOR,'lower_escalator_landing')
            for y in range(-1030,-1026):put((x,y,z),WALL if x==-40 else 'minecraft:air','lower_escalator_landing')
    for z in (364,365,366,367):
        for y in range(-1030,-1026):put((-46,y,z),'minecraft:air','lower_gallery_connection')
    for z in (345,346,347):
        for y in range(-1014,-1010):put((-46,y,z),'minecraft:air','upper_boarding_connection')
        for x in range(-46,-39):
            if z==345 or x in (-46,-43,-40):put((x,-1015,z),FLOOR,'upper_boarding_landing')
    sign((-47,-1028,363),['登机整备层 ↑','双向扶梯 / 步梯','下层：发射区检修廊','上层：三机插入栓入口'])
    rows=[]
    for p,s in wanted.items():
        tag=newtags.get(p);snbt=tag.snbt() if tag is not None else None
        if cells[p]!=s or snbt is not None:rows.append(dict(pos=p,before=cells[p],after=s,before_nbt=None,after_nbt=snbt,reason=reasons[p]))
    out.mkdir(parents=True,exist_ok=True)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode('utf8'),mtime=0))
    report=dict(world=str(world),cells=len(rows),rooms=rooms,stairs=dict(bottom=[-45,-1030,365],top=[-45,-1014,346],paired_native=True),reasons=dict(Counter(r['reason'] for r in rows)))
    (out/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('Inspection rooms:',len(rooms),'cells:',len(rows))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args();apply(a.world,a.output) if a.apply else plan(a.world,a.output)
