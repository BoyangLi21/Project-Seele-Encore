"""Invalidate derived DH rows for an installed, measured patch only."""
import argparse
import json
import msvcrt
import sqlite3
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('world', type=Path)
    ap.add_argument('plan', type=Path)
    args = ap.parse_args()
    receipts = list(args.plan.glob('applied_*/receipt.json'))
    if not receipts or not json.loads(receipts[-1].read_text('utf8'))['verified']:
        raise ValueError('Patch readback is not complete')
    db = args.world/'dimensions/projectseele/geofront/data/DistantHorizons.sqlite'
    chunks = json.loads((args.plan/'chunks.json').read_text('utf8'))
    tiles = {(x//4, z//4) for x,z in chunks}
    # A base tile contains sixteen chunks. All must be imported after removing
    # it; retaining their hashes makes DH skip otherwise unchanged siblings.
    hashes = {(tx*4+dx, tz*4+dz) for tx,tz in tiles for dx in range(4) for dz in range(4)}
    with (args.world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        with sqlite3.connect(db) as c:
            old = c.total_changes
            c.executemany('delete from FullData where DetailLevel=0 and PosX=? and PosZ=?', sorted(tiles))
            removed = c.total_changes-old
            c.executemany('delete from ChunkHash where ChunkPosX=? and ChunkPosZ=?', sorted(hashes))
    # Keep parents: deleting a whole parent loses its unaffected quadrants,
    # because only modified children propagate again during native import.
    print(f'Invalidated {removed} base LOD tiles and their chunk hashes for {len(chunks)} edited chunks; parents preserved')


if __name__ == '__main__':
    main()
