from pathlib import Path
import json
BASE=Path('F:/eva/artifacts/r53_repair_20261015')
OUT=BASE/'map-bindings252'
d=json.loads((BASE/'personnel-access-proposal/REVIEW.json').read_text('utf8'))
assert 'whole_hall_walk_cells' in d and 'lobby_paths' in d
for c in (124,76,28):
    for dz in (-12,0,12):
        z=c+dz
        d['whole_hall_walk_cells'].extend([x,-1030,zz] for x in range(-45,-29) for zz in range(z-3,z+3))
        d['whole_hall_walk_cells'].extend([x,-1030,zz] for x in (-47,-46) for zz in range(z-1,z+2))
d['whole_hall_walk_cells'].extend([x,-1030,z] for x in range(-48,-40) for z in (366,367))
d['whole_hall_walk_cells'].extend([x,-1014,z] for x in range(-48,-40) for z in (345,346,347))
stair=[[x,-1030,367] for x in range(-48,-42)]+[[-43,-1030,366]]+[[-43,-1030+max(0,min(16,n-1)),365-n] for n in range(20)]+[[-43,-1014,345]]
d['authored_stairs']=[stair, [[x,-1014,345] for x in range(-43,-49,-1)]]
(OUT/'ACCESS.json').write_text(json.dumps(d,ensure_ascii=False),'utf8')
print('Declared repaired rooms and stair connections added')
