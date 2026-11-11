"""Camera views for the E5 candidates: one per house (door face, or an aerial look), plus area overviews."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from blocks import FACING

HERE = Path(__file__).parent
houses = json.load(open(HERE / 'houses.json', encoding='utf8'))
doors = {tuple(d['pos']): d for d in json.load(open(HERE / 'doors.json'))}
views = []
for h in houses:
    bx0, bz0, bx1, bz1 = h['bbox']
    cx, cz = (bx0 + bx1) / 2, (bz0 + bz1) / 2
    if h['doors']:
        d = doors[tuple(h['doors'][0])]
        nx, nz = FACING[d['facing']]
        side = 1
        for k, s in (('front', 1), ('back', -1)):
            if (d['sides'][k]['blocked'] or d['sides'][k]['step']) and any(d['sides'][k]['natural'][:2]):
                side = s
                break
        x, y, z = d['pos']
        views.append(dict(name=f"{h['id']}-door", target=[x, y + 1, z], dir=[nx * side, nz * side], dist=6, rise=2.5))
    size = max(bx1 - bx0, bz1 - bz0, 6)
    views.append(dict(name=f"{h['id']}-air", target=[cx, h['ymax'], cz], dir=[0.6, 1], dist=size + 10, rise=size * 0.7 + 8))
overviews = [
    ('north-town-w', [-150, 80, -585]), ('north-town-c', [0, 75, -620]), ('north-town-e1', [100, 75, -660]),
    ('north-town-e2', [250, 76, -715]), ('south-residential', [200, 92, 543]),
]
for name, t in overviews:
    views.append(dict(name=name, target=t, dir=[0.3, 1], dist=70, rise=55, wait=120))
json.dump(views, open(sys.argv[1], 'w'), indent=0)
print(len(views))
