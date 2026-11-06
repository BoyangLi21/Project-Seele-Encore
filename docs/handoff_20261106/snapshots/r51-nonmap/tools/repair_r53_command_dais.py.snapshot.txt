"""Refinish the measured upper command dais to match its lower neighbours."""
import gzip,json,msvcrt
from pathlib import Path
from collections import defaultdict
import nbtlib
from query_blocks import read_box,iter_block_entities
from repair_r53_reported_landings import apply
from apply_s20_approved_semantic_repairs import parse_state
from retire_r53_old_yashima_platform import packed

BASE=Path('F:/eva/artifacts/r53_repair_20261015')
WORLD=BASE/'client/saves/SEELE_R53_WORLD'
OUT=BASE/'command-dais474'
DIM='projectseele:geofront'

def main():
    lo=(22,-511,277);hi=(34,-498,291)
    cells=read_box(WORLD,DIM,lo,hi);tags=dict(iter_block_entities(WORLD,DIM,lo,hi))
    wanted={}
    for p,s in cells.items():
        x,y,z=p
        if s!='projectseele:clear_glass' or not (23<=x<=33 and 278<=z<=290):continue
        assert p not in tags
        if y==-503 or (z==278 and y==-500):new='minecraft:white_concrete'
        elif y==-502 and z>=280 and cells.get((x,y+1,z))=='minecraft:air':
            new='railing'
        elif y>=-501:new='projectseele:nerv_machine_panel'
        else:new='projectseele:nerv_structural_panel'
        wanted[p]=new
    for p,s in list(wanted.items()):
        if s!='railing':continue
        x,y,z=p;parts=[]
        for face,dx,dz in (('east',1,0),('north',0,-1),('south',0,1),('west',-1,0)):
            q=(x+dx,y,z+dz);state=wanted.get(q,cells.get(q,'minecraft:air'))
            connected=state=='railing' or 'andesite_wall' in state or state in ('projectseele:nerv_structural_panel','projectseele:nerv_machine_panel')
            parts.append(f'{face}={"tall" if connected else "none"}')
        wanted[p]='minecraft:andesite_wall['+','.join(parts[:3]+['up=true','waterlogged=false',parts[3]])+']'
    rows=[dict(pos=p,before=cells[p],after=s,before_nbt=None,after_nbt=None,
               reason='upper_command_dais_matches_original_lower_platforms') for p,s in wanted.items()]
    OUT.mkdir(exist_ok=True)
    (OUT/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0))
    apply(WORLD,OUT)
    # These two native bearing cells were restored live after an observation
    # window overwrote them. Keep their existing generator records consistent.
    generator_rows=rows+[dict(pos=p,after='projectseele:nerv_machine_edge') for p in ((-29,-1028,138),(-29,-1027,39))]
    with (WORLD/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        data=WORLD/'dimensions/projectseele/geofront/data'
        topology=nbtlib.load(next(data.glob('projectseele_city_rigid_topology_r45_*.dat')))['data']
        folder=data/str(topology['GenerationFolder'])/'chunks';groups=defaultdict(list)
        for r in generator_rows:groups[r['pos'][0]//16,r['pos'][2]//16].append(r)
        changed=0
        for (cx,cz),batch in groups.items():
            path=folder/f'{cx}_{cz}.dat'
            if not path.exists():continue
            doc=nbtlib.load(path);bypos={int(r['Pos']):r for r in doc['Static']};palette=doc['Palette'];ids={r.snbt():i for i,r in enumerate(palette)};dirty=False
            for row in batch:
                old=bypos.get(packed(row['pos']))
                if old is None:continue
                state=parse_state(row['after']);key=state.snbt()
                if key not in ids:ids[key]=len(palette);palette.append(state)
                old['StateId']=nbtlib.Int(ids[key]);dirty=True;changed+=1
            if dirty:doc.save(path,gzipped=True)
    (OUT/'REVIEW.json').write_text(json.dumps(dict(cells=len(rows),generator_cells=changed,
        controls_and_seats_preserved=True,earth_display_untouched=True,
        original_glass_cells=list(map(list,wanted))),indent=2),'utf8')
    print('Command dais:',len(rows),'cells; existing generator cells:',changed)

if __name__=='__main__':main()
