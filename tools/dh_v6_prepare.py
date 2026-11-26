# Rebuild selected L0 sections and their L1-L3 ancestors on a staging copy of the DH database.
# Flag surviving direct children at each affected level so each rebuilt parent includes all its quadrants.
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
    # A rebuilt ancestor needs all four immediate child quadrants. Unchanged L1/L2
    # rows do not change when their L0 descendants are replayed, so DH would
    # otherwise leave their quadrants empty with no outstanding propagation flag.
    for level, x, z in anc:
        if level >= 2:
            c.execute('update FullData set ApplyToParent=1 where DetailLevel=? and PosX between ? and ? and PosZ between ? and ?',
                      (level - 1, x * 2, x * 2 + 1, z * 2, z * 2 + 1))
    c.commit()
    print('done')
