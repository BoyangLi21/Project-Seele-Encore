"""Original textures, block models and blockstates for the R65 street furniture (StreetFurnitureR65): Japanese
concrete utility poles, overhead lines, horizontal three-lamp signals and steel signal poles. Everything here is
drawn by this script; no outside art. Run from the repository root: python tools/gen_street_furniture_r65.py"""
import json
import random
from pathlib import Path

from PIL import Image

ROOT = Path('src/main/resources/assets/projectseele')
TEX, MODEL, STATE, ITEM = ROOT / 'textures/block', ROOT / 'models/block', ROOT / 'blockstates', ROOT / 'models/item'
for p in (TEX, MODEL, STATE, ITEM):
    p.mkdir(parents=True, exist_ok=True)
rng = random.Random(65)


def noisy(name, base, spread=8, streaks=0, size=16):
    im = Image.new('RGBA', (size, size))
    col_shift = [rng.randint(-streaks, streaks) for _ in range(size)]
    for x in range(size):
        for y in range(size):
            d = rng.randint(-spread, spread) + col_shift[x]
            im.putpixel((x, y), tuple(max(0, min(255, c + d)) for c in base) + (255,))
    im.save(TEX / f'{name}.png')


def lamp(name, rim, core, glow):
    im = Image.new('RGBA', (16, 16), rim + (255,))
    for x in range(16):
        for y in range(16):
            r = ((x - 7.5) ** 2 + (y - 7.5) ** 2) ** .5
            if r < 7.2:
                t = min(1, r / 7.2)
                c = tuple(int(core[i] * (1 - t) + glow[i] * t) for i in range(3))
                if (x + y) % 3 == 0 and r < 6:      # LED dot pattern
                    c = tuple(min(255, v + 18) for v in c)
                im.putpixel((x, y), c + (255,))
    im.save(TEX / f'{name}.png')


noisy('street_pole_concrete', (184, 182, 174), 6, 4)
noisy('street_steel_galv', (156, 162, 166), 7, 2)
noisy('street_signal_housing', (128, 132, 134), 4)
noisy('street_signal_back', (34, 34, 36), 3)
noisy('street_wire', (22, 22, 24), 2)
noisy('street_insulator', (226, 224, 214), 5)
noisy('street_transformer', (138, 146, 138), 5, 2)
noisy('street_crossarm', (96, 98, 100), 5)
lamp('street_lamp_green_on', (30, 30, 32), (210, 255, 240), (20, 200, 160))
lamp('street_lamp_amber_off', (30, 30, 32), (96, 80, 40), (70, 56, 26))
lamp('street_lamp_red_off', (30, 30, 32), (90, 40, 36), (64, 24, 22))
# luminaire underside: warm white
im = Image.new('RGBA', (16, 16), (255, 246, 214, 255))
for x in range(16):
    for y in range(16):
        if x in (0, 15) or y in (0, 15):
            im.putpixel((x, y), (120, 124, 126, 255))
im.save(TEX / 'street_luminaire.png')

ALL = ('north', 'south', 'east', 'west', 'up', 'down')


def box(a, b, tex, faces=ALL, shade=True):
    f = {}
    for side in faces:
        f[side] = {'texture': '#' + tex if isinstance(tex, str) else '#' + tex[side]}
    e = {'from': list(a), 'to': list(b), 'faces': f}
    if not shade:
        e['shade'] = False
    return e


def model(name, elements, textures, parent='minecraft:block/block'):
    textures = dict(textures)
    textures.setdefault('particle', textures[next(iter(textures))])
    (MODEL / f'{name}.json').write_text(json.dumps({'parent': parent, 'textures': textures, 'elements': elements}, indent=1), 'utf8')


def shaft(y0, y1, tex='c'):
    # one box per segment, about a third of a block across; stacked segments cull their touching faces, so a pole
    # costs four quads per block like the wall post it replaces (a rounder cross-section tripled the city's quads)
    e = box((5.5, y0, 5.5), (10.5, y1, 10.5), tex)
    if y0 == 0:
        e['faces']['down']['cullface'] = 'down'
    if y1 == 16:
        e['faces']['up']['cullface'] = 'up'
    return [e]


T = {'c': 'projectseele:block/street_pole_concrete', 's': 'projectseele:block/street_crossarm', 'i': 'projectseele:block/street_insulator',
     'w': 'projectseele:block/street_wire', 'g': 'projectseele:block/street_steel_galv', 't': 'projectseele:block/street_transformer',
     'l': 'projectseele:block/street_luminaire'}
# Utility pole, modelled facing north: the crossarm runs north-south (across the street), the road is to the north.
model('utility_pole_shaft', shaft(0, 16), {'c': T['c']})
cross = [box((7, 11, -6), (9, 13, 22), 's'),                              # crossarm across the street
         box((7.5, 7, 11), (8.5, 11, 16), 's'), box((7.5, 7, 0), (8.5, 11, 5), 's')]   # braces
ins = []
for z in (-4.5, 18.5):
    ins.append(box((7.25, 13, z), (8.75, 15, z + 1.5), 'i'))
ins.append(box((7.25, 16, 7.25), (8.75, 18, 8.75), 'i'))                  # middle insulator on the pole cap
top = shaft(0, 16) + [box((5, 15.5, 5), (11, 16, 11), 'c')] + cross + ins + [box((10.5, 5, 7.5), (12, 7, 8.5), 's')]  # cable hook
model('utility_pole_top', top, {k: T[k] for k in 'csi'})
lamp_arm = [box((7.5, 6, -10), (8.5, 7, 6), 'g'), box((7.5, 6, 5), (8.5, 10, 6), 'g'),
            box((6.5, 4.5, -14), (9.5, 6.5, -8), {'north': 'g', 'south': 'g', 'east': 'g', 'west': 'g', 'up': 'g', 'down': 'l'})]
