"""After an in-game test on a copy with the R65 write-back batches: does every planned cell still hold its new state?

  BUILDINGS_WORLD=<tested copy> python r65_writeback_check.py <r65-writeback dir>

Prints, per batch, how many cells hold the planned state, the original state, or something else (with examples), and
whether each replaced recipe file still has the planned content.
"""
import hashlib, json, sys
from collections import Counter
from pathlib import Path
from mca import REGION, World, WORLD


def main(plans):
    w = World(REGION)
    for batch in ('doors', 'shaft', 'local'):
        d = Path(plans) / batch
        rows = json.loads((d / 'rows.json').read_text('utf8'))
        c, other = Counter(), Counter()
        for r in rows:
            cur = w.get(*r[:3])
            k = 'planned' if cur == r[4] else 'original' if cur == r[3] else 'other'
            c[k] += 1
            if k == 'other':
                other[(r[4].split('[')[0], (cur or 'None').split('[')[0])] += 1
        files = json.loads((d / 'patch.json').read_text('utf8'))['files']
        changed = [f['file'] for f in files if hashlib.md5((Path(WORLD) / f['file']).read_bytes()).hexdigest() != f['after_md5']]
        print(batch, dict(c), 'others', other.most_common(6), 'recipes rewritten by the game', len(changed), changed[:3])


if __name__ == '__main__':
    main(sys.argv[1])
