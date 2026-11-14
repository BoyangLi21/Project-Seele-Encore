"""Read-only: count rows of write lists whose before state no longer matches a world (for example after other
lists went into the formal world). Opens region files for reading only.

    stale_rows_check.py WORLD ROWS.json [ROWS.json ...]
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from write_deep_cells import REGION, decode, read_chunk


def check(world, rows):
    grouped = defaultdict(lambda: defaultdict(list))
    for r in rows:
        grouped[r[0] >> 9, r[2] >> 9][r[0] >> 4, r[2] >> 4].append(r)
    bad, kinds, missing = [], Counter(), 0
    for (rx, rz), chunks in sorted(grouped.items()):
        path = Path(world) / REGION / f'r.{rx}.{rz}.mca'
        if not path.exists():
            missing += sum(len(c) for c in chunks.values())
            continue
        buf = path.read_bytes()
        for (cx, cz), cells in chunks.items():
            try:
                root = read_chunk(buf, cx, cz)[3]
            except ValueError:
                missing += len(cells)
                continue
            decoded = {int(s['Y']): decode(s['block_states']) for s in root['sections'] if 'block_states' in s}
            for x, y, z, before, *_ in cells:
                if y >> 4 in decoded:
                    ids, palette = decoded[y >> 4]
                    state = palette[ids[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)]]
                else:
                    state = 'minecraft:air'
                if state != before:
                    bad.append([x, y, z, before, state])
                    kinds[before.split('[')[0] + ' -> ' + state.split('[')[0]] += 1
    return bad, kinds, missing


def main():
    world = sys.argv[1]
    for f in sys.argv[2:]:
        rows = json.load(open(f))
        bad, kinds, missing = check(world, rows)
        print(json.dumps(dict(list=f, rows=len(rows), stale=len(bad), missing=missing, kinds=kinds.most_common(8), sample=bad[:5])))


if __name__ == '__main__':
    main()
