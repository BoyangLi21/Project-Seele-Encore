"""Original textures, models and blockstate for the NERV staff gate (NervStaffGateR65, R65 owner feedback 2 item 3):
brushed steel cabinets with a red band and a NERV plate, a card reader with its lamp on the entry end, and two
full-height tinted glass leaves. Everything here is drawn by this script. Run from the repository root."""
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path('src/main/resources/assets/projectseele')
TEX, MODEL, STATE, ITEM = ROOT / 'textures/block', ROOT / 'models/block', ROOT / 'blockstates', ROOT / 'models/item'
rng = random.Random(653)


def save(im, name):
    im.save(TEX / f'{name}.png')


# brushed steel: horizontal grain
im = Image.new('RGBA', (16, 16))
for y in range(16):
    row = rng.randint(-6, 6)
    for x in range(16):
        v = 196 + row + rng.randint(-3, 3)
        im.putpixel((x, y), (v - 4, v, v + 4, 255))
save(im, 'nerv_gate_steel')
im = Image.new('RGBA', (16, 16))
for y in range(16):
    for x in range(16):
        v = 46 + rng.randint(-3, 3)
        im.putpixel((x, y), (v, v, v + 3, 255))
save(im, 'nerv_gate_dark')
im = Image.new('RGBA', (16, 16))
for y in range(16):
    for x in range(16):
        im.putpixel((x, y), (186 + rng.randint(-6, 6), 24, 30, 255))
save(im, 'nerv_gate_red')
# tinted glass with a brighter frame line
im = Image.new('RGBA', (16, 16), (170, 214, 226, 86))
for i in range(16):
    for p in ((i, 0), (i, 15), (0, i), (15, i)):
        im.putpixel(p, (220, 236, 240, 170))
for i in range(3, 9):
    im.putpixel((i, 12 - i), (240, 250, 255, 140))                  # a glint
save(im, 'nerv_gate_glass')
for name, rim, core in (('nerv_gate_lamp_green', (20, 60, 40), (80, 255, 150)), ('nerv_gate_lamp_red', (60, 20, 20), (255, 70, 60))):
    im = Image.new('RGBA', (16, 16), rim + (255,))
    for x in range(16):
        for y in range(16):
            r = ((x - 7.5) ** 2 + (y - 7.5) ** 2) ** .5
            if r < 6.5:
                t = r / 6.5
                im.putpixel((x, y), tuple(int(core[i] * (1 - t * .5)) for i in range(3)) + (255,))
    save(im, name)
# NERV plate: white letters drawn as strokes on red (no font file, no logo)
im = Image.new('RGBA', (32, 16), (176, 20, 26, 255))
d = ImageDraw.Draw(im)
W = (240, 240, 240, 255)
# N
d.line((3, 12, 3, 3), W, 2); d.line((3, 3, 8, 12), W, 2); d.line((8, 12, 8, 3), W, 2)
# E
d.line((11, 3, 11, 12), W, 2); d.line((11, 3, 15, 3), W, 2); d.line((11, 7, 14, 7), W, 2); d.line((11, 12, 15, 12), W, 2)
# R
d.line((18, 12, 18, 3), W, 2); d.line((18, 3, 21, 3), W, 2); d.line((22, 4, 22, 6), W, 2); d.line((18, 7, 21, 7), W, 2); d.line((20, 8, 23, 12), W, 2)
# V
d.line((25, 3, 27, 12), W, 2); d.line((27, 12, 29, 3), W, 2)
save(im, 'nerv_gate_plate')

ALL = ('north', 'south', 'east', 'west', 'up', 'down')


def box(a, b, tex, faces=ALL, uv=None):
    f = {}
    for s in faces:
        t = tex if isinstance(tex, str) else tex.get(s)
        if t is None:
            continue
        f[s] = {'texture': '#' + t}
        if uv and s in uv:
            f[s]['uv'] = uv[s]
    return {'from': list(a), 'to': list(b), 'faces': f}


def model(name, elements, textures, translucent=False):
    m = {'parent': 'minecraft:block/block', 'textures': dict(textures, particle=textures['s']), 'elements': elements}
    if translucent:
        m['render_type'] = 'minecraft:translucent'
    (MODEL / f'{name}.json').write_text(json.dumps(m, indent=1), 'utf8')


