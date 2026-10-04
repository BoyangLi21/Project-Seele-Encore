"""Read-only R45 school/station measurements through query_blocks only."""
from pathlib import Path
import argparse
import json
from collections import Counter

from measure_world_r40 import MeasuredWorld
from query_blocks import AIR, iter_block_entities

ROOT = Path(__file__).resolve().parents[1]
DIM = 'projectseele:geofront'
SCHOOL = ((216, 48, -800), (314, 102, -668))
HAKONE = ((-1560, 90, 610), (-1396, 148, 770))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--world', type=Path, default=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW')
    p.add_argument('--out', type=Path, default=ROOT/'artifacts/rebuild_r45/school_hakone_agent/survey')
    a = p.parse_args()
    assert a.out.resolve() != a.world.resolve() and a.world.resolve() not in a.out.resolve().parents
    a.out.mkdir(parents=True, exist_ok=True)
    summaries = {}
    for name, (lo, hi) in [('school', SCHOOL), ('hakone', HAKONE)]:
        w = MeasuredWorld(a.world, DIM)
        w.box(lo, hi)
        w.load()
        tags = {q: tag.snbt() for q, tag in iter_block_entities(a.world, DIM, lo, hi)}
        top, census = [], Counter()
        for z in range(lo[2], hi[2]+1):
            for x in range(lo[0], hi[0]+1):
                solid = None
                water = None
                for y in range(hi[1], lo[1]-1, -1):
                    s = w.get(x, y, z)
                    census[s] += 1
                    if s and s.split('[')[0] == 'minecraft:water' and water is None:
                        water = y
                    if s and s.split('[')[0] not in AIR | {'minecraft:water','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'} and solid is None:
                        solid = [y, s]
                top.append({'pos':[x,z], 'top':solid, 'water':water})
        (a.out/(name+'_columns.json')).write_text(json.dumps(top,indent=2),'utf8')
        (a.out/(name+'_block_entities.json')).write_text(json.dumps([{'pos':q,'snbt':tag} for q,tag in tags.items()],indent=2),'utf8')
        floors = [72,77,82,87] if name=='school' else [104,110,118,125,130,137,141]
        with (a.out/(name+'_plans.txt')).open('w',encoding='utf8') as f:
            for y in floors:
                f.write(f'Y={y}, columns X={lo[0]}..{hi[0]}, Z={lo[2]}..{hi[2]}, N=decreasing Z\n')
                for z in range(lo[2],hi[2]+1):
                    chars = []
                    for x in range(lo[0],hi[0]+1):
                        s=w.get(x,y,z) or '?';n=s.split('[')[0]
                        chars.append(' ' if n in AIR else '~' if n=='minecraft:water' else 'D' if 'door' in n or 'ticket_barrier' in n else '=' if 'escalator' in n or 'stairs' in n else 'G' if 'glass' in n or 'pane' in n else 'p' if 'platform' in n else 't' if 'tactile' in n else 'B' if (x,y,z) in tags else ',' if n in {'minecraft:grass_block','minecraft:dirt','minecraft:stone'} else '#')
                    f.write(f'{z:5} '+''.join(chars)+'\n')
        summaries[name]={'bounds':[lo,hi],'chunks':len(w.selected),'full_chunks':sum(s=='full' for s in w.status.values()),'block_entities':len(tags),'census':census.most_common(30)}
        print(name, 'chunks',len(w.selected),'block entities',len(tags), 'census',census.most_common(10),flush=True)
    (a.out/'measurement.json').write_text(json.dumps({'world':str(a.world.resolve()),'dimension':DIM,'world_written':False,'surveys':summaries},indent=2),'utf8')


if __name__ == '__main__':
    main()
