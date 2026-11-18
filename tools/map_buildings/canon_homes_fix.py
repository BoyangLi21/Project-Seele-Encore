"""Corrections to the canon homes already in the world (batches 501-503), as one list for the writer.

  python canon_homes_fix.py <out dir>

The homes are rebuilt in memory with canon_homes at the floor heights found in the world (BUILDINGS_WORLD) and only the
cells that differ are listed: pane and bar connections, the 11-A-2 kitchen and floor clutter, the item labels removed
and the 402 name card shortened. The street light in front of Comfort 17 that lost its pole stands again on the
ground, its arm over the road. Writes rows.json, signs.json (402 only; the writer needs --signs) and report.json.
Removing the three labels replaces sign blocks, so the writer needs --allow-block-entities; no other row touches a
block entity.
"""
import io, json, sys, zlib
from collections import Counter
from pathlib import Path
import nbtlib
from mca import REGION, World
from float_fix import guards
import canon_homes as ch

LAMP = dict(old=[(-29, 135, 766), (-29, 140, 766)], base=(-29, 133, 765), top=138, facing='north')
REI = [(-201, 498, 1), (-201, 513, 2), (-201, 528, 3)]
KIRISATO = [(-2878, -1112), (-2790, -1112), (-2702, -1112), (-2878, -1016), (-2790, -1016), (-2702, -1016)]


def danchi_floor(w, x0, z0):
    for y in range(240, 40, -1):
        if w.get(x0 + 3, y, z0 + 3) == 'minecraft:smooth_stone' and w.get(x0 + 3, y + 3, z0 + 3) == 'minecraft:light_gray_concrete':
            return y
    raise SystemExit(f'no danchi floor at {x0},{z0}')


def sign_texts(x, y, z):
    """Front lines of the sign block entity in the world, or None."""
    cx, cz = x >> 4, z >> 4
    buf = (Path(REGION) / f'r.{cx >> 5}.{cz >> 5}.mca').read_bytes()
    i = 4 * ((cx & 31) + (cz & 31) * 32)
    loc = int.from_bytes(buf[i:i + 3], 'big')
    n = int.from_bytes(buf[loc * 4096:loc * 4096 + 4], 'big')
    root = nbtlib.File.parse(io.BytesIO(zlib.decompress(buf[loc * 4096 + 5:loc * 4096 + 4 + n])))
    for e in root.get('block_entities', []):
        if (int(e['x']), int(e['y']), int(e['z'])) == (x, y, z) and 'sign' in str(e['id']):
            return [json.loads(str(m)).get('text', '') for m in e['front_text']['messages']]
    return None


def main(out):
    w = World(REGION)
    parts = {}
    b = ch.Build()
    ch.comfort17(b, -66, 132, 768)
    b.finish()
    parts['comfort17'] = b
    for x0, z0, n in REI:
        b = ch.Build()
        ch.danchi(b, x0, danchi_floor(w, x0, z0), z0, n, rei=(n == 2), seed=n)
        b.finish()
        parts[f'rei{n}'] = b
    n = 1
    for ox, oz in KIRISATO:
        for dx in (2, 42):
            b = ch.Build()
            ch.danchi(b, ox + dx, danchi_floor(w, ox + dx, oz + 6), oz + 6, n, seed=100 + n)
            b.finish()
            parts[f'kirisato{n}'] = b
            n += 1
    lamp = ch.Build()
    for p in LAMP['old']:
        lamp.put(*p, ch.AIR)
    bx, by, bz = LAMP['base']
    lamp.put(bx, by, bz, ch.M('polished_deepslate'))
    for y in range(by + 1, LAMP['top']):
        lamp.put(bx, y, bz, ch.BARS)
    lamp.put(bx, LAMP['top'], bz, f"projectseele:street_light_head[facing={LAMP['facing']}]")
    parts['lamp'] = lamp

    everything = ch.Build()
    for b in parts.values():
        everything.c.update(b.c)
    ch.connect_panes(everything, w)

    gs = guards()
    rows, report, kinds = [], {}, Counter()
    where = {p: name for name, b in parts.items() for p in b.c}
    for (x, y, z), want in everything.c.items():
        cur = w.get(x, y, z)
        if cur is None:
            raise SystemExit(f'{x},{y},{z} not generated')
        if cur == want:
            continue
        for g in gs:
            g.assert_positions([(x, y, z)])
        if w.block_entity(x, y, z) and not cur.split('[')[0].endswith('sign'):
            raise SystemExit(f'{x},{y},{z} {cur} carries a block entity')
        rows.append([x, y, z, cur, want])
        part = where[x, y, z]
        report.setdefault(part, Counter())[(cur.split('[')[0] + ' -> ' + want.split('[')[0]).replace('minecraft:', '')] += 1
    signs = []
    for b in parts.values():
        for sg in b.signs:
            have = sign_texts(*sg['pos'])
            if have is not None and have != (sg['front'] + [''] * 4)[:4]:
                signs.append(sg)
    removed = [r[:3] for r in rows if r[3].split('[')[0].endswith('sign')]
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    (Path(out) / 'signs.json').write_text(json.dumps(signs, ensure_ascii=False, indent=1), 'utf8')
    summary = dict(rows=len(rows), signs=len(signs), labels_removed=removed,
                   parts={k: dict(v.most_common()) for k, v in report.items()})
    (Path(out) / 'report.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
