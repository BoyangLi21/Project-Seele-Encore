"""Move surveyed airport plaques and the obscured U1 board to fixed walls."""
import argparse,copy,gzip,json
from pathlib import Path
import nbtlib
from query_blocks import read_box,iter_block_entities,AIR
from repair_r53_reported_landings import apply,DIM

def plan(world,out):
    moves=[((x,98,z),(x-18,82,z),'south',False)for x,z in ((-1970,-229),(-2075,-229),(1015,1221),(1120,1221))]
    moves += [((x,80,26),(x,75,28),'north',True)for x in (511,611)]
    moves += [((-336,-461,740),(-342,-465,740),'north',False)]
    rows=[]
    for old,new,face,arrow in moves:
        dx,dz=(0,1)if face=='south'else(0,-1)
        back=(new[0]-dx,new[1],new[2]-dz)
        points=[old,new,back];lo=tuple(min(p[k]for p in points)for k in range(3));hi=tuple(max(p[k]for p in points)for k in range(3))
        cells=read_box(world,DIM,lo,hi);tags=dict(iter_block_entities(world,DIM,lo,hi))
        assert cells[new]in AIR and new not in tags
        assert cells[back]in ('minecraft:light_gray_concrete','projectseele:nerv_structural_panel','projectseele:nerv_wall_panel'),(new,cells[back])
        tag=tags[old];next_tag=copy.deepcopy(tag)
        for key,value in zip(('x','y','z'),new):next_tag[key]=nbtlib.Int(value)
        if arrow:
            for key in ('front_text','back_text'):
                if key in next_tag:next_tag[key]['messages'][1]=nbtlib.String(json.dumps({'text':'← 航空整备库'},ensure_ascii=False))
        elif old[1]==98:
            for key in ('front_text','back_text'):
                if key in next_tag:
                    for line,text in ((2,'AUTHORIZED'),(3,'PERSONNEL')):
                        next_tag[key]['messages'][line]=nbtlib.String(json.dumps({'text':text}))
        rows += [dict(pos=old,before=cells[old],after='minecraft:air',before_nbt=tag.snbt(),after_nbt=None,reason='move_existing_plaque_to_visible_fixed_wall'),
                 dict(pos=new,before=cells[new],after=cells[old],before_nbt=None,after_nbt=next_tag.snbt(),reason='existing_personnel_approach_human_height')]
    out.mkdir(parents=True,exist_ok=True)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode('utf8'),mtime=0))
    (out/'PLAN.json').write_text(json.dumps(dict(world=str(world),moves=moves,changed_cells=len(rows),doors_aircraft_and_original_monitor_unchanged=True),ensure_ascii=False,indent=2),'utf8')
    print('Planned',len(moves),'existing label relocations')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    apply(a.world,a.output)if a.apply else plan(a.world,a.output)
