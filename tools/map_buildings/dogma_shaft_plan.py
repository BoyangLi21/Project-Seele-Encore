"""Proposal geometry for the Central Dogma main shaft (ROADMAP 5.2a) and the interface for the falling/climbing code.

  python dogma_shaft_plan.py <survey.npz> <out dir>

Writes shaft_r66.json (shaft box, top and bottom openings, bulkhead planes, ledges, climbable faces) and annotated
sections. Nothing here writes a world. EVA collision box: 17 wide, 60 tall (EvaScale NORMAL_* x WORLD_MULTIPLIER).
Two kinds of platform, after the motion side's measurements (Fable, fable-r66-shaft-interface-20261122): stations
22 x 14 to stand and fight on, every ~55 blocks, with 62 clear over an EVA standing on one; and 12 x 6 hand ledges in a
spiral every 16 blocks, only to hang on. Rung grooves ring the walls every 8 blocks (1 block deep into the lining). The
planner checks the station clearance against every other platform and that the middle stays at least 17 wide.
"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

X0, X1, Z0, Z1 = 104, 135, 226, 257          # shaft interior
LIP, FLOOR = -1056, -1265                     # aisle floor at the top, lobby floor (feet stand on FLOOR + 1)
EVA_W, EVA_H = 17, 60
LEDGE_LEN, LEDGE_DEPTH, LEDGE_STEP = 12, 6, 16
BULKHEADS = [-1091, -1126, -1161, -1196, -1231]   # 35 apart (owner: every 30-40); 2 blocks thick
DOOR_HALL = dict(x=(94, 95), z=(230, 254), y=(-1051, -989))     # 25 wide, 63 tall opening in the hall's east wall
GALLERY = dict(x=(96, 103), z=(230, 254), y=(-1264, -1202))     # bottom, into the lobby's east wall
FACES = ['N', 'E', 'S', 'W']
STATION_LEN, STATION_DEPTH = 22, 14
STATIONS = [('N', -1100), ('S', -1155), ('N', -1210)]
RUNG_STEP = 8
NORMAL = {'N': [0, 0, 1], 'S': [0, 0, -1], 'W': [1, 0, 0], 'E': [-1, 0, 0]}


def station_box(face, top):
    a = (X1 - X0 + 1 - STATION_LEN) // 2
    L, D = STATION_LEN, STATION_DEPTH
    if face == 'N':
        return (X0 + a, top - 1, Z0, X0 + a + L - 1, top, Z0 + D - 1)
    if face == 'S':
        return (X0 + a, top - 1, Z1 - D + 1, X0 + a + L - 1, top, Z1)
    if face == 'W':
        return (X0, top - 1, Z0 + a, X0 + D - 1, top, Z0 + a + L - 1)
    return (X1 - D + 1, top - 1, Z0 + a, X1, top, Z0 + a + L - 1)


def ledge_box(face, top, gap=3):
    """Each ledge sits at the end of its face next to the following face of the spiral (N, E, S, W), gap blocks off
    the corner, so an EVA standing on it, centred on it against the wall, stays clear of the next ledges above."""
    L, D = LEDGE_LEN, LEDGE_DEPTH
    if face == 'N':
        return (X1 - gap - L + 1, top - 1, Z0, X1 - gap, top, Z0 + D - 1)
    if face == 'E':
        return (X1 - D + 1, top - 1, Z1 - gap - L + 1, X1, top, Z1 - gap)
    if face == 'S':
        return (X0 + gap, top - 1, Z1 - D + 1, X0 + gap + L - 1, top, Z1)
    return (X0, top - 1, Z0 + gap, X0 + D - 1, top, Z0 + gap + L - 1)


def eva_box(face, b):
    """EVA standing on ledge b against its wall, centred on the ledge along the wall."""
    x0, y0, z0, x1, y1, z1 = b
    cx, cz = (x0 + x1 + 1) / 2, (z0 + z1 + 1) / 2
    h = EVA_W / 2
    if face == 'N':
        return (cx - h, Z0, cx + h, Z0 + EVA_W)
    if face == 'S':
        return (cx - h, Z1 + 1 - EVA_W, cx + h, Z1 + 1)
    if face == 'E':
        return (X1 + 1 - EVA_W, cz - h, X1 + 1, cz + h)
    return (X0, cz - h, X0 + EVA_W, cz + h)


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def main(survey, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    stations = [dict(kind='station', face=f, top_y=t, box=station_box(f, t)) for f, t in STATIONS]

    def blocks(st, other):
        """Does platform `other` sit inside the 61 blocks over an EVA standing on station `st`?"""
        if other is st or not (st['top_y'] < other['top_y'] - 1 <= st['top_y'] + EVA_H + 1):
            return False
        x0, y0, z0, x1, y1, z1 = other['box']
        return overlaps(eva_box(st['face'], st['box']), (x0, z0, x1 + 1, z1 + 1))

    ledges = []
    top = LIP - 14
    i = 0
    while top > FLOOR + 8:
        face = FACES[i % 4]
        L = dict(kind='hand_ledge', face=face, top_y=top, box=ledge_box(face, top))
        if all(abs(top - b) > 4 for b in BULKHEADS) and all(abs(top - s['top_y']) > 6 for s in stations)                 and not any(blocks(s, L) for s in stations):
            ledges.append(L)
        top -= LEDGE_STEP
        i += 1
    faults = [(s['top_y'], o['top_y']) for s in stations for o in stations + ledges if blocks(s, o)]
    rungs = list(range(LIP - 4, FLOOR + 8, -RUNG_STEP))
    clear = (X1 - X0 + 1) - STATION_DEPTH          # rungs are grooves in the wall, so nothing else narrows it
    plan = dict(schema='projectseele.r66.central-dogma-shaft.v0-proposal',
                note='proposal only; nothing written to any world',
                eva_box=dict(width=EVA_W, height=EVA_H),
                shaft=dict(interior=[X0, FLOOR + 1, Z0, X1, LIP, Z1], lip_y=LIP, floor_y=FLOOR, depth=LIP - FLOOR,
                           wall_lining='2 blocks nerv_shaft_panel, light strips every 8 blocks'),
                hall_doorway=dict(DOOR_HALL, guard='inside the launch route reservation (space cell x64..95 z224..255): needs an approved writer exception'),
                bottom_gallery=GALLERY,
                entry=dict(edge='W', note='the EVA comes in from the hall through the doorway and the aisle (x 96..103) and steps east off the west lip; the other three sides of the entry bay are wall'),
                bottom_gallery_floor='same height as the shaft floor, no threshold',
                bulkheads=[dict(id=f'bulkhead_{k}', y=[y, y + 1], cells=[X0, y, Z0, X1, y + 1, Z1], closed_state='projectseele:nerv_launch_armor',
                                open_state='minecraft:air', breakable=True, debris_box=[X0, y - 1, Z0, X1, y + 2, Z1]) for k, y in enumerate(BULKHEADS)],
                stations=stations, station_rule=dict(length=STATION_LEN, depth=STATION_DEPTH, clear_over=EVA_H + 2),
                ledges=ledges, ledge_rule=dict(length=LEDGE_LEN, depth=LEDGE_DEPTH, step=LEDGE_STEP),
                clear_middle_min=clear,
                rungs_y=rungs, rung_rule='a continuous 1-block groove cut into the wall lining on all four faces (a hand grips its lower edge); grooves keep the shaft 32 wide, beams would leave only 17 beside a station',
                climbable_faces=[dict(face=f, normal=NORMAL[f], y=[FLOOR + 1, LIP]) for f in FACES],
                clearance_faults=faults)
    (out / 'shaft_r66.json').write_text(json.dumps(plan, indent=1), 'utf8')
    print('stations', len(stations), 'ledges', len(ledges), 'rungs', len(rungs), 'faults', len(faults), 'clear middle', clear)

    data = np.load(survey); cls, origin = data['classes'], data['origin']
    ox, oy, oz = (int(v) for v in origin)
    COL = {0: (245, 245, 245), 1: (70, 70, 74), 2: (60, 110, 200), 3: (90, 210, 230), 4: (240, 140, 40), 5: (0, 0, 0)}
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 15)
    S = 3
    ny = cls.shape[0]
    for name, fixed, axis in (('plan-ew-z242', 242, 'ew'), ('plan-ns-x119', 119, 'ns')):
        sl = cls[:, fixed - oz, :] if axis == 'ew' else cls[:, :, fixed - ox]
        h0 = ox if axis == 'ew' else oz
        rgb = np.zeros(sl.shape + (3,), np.uint8)
        for v, c in COL.items():
            rgb[sl == v] = c
        im = Image.fromarray(rgb[::-1]).resize((sl.shape[1] * S, ny * S), Image.NEAREST)
        d = ImageDraw.Draw(im)
        Y = lambda y: (oy + ny - 1 - y) * S
        H = lambda h: (h - h0) * S
        for c in range(h0, h0 + sl.shape[1]):
            if c % 32 == 0:
                d.line([(H(c), 0), (H(c), im.height)], fill=(120, 120, 0)); d.text((H(c) + 2, 2), str(c), font=font, fill=(255, 255, 0))
        for y in range(oy, oy + ny):
            if y % 32 == 0:
                d.line([(0, Y(y)), (im.width, Y(y))], fill=(120, 120, 0)); d.text((2, Y(y) + 2), f'y{y}', font=font, fill=(255, 255, 0))
        a0, a1 = (X0, X1) if axis == 'ew' else (Z0, Z1)
        d.rectangle([(H(a0), Y(LIP)), (H(a1 + 1), Y(FLOOR + 1))], fill=(255, 235, 235), outline=(220, 0, 0), width=3)
        for k, y in enumerate(BULKHEADS):
            d.rectangle([(H(a0), Y(y + 1)), (H(a1 + 1), Y(y - 1))], fill=(200, 40, 40))
            d.text((H(a1 + 1) + 4, Y(y + 1) - 4), f'隔墙{k + 1} y{y}', font=font, fill=(255, 90, 90))
        for k in rungs:
            d.line([(H(a0), Y(k)), (H(a1 + 1), Y(k))], fill=(150, 150, 150), width=1)
        for L in stations + ledges:
            x0, y0, z0, x1, y1, z1 = L['box']
            b0, b1 = (x0, x1) if axis == 'ew' else (z0, z1)
            c0, c1 = (z0, z1) if axis == 'ew' else (x0, x1)
            if c0 <= fixed <= c1 or True:
                col = (230, 120, 0) if L['kind'] == 'station' else (255, 170, 0)
                d.rectangle([(H(b0), Y(y1)), (H(b1 + 1), Y(y0 - 1))], fill=col if c0 <= fixed <= c1 else (255, 220, 150))
        if axis == 'ew':
            g = GALLERY; d.rectangle([(H(g['x'][0]), Y(g['y'][1])), (H(g['x'][1] + 1), Y(g['y'][0] - 1))], outline=(0, 160, 0), width=3)
            h = DOOR_HALL; d.rectangle([(H(h['x'][0]), Y(h['y'][1])), (H(h['x'][1] + 1), Y(h['y'][0] - 1))], outline=(0, 160, 0), width=3)
        eva_y = FLOOR + 1
        e0 = (a0 + a1) / 2 - EVA_W / 2
        d.rectangle([(H(e0), Y(eva_y + EVA_H)), (H(e0 + EVA_W), Y(eva_y))], outline=(160, 0, 200), width=2)
        d.text((H(e0) + 2, Y(eva_y + EVA_H) + 2), 'EVA 碰撞箱 17×60', font=font, fill=(160, 0, 200))
        label = f'东西剖面 z={fixed}（左西右东）：粉=竖井，红=装甲隔墙，橙=平台（浅橙为不在此剖面的平台），绿框=机库门洞/井底廊道' if axis == 'ew' \
            else f'南北剖面 x={fixed}（左北右南）'
        d.text((8, im.height - 24), label, font=font, fill=(255, 80, 80))
        im.save(out / f'{name}.png')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
