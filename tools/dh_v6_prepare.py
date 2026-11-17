# Make DH rebuild stale level-0 sections even from far away (V6 "b" recipe, map-edges 2026-11-15, approved
# for the R64 bake's prepare step; copied unchanged from map-edges-work/v1/v6_prepare.py).
# Deletes the stale L0 rows, their L1-L3 ancestors, and flags the surviving L0 children of those ancestors
# ApplyToParent=1 so DH re-propagates them upward. Only ever run it on a database COPY under the bake folder.
# R64: run after `rebake_r63.py prepare` with the prepare step's WORK/lod/rebuild_sections.json as the list.
# usage: dh_v6_prepare.py <DistantHorizons.sqlite COPY> <stale.json> [--dry-run]
import sqlite3, json, sys
db, stale_path = sys.argv[1], sys.argv[2]
dry = '--dry-run' in sys.argv
stale = {tuple(s) for s in json.load(open(stale_path))}
anc = {(lv, x >> lv, z >> lv) for x, z in stale for lv in (1, 2, 3)}
uri = 'file:' + db + ('?mode=ro&immutable=1' if dry else '')
c = sqlite3.connect(uri, uri=True)
l0 = [(x, z) for x, z in c.execute('select PosX, PosZ from FullData where DetailLevel=0')]
kids = [(x, z) for x, z in l0 if (x, z) not in stale and (3, x >> 3, z >> 3) in anc]
have_anc = sum(1 for lv, x, z in anc if c.execute(
    'select 1 from FullData where DetailLevel=? and PosX=? and PosZ=?', (lv, x, z)).fetchone())
print('stale L0', len(stale), 'present', sum(1 for s in l0 if s in stale))
print('ancestor keys', len(anc), 'present', have_anc)
print('L0 children to flag', len(kids))
if not dry:
    c.executemany('delete from FullData where DetailLevel=0 and PosX=? and PosZ=?', list(stale))
    c.executemany('delete from FullData where DetailLevel=? and PosX=? and PosZ=?', list(anc))
    c.executemany('update FullData set ApplyToParent=1 where DetailLevel=0 and PosX=? and PosZ=?', kids)
    c.commit()
    print('done')