T = {'s': 'projectseele:block/nerv_gate_steel', 'd': 'projectseele:block/nerv_gate_dark', 'r': 'projectseele:block/nerv_gate_red',
     'g': 'projectseele:block/nerv_gate_glass', 'lg': 'projectseele:block/nerv_gate_lamp_green', 'lr': 'projectseele:block/nerv_gate_lamp_red',
     'p': 'projectseele:block/nerv_gate_plate'}


# modelled facing north: travel towards -z, the lane spans x, cabinets at both x edges, the reader at the entry (+z) end
def cabinet(x0, x1, outer):
    side = 'west' if outer == 'west' else 'east'
    parts = [box((x0, 0, 1), (x1, 15, 15), 's'),
             box((x0, 15, 1), (x1, 16.5, 15), {'up': 'd', 'north': 'd', 'south': 'd', 'east': 'd', 'west': 'd'}),   # dark top
             box((x0 - .01, 10, 1.5), (x1 + .01, 11.5, 14.5), {'east': 'r', 'west': 'r'}),                        # red band
             box((x0 - .02, 4, 4), (x1 + .02, 8, 12), {side: 'p'}, uv={side: [0, 0, 16, 8]})]                    # NERV plate, outer side
    return parts


def lower(card, open_):
    els = cabinet(0, 2.5, 'west') + cabinet(13.5, 16, 'east')
    # reader on the right cabinet's entry end: dark pad with the lamp, tilted face up
    els.append(box((13.75, 16.5, 11), (15.75, 17.5, 14.5), {'up': 'd', 'north': 'd', 'south': 'd', 'east': 'd', 'west': 'd'}))
    els.append(box((14.25, 17.5, 11.75), (15.25, 17.6, 13.75), {'up': 'lg' if card else 'lr'}))
    els.append(box((0.25, 16.5, 11), (2.25, 17.5, 14.5), {'up': 'd', 'north': 'd', 'south': 'd', 'east': 'd', 'west': 'd'}))
    els.append(box((0.75, 17.5, 11.75), (1.75, 17.6, 13.75), {'up': 'lg'}))
    els += leaves(16, open_)
    return els


def leaves(top, open_):
    if open_:
        # swung back flat against the cabinets
        return [box((2.5, 0, 2), (3.1, top, 8), 'g'), box((12.9, 0, 2), (13.5, top, 8), 'g')]
    return [box((2.5, 0, 7.7), (8, top, 8.3), 'g'), box((8, 0, 7.7), (13.5, top, 8.3), 'g'),
            box((7.9, 0, 7.6), (8.1, top, 8.4), 's', ('north', 'south', 'up'))]                   # meeting edge strip


for card in (True, False):
    for open_ in (True, False):
        model(f'nerv_staff_gate_lower_{"card" if card else "free"}_{"open" if open_ else "closed"}', lower(card, open_), T, True)
for open_ in (True, False):
    model(f'nerv_staff_gate_upper_{"open" if open_ else "closed"}', leaves(12, open_) + [box((2.5, 11.5, 7.6), (13.5, 12, 8.4), 's')] * (not open_), T, True)
rot = {'north': 0, 'east': 90, 'south': 180, 'west': 270}
variants = {}
for f, r in rot.items():
    for open_ in ('true', 'false'):
        for card in ('true', 'false'):
            m = f'projectseele:block/nerv_staff_gate_lower_{"card" if card == "true" else "free"}_{"open" if open_ == "true" else "closed"}'
            variants[f'card={card},facing={f},half=lower,open={open_}'] = dict(model=m, **({'y': r} if r else {}))
            m = f'projectseele:block/nerv_staff_gate_upper_{"open" if open_ == "true" else "closed"}'
            variants[f'card={card},facing={f},half=upper,open={open_}'] = dict(model=m, **({'y': r} if r else {}))
(STATE / 'nerv_staff_gate.json').write_text(json.dumps({'variants': variants}, indent=1), 'utf8')
(ITEM / 'nerv_staff_gate.json').write_text(json.dumps({'parent': 'projectseele:block/nerv_staff_gate_lower_card_closed'}, indent=1), 'utf8')
print('written')
