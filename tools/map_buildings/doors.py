"""Check every building door in a world copy: blocked thresholds (E5) and air gaps beside the door (E6)."""
import sys, json, io
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import nbtlib
sys.path.insert(0, str(Path(__file__).parent))
from mca import raw_chunks, decode, World, AIR
from blocks import DOORS, FACING, base, short, is_open, is_natural, is_door, props


def find_doors(path):
    out = []
    for cx, cz, raw in raw_chunks(path):
        if b'door' not in raw:
            continue
        root = nbtlib.File.parse(io.BytesIO(raw))
        for s in root['sections']:
            if 'block_states' not in s:
                continue
            ids, pal = decode(s['block_states'])
            sy = int(s['Y'])
            for i, n in enumerate(pal):
                if base(n) in DOORS and 'half=lower' in n:
                    for at in (ids == i).nonzero()[0].tolist():
                        out.append((cx * 16 + (at & 15), sy * 16 + (at >> 8), cz * 16 + ((at >> 4) & 15), n))
    return out


def check(args):
    region_dir, doors = args
    w = World(region_dir)
    res = []
    for x, y, z, state in doors:
        p = props(state)
        nx, nz = FACING[p['facing']]
        ax, az = -nz, nx                       # along the wall
        g = lambda dx, dy, dz: w.get(x + dx, y + dy, z + dz)
        rec = dict(pos=[x, y, z], door=short(state), state=state, facing=p['facing'], hinge=p.get('hinge'),
                   upper=g(0, 1, 0), lintel=g(0, 2, 0))
        sides = {}
        for name, k in (('front', 1), ('back', -1)):
            cells = [g(nx * k, dy, nz * k) for dy in (0, 1, 2)]
            sides[name] = dict(cells=cells, below=g(nx * k, -1, nz * k),
                               blocked=not is_open(cells[0]) and not is_open(cells[1]),
                               step=not is_open(cells[0]) and is_open(cells[1]),
                               natural=[is_natural(c) for c in cells])
            if sides[name]['blocked'] or sides[name]['step']:
                d = 99
                for dd in range(1, 25):
                    if is_open(g(nx * k * dd, 0, nz * k * dd)) and is_open(g(nx * k * dd, 1, nz * k * dd)):
                        d = dd
                        break
                sides[name]['depth'] = d
                top = None
                for dy in range(0, 40):
                    if is_open(g(nx * k, dy, nz * k)) and is_open(g(nx * k, dy + 1, nz * k)):
                        top = dy
                        break
                sides[name]['surface_dy'] = top
        rec['sides'] = sides
        gaps = []
        lintel_solid = rec['lintel'] is not None and not is_open(rec['lintel'])
        for s in (1, -1):
            if is_door(g(ax * s, 0, az * s)) or is_door(g(ax * s, 1, az * s)):
                continue
            for dy in (0, 1):
                c = g(ax * s, dy, az * s)
                if c is None or c not in AIR:
                    continue
                through = is_open(g(ax * s + nx, dy, az * s + nz)) and is_open(g(ax * s - nx, dy, az * s - nz))
                outer = g(ax * s * 2, dy, az * s * 2)
                top = g(ax * s, 2, az * s)
                frame = (outer is not None and not is_open(outer)) or (top is not None and not is_open(top))
                if through and frame and lintel_solid:
                    gaps.append(dict(cell=[x + ax * s, y + dy, z + az * s], side=s, dy=dy, outer=outer, top=top,
                                     below=g(ax * s, -1, az * s)))
        above = g(0, 2, 0)
        if above in AIR and not is_open(g(0, 3, 0)) and not is_open(g(ax, 2, az)) and not is_open(g(-ax, 2, -az)) \
                and is_open(g(nx, 2, nz)) and is_open(g(-nx, 2, -nz)):
            gaps.append(dict(cell=[x, y + 2, z], side=0, dy=2, outer=g(ax, 2, az), top=g(0, 3, 0), below=None))
        rec['gaps'] = gaps
        res.append(rec)
    return res


if __name__ == '__main__':
    REGION = Path(sys.argv[1])
    OUT = Path(sys.argv[2])
    files = sorted(REGION.glob('r.*.mca'))
    with ProcessPoolExecutor(28) as ex:
        found = [d for part in ex.map(find_doors, files) for d in part]
    print('doors', len(found))
    by_region = {}
    for d in found:
        by_region.setdefault((d[0] >> 9, d[2] >> 9), []).append(d)
    jobs = [(str(REGION), v) for v in by_region.values()]
    with ProcessPoolExecutor(28) as ex:
        recs = [r for part in ex.map(check, jobs) for r in part]
    OUT.write_text(json.dumps(recs), 'utf8')
    f = lambda r, k: r['sides'][k]['blocked']
    print('checked', len(recs), 'blocked one side', sum(1 for r in recs if f(r, 'front') != f(r, 'back')),
          'both', sum(1 for r in recs if f(r, 'front') and f(r, 'back')),
          'step', sum(1 for r in recs if r['sides']['front']['step'] or r['sides']['back']['step']),
          'gaps', sum(1 for r in recs if r['gaps']))
