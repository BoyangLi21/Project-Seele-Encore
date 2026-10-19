"""Six measured ground-floor shopfronts inside existing commercial plots.

Offices and stairs above remain intact. The original middle entrance remains
the single access; detailed frontage does not introduce inaccessible doors.
"""
from pathlib import Path
import argparse,json,math
import nbtlib
import regional_voxels as v
from query_blocks import read_box,iter_block_entities,AIR
ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_R24_TV_REVIEW';OUT=ROOT/'artifacts/facility_r24/city_frontages'
PROGRAMME=[('tokyo_north/09-04','青叶书店','青葉書房 · 書籍と雑誌','newspaper_rack','document_cart'),
           ('tokyo_north/12-05','中央咖啡','中央喫茶 · COFFEE','coffee_machine','cafe_counter'),
           ('tokyo_north/07-04','北町电器','北町電器 · 修理受付','tech_bench','utility_box'),
           ('new_hakone/06-05','箱根文具','箱根文具 · 事務用品','document_cart','newspaper_rack'),
           ('new_hakone/09-04','青坂药房','青坂薬房 · 相談窓口','document_cart','cafe_counter'),
           ('new_hakone/05-05','山手茶室','山手喫茶 · TEA ROOM','coffee_machine','cafe_counter')]

def main(apply=False):
    OUT.mkdir(parents=True,exist_ok=True);v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();frontages=[];walks=[]
    sites={r['id']:r for r in json.loads((ROOT/'artifacts/world_expansion_20260907/geometry_all/places.json').read_text(encoding='utf8'))['landmarks']}
    geometry={r['name']:r for r in json.loads((ROOT/'artifacts/facility_r24/props/geometry.json').read_text())}
    for id,title,subtitle,left,right in PROGRAMME:
        site=sites[id];assert site['style']=='office';x0,x1,z0,z1=site['bounds'];f=site['floor'];cx=(x0+x1)//2
        b=read_box(WORLD,v.DIM,(x0,f-1,z1-4),(x1,f+6,z1+6));tags=dict(iter_block_entities(WORLD,v.DIM,(x0,f,z1-4),(x1,f+6,z1+6)))
        owner='r24/frontage/'+id;edits={};items=[]
        p.protect((cx-3,f,z1+1,cx+3,f,z1+5),'retained existing entrance paving')
        def put(q,state,allowed):
            assert q not in edits,(id,'duplicate edit',q)
            assert b.get(q) in allowed,(id,q,b.get(q),'placement conflict')
            edits[q]=state;p.match((*q,*q),b[q],state,owner)
        # This frontage apron joins the measured existing entrance paving.
        # A smooth full-cube surface stays level with the existing plot floor.
        for x in range(cx-12,cx+13):
            for z in range(z1+1,z1+6):
                assert b[(x,f-1,z)].split('[')[0] in {'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:polished_deepslate'}
                if abs(x-cx)>3:put((x,f,z),'projectseele:period_station_floor',{'minecraft:grass_block[snowy=false]','minecraft:smooth_stone','minecraft:polished_deepslate'})
                else:assert b[(x,f,z)] in {'minecraft:black_concrete','minecraft:grass_block[snowy=false]','minecraft:smooth_stone','minecraft:polished_deepslate'}
                for y in (f+1,f+2):assert b[(x,y,z)] in AIR or b[(x,y,z)].startswith('minecraft:iron_bars['),(id,'pedestrian apron occupied',(x,y,z))
        for x in range(cx-12,cx+13):
            for z in (z1+1,z1+2):put((x,f+4,z),'minecraft:smooth_stone_slab[type=top,waterlogged=false]',AIR)
        # The canopy meets the existing wall continuously; there are no
        # posts on the walking line. Signs sit on solid storey bands above.
        for x in range(cx-12,cx+13):assert b[(x,f+4,z1)].split('[')[0] in {'minecraft:gray_concrete','minecraft:smooth_sandstone','minecraft:light_gray_concrete','minecraft:white_concrete'}
        old=(cx+3,f+3,z1+1)
        if old in tags and '_wall_sign[' in b[old]:
            assert id.split('/')[-1] in tags[old].snbt();put(old,'minecraft:air',{b[old]})
        # Leave a full wall course above the projecting canopy so that the
        # lower text line remains visible from the existing pavement.
        sign=(cx,f+6,z1+1)
        for dx in (-1,0,1):assert b[(cx+dx,f+6,z1)] in {'minecraft:smooth_sandstone','minecraft:gray_concrete'} and b[(cx+dx,f+6,z1+1)] in AIR
        put(sign,'projectseele:period_fixture[facing=south,kind=shop_sign]',AIR)
        p.block_entities[sign]=nbtlib.Compound({'id':nbtlib.String('projectseele:period_fixture'),'x':nbtlib.Int(sign[0]),'y':nbtlib.Int(sign[1]),'z':nbtlib.Int(sign[2]),'Title':nbtlib.String(title),'Lines':nbtlib.List[nbtlib.String]([nbtlib.String(subtitle)])})
        def fixture(kind,x,z,face='south'):
            q=(x,f+1,z);assert abs(x-cx)>=4,'Preserve entrance approach'
            # Include the vending buttons' slight projection in the free
            # envelope, as well as all upper collision/picking cells.
            for dy in range(math.ceil(geometry[kind]['hi'][1])):
                assert b[(x,f+1+dy,z)] in AIR
                if kind=='vending_machine':assert b[(x,f+1+dy,z+1)] in AIR
            put(q,f'projectseele:period_fixture[facing={face},kind={kind}]',AIR)
            for offset in range(1,math.ceil(geometry[kind]['hi'][1])):put((x,f+1+offset,z),f'projectseele:period_fixture_part[offset={offset}]',AIR)
            p.block_entities[q]=nbtlib.Compound({'id':nbtlib.String('projectseele:period_fixture'),'x':nbtlib.Int(x),'y':nbtlib.Int(f+1),'z':nbtlib.Int(z),'Title':nbtlib.String(title),'Lines':nbtlib.List[nbtlib.String]([nbtlib.String('一层店铺 · 上层办公室'),nbtlib.String('沿中央入口进入，请保持通道畅通。')])})
            items.append(dict(kind=kind,position=q))
        fixture(left,cx-7,z1-3);fixture(right,cx+7,z1-3)
        fixture('vending_machine',cx+10,z1+1);fixture('letter_box',cx-10,z1+1)
        fixture('notice_board',cx-6,z1+1)
        # Existing entry and a two-metre-deep browsing aisle remain clear.
        paths=[('entry',[[cx+.5,f+1,z1+5.5],[cx+.5,f+1,z1-1.5]]),
               ('front',[[cx-11.5,f+1,z1+3.5],[cx+11.5,f+1,z1+3.5]]),
               ('interior',[[cx-8.5,f+1,z1-1.5],[cx+8.5,f+1,z1-1.5]])]
        for name,path in paths:
            for reverse in (False,True):
                route=path[::-1] if reverse else path
                walks.append(dict(id=owner+'/'+name+'/'+str(int(reverse)),start=route[0],end=route[-1],path=route))
        frontages.append(dict(id=id,title=title,bounds=site['bounds'],floor=f,original_entry=site['entry'],sign=sign,equipment=items,upper_offices_and_stairs_unchanged=True))
    p.meta.update(frontages=frontages,walk_nodes=walks,reference='Tokyu Corporation 1989 public archive views; original geometry and text, no photographs embedded')
    p.save_plan('measured_commercial_frontages')
    if apply:p.apply('measured_commercial_frontages')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Shopfronts',len(frontages),'routes',len(walks))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
