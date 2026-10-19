"""Move the twelve R24 nameplates hidden behind their own entrance canopies."""
import argparse,copy,gzip,json
from pathlib import Path
import nbtlib
from query_blocks import AIR,read_box,iter_block_entities
from repair_r53_reported_landings import apply
from station_sign_readers_r44 import NORMAL

SHOP={(-256,85,-306),(-144,85,-306),(24,85,-250),(-1336,109,546),(-1528,109,610),(-1592,109,610)}
ESTATE={(x,74,z) for x in (-2871,-2783,-2695) for z in (-1017,-1113)}

def plan(world,evidence,out):
    source=json.loads((evidence/'plates_inventory.json').read_text('utf8'))
    labels={tuple(r['pos']):r for r in source['rows']};rows=[];moves=[]
    for old in sorted(SHOP|ESTATE):
        entry=labels[old];x,y,z=old;new=(x,y+(1 if old in SHOP else -2),z)
        lo=(x-2,min(y,new[1]),z-1);hi=(x+2,max(y,new[1]),z+1)
        cells=read_box(world,source['dimension'],lo,hi);tags=dict(iter_block_entities(world,source['dimension'],lo,hi))
        original=nbtlib.parse_nbt(entry['nbt']);face='south' if old in SHOP else 'north';dx,dz=NORMAL[face]
        assert cells[old]==f'projectseele:period_fixture[facing={face},kind=shop_sign]' and tags[old]==original
        assert cells[new] in AIR and new not in tags
        # The whole three-metre nameplate must sit against the original fixed
        # wall, above the shop canopy or under the estate bicycle canopy.
        for lateral in (-1,0,1):
            support=(new[0]+lateral,new[1],new[2]-dz)
            assert cells[support] in {'minecraft:smooth_sandstone','minecraft:gray_concrete','minecraft:light_gray_concrete'},(support,cells[support])
        updated=copy.deepcopy(original)
        for k,v in zip(('x','y','z'),new):updated[k]=nbtlib.Int(v)
        reason='same_authored_shop_or_estate_entrance_clear_of_r24_canopy'
        rows.extend([dict(pos=old,before=cells[old],after='minecraft:air',before_nbt=original.snbt(),after_nbt=None,reason=reason),dict(pos=new,before=cells[new],after=cells[old],before_nbt=None,after_nbt=updated.snbt(),reason=reason)])
        labels[old]=dict(entry,pos=new,nbt=updated.snbt());moves.append(dict(old=old,new=new,text=entry['text']))
    out.mkdir(parents=True,exist_ok=True)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode(),mtime=0))
    (out/'PLAN.json').write_text(json.dumps(dict(world=str(world),moves=moves,changed_cells=len(rows),source='detail_city_frontages_r24.py and detail_kirisato_life_r24.py; native shop720/estate720 views'),ensure_ascii=False,indent=2),'utf8')
    (out/'inventory.json').write_text(json.dumps(dict(source,rows=list(labels.values())),ensure_ascii=False,indent=2),'utf8')
    print('Canopy nameplates',len(moves),'exact cells',len(rows))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path,required=True);p.add_argument('--evidence',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    if a.apply:apply(a.world,a.output)
    else:plan(a.world,a.evidence,a.output)
