"""Finish authored stair endpoints, old crew piers and generator retirement."""
from pathlib import Path
import json,gzip,math,msvcrt
import nbtlib
from query_blocks import read_box,iter_block_entities,AIR
from repair_r53_reported_landings import apply
from retire_r53_old_yashima_platform import packed
from apply_s20_approved_semantic_repairs import parse_state

BASE=Path('F:/eva/artifacts/r53_repair_20261015')
WORLD=BASE/'client/saves/SEELE_R53_WORLD';OUT=BASE/'map-bindings252';DIM='projectseele:geofront'

def main():
    OUT.mkdir(exist_ok=True);rows=[]
    cells=read_box(WORLD,DIM,(-45,-1015,346),(-41,-1014,347))
    for z,shape in ((346,'landing_top'),(347,'transition_top')):
        for start,direction in ((-45,True),(-42,False)):
            for lane in (0,1):
                p=(start+lane,-1015,z);side='left' if lane==0 else 'right'
                s=f'mtr:escalator_step[direction={str(direction).lower()},facing=north,orientation={shape},side={side},status=true]'
                if cells[p]!=s:rows.append(dict(pos=p,before=cells[p],after=s,before_nbt=None,after_nbt=None,reason='restore_authored_upper_escalator_landing'))
    # Restore the exact R50 authored natural ridge formula only underneath the
    # now-retired crew steps. Adjacent streets and all other mountain are kept.
    cells=read_box(WORLD,DIM,(66,72,502),(71,108,528));tags=dict(iter_block_entities(WORLD,DIM,(66,72,502),(71,108,528)))
    for x in (66,67,69,70):
        for z in range(502,529):
            ground=max((y for y in range(72,85) if cells[x,y,z].split('[')[0] in {'minecraft:grass_block','minecraft:dirt','minecraft:stone'}),default=79)
            shoulder=max(0,1-max(0,abs(x-30)-25)/95)
            def lobe(c,h,peak):
                f=max(0,1-abs(z-c)/h);return (peak-ground)*f*f*(3-2*f)
            top=math.floor(ground+max(lobe(458,21,109),lobe(486,43,103))*shoulder*shoulder*(3-2*shoulder))
            top=max(ground,top+math.floor(.6*math.sin(x*.24+z*.3)+.5*math.sin(x*.47-z*.11)))
            for y in range(max(88,top+1),108):
                p=(x,y,z)
                if cells[p]=='minecraft:stone' and p not in tags:rows.append(dict(pos=p,before=cells[p],after='minecraft:air',before_nbt=None,after_nbt=None,reason='retired_authored_crew_stair_stone_bearing'))
    (OUT/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0))
    apply(WORLD,OUT)
    with (WORLD/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        data=WORLD/'dimensions/projectseele/geofront/data'
        topology=nbtlib.load(next(data.glob('projectseele_city_rigid_topology_r45_*.dat')))['data']
        folder=data/str(topology['GenerationFolder'])/'chunks';latest={}
        for name in ('reported-landings237','old-yashima249','reported-exteriors250','inspection-rooms251','map-bindings252'):
            for r in json.loads(gzip.decompress((BASE/name/'EXACT_DELTA.json.gz').read_bytes())):latest[tuple(r['pos'])]=r
        grouped={}
        for p,r in latest.items():grouped.setdefault((p[0]//16,p[2]//16),[]).append(r)
        changed_count=0
        for (cx,cz),batch in grouped.items():
            path=folder/f'{cx}_{cz}.dat'
            if not path.exists():continue
            doc=nbtlib.load(path);bypos={int(r['Pos']):r for r in doc['Static']};palette=doc['Palette'];ids={r.snbt():i for i,r in enumerate(palette)};changed=False
            for row in batch:
                old=bypos.get(packed(row['pos']))
                if old is None:continue
                state=parse_state(row['after']);key=state.snbt()
                if key not in ids:ids[key]=len(palette);palette.append(state)
                old['StateId']=nbtlib.Int(ids[key]);old.pop('NBT',None)
                if row.get('after_nbt'):old['NBT']=nbtlib.parse_nbt(row['after_nbt'])
                changed=True;changed_count+=1
            if changed:doc.save(path,gzipped=True)
    (OUT/'GENERATORS.json').write_text(json.dumps({'existing_owned_cells_updated':changed_count,'map_cells':len(rows)},indent=2))
    print('Map endpoints and retired piers:',len(rows),'existing generator records:',changed_count)

if __name__=='__main__':main()