model('utility_pole_lamp', top + lamp_arm, {k: T[k] for k in 'csigl'})
# a lamp pole for roads without an overhead line: the same pole and lamp bracket, capped, no crossarm
model('utility_pole_street', shaft(0, 16) + [box((5, 15.5, 5), (11, 16.5, 11), 'c')] + lamp_arm, {k: T[k] for k in 'csgl'})
can = [box((11, 1, 4.5), (17, 11, 11.5), 't'), box((10.5, 11, 5), (17.5, 12, 11), 't'), box((10.5, 2, 7.5), (11.5, 3, 8.5), 's'),
       box((10.5, 9, 7.5), (11.5, 10, 8.5), 's'), box((13.5, 12, 7.5), (14.5, 14, 8.5), 'i')]
model('utility_pole_transformer', shaft(0, 16) + [box((7.5, 1, 11), (8.5, 2, 12), 's')] + [dict(e) for e in can], {k: T[k] for k in 'csti'})
# Overhead line along z: the two outer conductors in line with the crossarm insulators and the telecom cable lower
# down; no top faces (nobody looks down on them), three quads a strand, which keeps 15,000 cells of line cheap.
wires = [box((-3.9, 15.2, 0), (-3.1, 15.8, 16), 'w', ('down', 'east', 'west')), box((19.1, 15.2, 0), (19.9, 15.8, 16), 'w', ('down', 'east', 'west')),
         box((11.4, 5.6, 0), (12.6, 6.8, 16), 'w', ('down', 'east', 'west'))]
model('power_line', wires, {'w': T['w']})
# Signal pole and the horizontal three-lamp head (modelled facing north, the bracket reaching back to the pole one block south).
model('signal_pole', [box((6.5, 0, 6.5), (9.5, 16, 9.5), 'g')], {'g': T['g']})
model('signal_pole_top', [box((6.5, 0, 6.5), (9.5, 12, 9.5), 'g'), box((6, 12, 6), (10, 13, 10), 'g')], {'g': T['g']})
H = {'h': 'projectseele:block/street_signal_housing', 'b': 'projectseele:block/street_signal_back', 'gl': 'projectseele:block/street_lamp_green_on',
     'al': 'projectseele:block/street_lamp_amber_off', 'rl': 'projectseele:block/street_lamp_red_off', 'g': T['g']}
head = [box((-8, 3, 5), (24, 12, 10), {'north': 'b', 'south': 'h', 'east': 'h', 'west': 'h', 'up': 'h', 'down': 'h'})]
# from a driver facing it, green is on the left: the head faces north, so the driver looks south and left is east
for x0, t in ((14, 'gl'), (4.5, 'al'), (-5, 'rl')):
    head.append(box((x0, 4, 4.6), (x0 + 7, 11, 5), {'north': t}, ('north',), shade=t != 'gl'))
    head.append(box((x0 - .5, 11, 1.5), (x0 + 7.5, 11.6, 5), 'h'))                      # visor top
    head.append(box((x0 - .5, 6, 1.5), (x0, 11, 5), 'h', ('east', 'west', 'up', 'down')))
    head.append(box((x0 + 7, 6, 1.5), (x0 + 7.5, 11, 5), 'h', ('east', 'west', 'up', 'down')))
head += [box((7, 6.5, 10), (9, 8.5, 24), 'g'), box((6.5, 8.5, 9.5), (9.5, 10.5, 11), 'g')]   # bracket to the pole
model('traffic_signal', head, H)
# blockstates
rot = {'north': 0, 'east': 90, 'south': 180, 'west': 270}
st = {f'facing={f},part={p}': {'model': f'projectseele:block/utility_pole_{p}', 'y': r} for f, r in rot.items()
      for p in ('shaft', 'top', 'lamp', 'transformer', 'street')}
for k, v in st.items():
    if v['y'] == 0:
        del v['y']
(STATE / 'utility_pole.json').write_text(json.dumps({'variants': st}, indent=1), 'utf8')
(STATE / 'power_line.json').write_text(json.dumps({'variants': {'axis=z': {'model': 'projectseele:block/power_line'},
                                                                 'axis=x': {'model': 'projectseele:block/power_line', 'y': 90}}}, indent=1), 'utf8')
sig = {f'facing={f}': ({'model': 'projectseele:block/traffic_signal', 'y': r} if r else {'model': 'projectseele:block/traffic_signal'}) for f, r in rot.items()}
(STATE / 'traffic_signal.json').write_text(json.dumps({'variants': sig}, indent=1), 'utf8')
(STATE / 'signal_pole.json').write_text(json.dumps({'variants': {'top=false': {'model': 'projectseele:block/signal_pole'},
                                                                  'top=true': {'model': 'projectseele:block/signal_pole_top'}}}, indent=1), 'utf8')
for n, m in (('utility_pole', 'utility_pole_lamp'), ('power_line', 'power_line'), ('traffic_signal', 'traffic_signal'), ('signal_pole', 'signal_pole_top')):
    (ITEM / f'{n}.json').write_text(json.dumps({'parent': f'projectseele:block/{m}'}, indent=1), 'utf8')
print('written')
