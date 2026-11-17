"""Rows that bring a review copy from an old version of a list to a new one.

copy_sync.py <old rows.json> <new rows.json> <out dir>

On the copy (BUILDINGS_WORLD) the old list is already written. Every cell of either list should
end as the new list says, or back at its original block (the old list's 'before') when only the
old list touched it. The rows hold what the copy has now as their 'before', so the deep writer's
check passes on the copy. For review copies only; formal lists are always planned fresh.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World


def main(old, new, out):
    w = World(REGION)
    O = {tuple(r[:3]): r for r in json.load(open(old))}
    N = {tuple(r[:3]): r for r in json.load(open(new))}
    rows = []
    for c in set(O) | set(N):
        want = N[c][4] if c in N else O[c][3]
        cur = w.get(*c)
        if cur != want and not w.block_entity(*c):
            rows.append([*c, cur, want])
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    print('sync rows', len(rows))


if __name__ == '__main__':
    main(*sys.argv[1:])
