"""Original thin diagonal stair guards; no external mesh or texture conversion."""
import json
import math
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / 'src/main/resources/assets/projectseele'


def build():
    variants = {}
    for left in (False, True):
        x = 15.12 if left else 0
        elements = []
        def element(start, end, rotation=None):
            row = dict(from_=start, to=end, faces={f: {'texture': '#metal', 'uv': [0, 0, 16, 16]}
                for f in ('up', 'down', 'north', 'south', 'west', 'east')})
            row['from'] = row.pop('from_')
            if rotation: row['rotation'] = rotation
            elements.append(row)
        element([x, -8, 0], [x+.88, 6.88, .88])
        element([x, 8, 15.12], [x+.88, 22.88, 16])
        for centre in (4, 14):
            element([x, centre-.4, 8-8*math.sqrt(2)], [x+.88, centre+.4, 8+8*math.sqrt(2)],
                    dict(origin=[x, centre, 8], axis='x', angle=-45, rescale=False))
        name = 'personnel_stair_guard_r53_' + ('left' if left else 'right')
        model = dict(ambientocclusion=False,
                     textures={'metal': 'projectseele:block/nerv_machine_edge',
                               'particle': 'projectseele:block/nerv_machine_edge'}, elements=elements)
        (ASSETS/'models/block'/f'{name}.json').write_text(json.dumps(model, indent=2)+'\n', 'utf8')
        for face, angle in (('south', 0), ('west', 90), ('north', 180), ('east', 270)):
            variants[f'facing={face},left={str(left).lower()}'] = {'model': 'projectseele:block/'+name, 'y': angle}
    (ASSETS/'blockstates/personnel_stair_guard_r53.json').write_text(json.dumps({'variants': variants}, indent=2)+'\n', 'utf8')


if __name__ == '__main__': build()
