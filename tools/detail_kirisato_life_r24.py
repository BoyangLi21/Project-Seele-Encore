"""Measured entrance bicycle shelters in the six documented Kirisato bars.

The UR Suwa photograph informs the modest concrete canopy, bicycles and
grass/paving boundary. It is a reference, not an imported game texture.
"""
from pathlib import Path
import argparse,json
import nbtlib
import regional_voxels as v
from query_blocks import read_box,iter_block_entities,AIR

ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_R24_TV_REVIEW'
OUT=ROOT/'artifacts/facility_r24/kirisato_life'
ENTRIES=[(-2878,-1112),(-2790,-1112),(-2702,-1112),(-2878,-1016),(-2790,-1016),(-2702,-1016)]

def main(apply=False):
    OUT.mkdir(parents=True,exist_ok=True);v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();shelters=[];walks=[]
    for index,(x,z) in enumerate(ENTRIES):
        label=chr(65+index);owner='r24/kirisato_'+label
        b=read_box(WORLD,v.DIM,(x+1,69,z-5),(x+15,75,z))
        tags=dict(iter_block_entities(WORLD,v.DIM,(x+1,69,z-5),(x+15,75,z)))
        oldsign=(x+7,73,z-1);assert 'oak_wall_sign[facing=north' in b[oldsign]
        assert label+'棟' in tags[oldsign].snbt(),(label,'wrong building sign')
        p.protect((x+10,70,z-5,x+14,75,z),'original stairwell entry')
        def setcell(q,state,allowed):
            assert b.get(q) in allowed,(label,q,b.get(q),'placement conflict')
            p.match((*q,*q),b[q],state,owner)
        for xx in range(x+2,x+10):
            for zz in range(z-4,z):
                setcell((xx,70,zz),'minecraft:smooth_stone',{'minecraft:grass_block[snowy=false]','minecraft:smooth_stone'})
                for yy in (71,72,73):
                    if (xx,yy,zz)!=oldsign:assert b.get((xx,yy,zz)) in AIR,(label,'canopy envelope occupied',(xx,yy,zz))
                roof='minecraft:light_gray_concrete' if xx in (x+2,x+9) and zz==z-1 else 'minecraft:smooth_stone_slab[type=top,waterlogged=false]'
                setcell((xx,73,zz),roof,AIR|{b[oldsign]})
        for xx in (x+2,x+9):
            for yy in (71,72):
                setcell((xx,yy,z-1),'minecraft:light_gray_concrete',AIR)
        # Back-supported cantilever beams meet the roof and existing landing
        # wall; the original five-wide entry remains entirely outside the patch.
        bikes=[]
        for xx in (x+4,x+7):
            q=(xx,71,z-3)
            for dx in (-1,0,1):
                for dy in (0,1):assert b.get((xx+dx,71+dy,z-3)) in AIR
            setcell(q,'projectseele:period_fixture[facing=south,kind=parked_bicycle]',AIR)
            setcell((xx,72,z-3),'projectseele:period_fixture_part[offset=1]',AIR)
            p.block_entities[q]=nbtlib.Compound({'id':nbtlib.String('projectseele:period_fixture'),'x':nbtlib.Int(xx),'y':nbtlib.Int(71),'z':nbtlib.Int(z-3),'Title':nbtlib.String('霧里团地 · 居民自行车')})
            bikes.append(q)
        # The deep canopy hides labels above it from ground level. Keep the
        # identity on the same solid wall, below the canopy and above bicycles.
        q=(x+7,72,z-1)
        for dx in (-1,0,1):
            assert b[(q[0]+dx,72,z)]=='minecraft:light_gray_concrete'
            assert b[(q[0]+dx,72,z-1)] in AIR
        setcell(q,'projectseele:period_fixture[facing=north,kind=shop_sign]',AIR)
        p.block_entities[q]=nbtlib.Compound({'id':nbtlib.String('projectseele:period_fixture'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'Title':nbtlib.String(label+'栋 · 霧里团地'),'Lines':nbtlib.List[nbtlib.String]([nbtlib.String('KIRISATO  /  自転車置場')])})
        shelters.append(dict(building=label,bounds=[x+2,70,z-4,x+9,74,z-1],bicycles=bikes,sign=q,entry_preserved=[x+10,70,z-5,x+14,75,z],source_sign=tags[oldsign].snbt()))
        for name,a,c in [('entry',[x+12.5,71,z-5.5],[x+12.5,71,z+.5]),('shelter',[x+10.5,71,z-1.5],[x+3.5,71,z-1.5])]:
            for reverse in (False,True):
                start,end=(c,a) if reverse else (a,c)
                walks.append(dict(id=f'r24/kirisato/{label}/{name}/{int(reverse)}',start=start,end=end,path=[start,end]))
    p.meta.update(shelters=shelters,walk_nodes=walks,source='UR Suwa primary photograph; adapted scale, not a surveyed 1:1 replica',room_402_unchanged=True)
    p.save_plan('documented_estate_entry_shelters')
    if apply:p.apply('documented_estate_entry_shelters')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8')
    print('Shelters',len(shelters),'bicycles',sum(len(s['bicycles']) for s in shelters),'native routes',len(walks))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
