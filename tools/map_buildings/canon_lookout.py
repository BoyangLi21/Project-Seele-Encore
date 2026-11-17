"""The Kintoki lookout over Tokyo-3 (episode 2's hill), original design: an elevated timber deck above the canopy on the
south slope of Mt Kintoki, a stepped footpath from the nearest road, and the tree tops trimmed in a wedge toward the city.

  python canon_lookout.py <out dir>
"""
import json, math, sys
from collections import Counter
from pathlib import Path
from mca import REGION, World
from float_fix import guards

M = lambda n: 'minecraft:' + n
AIR = 'minecraft:air'
SOFT = ('leaves', '_log', 'short_grass', 'tall_grass', 'fern', 'flower', 'bush', 'sapling', 'vine', 'moss_carpet')
ROAD_END = (-32, -273)
WAYPOINTS = [(-32, -273), (-18, -290), (-40, -298), (-26, -306), (-60, -312)]   # ends just south of the deck's stair
DECK = (-58, -321, -50, -315)                 # x0, z0, x1, z1
CITY = (30, 220)
FENCE = M('spruce_fence[east=false,north=false,south=false,waterlogged=false,west=false]')


def plan(out):
    w = World(REGION)
    gs = guards()
    c, signs, rep = {}, [], {}

    def ground(x, z):
        for y in range(230, 60, -1):
            s = w.get(x, y, z) or ''
            if s and not s.endswith(':air') and not any(k in s for k in SOFT):
                return y
        return 60

    def clear_trees(x0, z0, x1, z1, ymin, ymax):
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                for y in range(ymin, ymax + 1):
                    s = w.get(x, y, z) or ''
                    if 'leaves' in s or '_log' in s:
                        c.setdefault((x, y, z), AIR)

    # the footpath: cells along the waypoints, rising at most one block per step
    cells = []
    for (ax, az), (bx, bz) in zip(WAYPOINTS, WAYPOINTS[1:]):
        n = max(abs(bx - ax), abs(bz - az))
        for i in range(n):
            cells.append((round(ax + (bx - ax) * i / n), round(az + (bz - az) * i / n)))
    cells.append(WAYPOINTS[-1])
    h = ground(*cells[0])
    prev = cells[0]
    for x, z in cells:
        g = ground(x, z)
        nh = min(g, h + 1) if g >= h else max(g, h - 1)
        dx, dz = x - prev[0], z - prev[1]
        facing = 'east' if dx > 0 else 'west' if dx < 0 else 'south' if dz > 0 else 'north'
        for ox in (0, 1):                                       # two cells wide
            px = x + ox
            gg = ground(px, z)
            for y in range(min(gg, nh), nh):                    # support under a raised step
                c[px, y, z] = M('stone_bricks')
            if nh > h:
                c[px, nh, z] = M(f'stone_brick_stairs[facing={facing},half=bottom,shape=straight,waterlogged=false]')
            else:
                c[px, nh, z] = M('gravel') if (x + z) % 3 else M('coarse_dirt')
            for y in range(nh + 1, max(gg, nh) + 4):             # head room, cutting the slope where needed
                c[px, y, z] = AIR
            clear_trees(px - 1, z - 1, px + 1, z + 1, nh + 1, nh + 12)
        h, prev = nh, (x, z)
    rep['path cells'] = len(cells)
    rep['path top'] = h
    # the deck: posts from the ground, platform 12 above the slope's high corner, fence, benches, telescope, lanterns
    x0, z0, x1, z1 = DECK
    gmax = max(ground(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
    steps = (z1 + 2) - z0 + 1                                   # the stair climbs north along the deck's west side
    D = h + steps                                               # deck floor = top of the stair
    if D < gmax + 3:
        raise SystemExit(f'deck {D} would sit too close to the ground {gmax}: move the path end')
    clear_trees(x0 - 2, z0 - 2, x1 + 2, z1 + 2, min(h, gmax) - 2, D + 14)
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            c[x, D, z] = M('spruce_planks')
            for y in range(D + 1, D + 4):
                c.setdefault((x, y, z), AIR)
    for x, z in ((x0, z0), (x1, z0), (x0, z1), (x1, z1), ((x0 + x1) // 2, z0), ((x0 + x1) // 2, z1)):
        for y in range(ground(x, z) + 1, D):
            c[x, y, z] = M('stripped_spruce_log[axis=y]')
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if x in (x0, x1) or z in (z0, z1):
                c[x, D + 1, z] = FENCE
    # stair from the end of the path (just south of the deck) up its west side to the north-west corner
    sx = x0 - 1
    for i in range(steps):
        z = z1 + 2 - i
        y = h + 1 + i
        c[sx, y, z] = M('spruce_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
        for yy in range(ground(sx, z) + 1, y):
            c[sx, yy, z] = M('stripped_spruce_log[axis=y]') if i % 3 == 0 else c.get((sx, yy, z), AIR)
        for yy in range(y + 1, y + 4):
            c[sx, yy, z] = AIR
    c[x0, D + 1, z0] = AIR                                      # gap in the fence at the top of the stair
    for x in (x0 + 2, x0 + 3, x1 - 3, x1 - 2):                  # two benches facing the city (south)
        c[x, D + 1, z0 + 1] = M('spruce_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
    mx = (x0 + x1) // 2
    c[mx, D + 1, z1 - 1] = M('polished_blackstone_wall[east=none,north=none,south=none,up=true,waterlogged=false,west=none]')
    c[mx, D + 2, z1 - 1] = M('observer[facing=south,powered=false]')    # the coin telescope, its face toward the city
    for x, z in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
        c[x, D + 2, z] = M('lantern[hanging=false,waterlogged=false]')
    c[mx + 2, D + 1, z1 - 1] = M('spruce_planks')
    c[mx + 2, D + 2, z1 - 1] = M('spruce_sign[rotation=0,waterlogged=false]')
    signs.append(dict(pos=[mx + 2, D + 2, z1 - 1], front=['金時山展望台', '第3新東京市', '', ''], color='black'))
    # the sightline: trim leaves and logs at and above deck level in a wedge toward the city
    ax, az = (x0 + x1) / 2, z1
    ux, uz = CITY[0] - ax, CITY[1] - az
    L = math.hypot(ux, uz); ux, uz = ux / L, uz / L
    trimmed = 0
    for d in range(2, 110):
        half = 4 + d * 0.35
        for s in range(-int(half), int(half) + 1):
            x, z = round(ax + ux * d - uz * s), round(az + uz * d + ux * s)
            for y in range(D - 1, D + 16):
                st = w.get(x, y, z) or ''
                if ('leaves' in st or '_log' in st) and (x, y, z) not in c:
                    c[x, y, z] = AIR; trimmed += 1
    rep['deck floor y'] = D
    rep['ground under deck max'] = gmax
    rep['tree cells trimmed in the sightline'] = trimmed
    rows, refused = [], Counter()
    for (x, y, z), want in c.items():
        cur = w.get(x, y, z)
        if cur is None or cur == want:
            continue
        natural = cur.endswith(':air') or any(k in cur for k in SOFT) or cur.split('[')[0].split(':')[-1] in (
            'grass_block', 'dirt', 'coarse_dirt', 'stone', 'gravel', 'podzol', 'rooted_dirt', 'moss_block', 'andesite', 'granite', 'diorite', 'tuff')
        if not natural:
            refused['occupied'] += 1; continue
        try:
            for g in gs:
                g.assert_positions([(x, y, z)])
        except ValueError:
            refused['protected'] += 1; continue
        rows.append([x, y, z, cur, want])
    for st in set(r[4] for r in rows):
        if '[' in st:
            props = st[st.index('[') + 1:-1].split(',')
            assert props == sorted(props), st
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    (Path(out) / 'signs.json').write_text(json.dumps(signs, ensure_ascii=False, indent=1), 'utf8')
    rep.update(rows=len(rows), refused=dict(refused))
    (Path(out) / 'report.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), 'utf8')
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == '__main__':
    plan(sys.argv[1])
