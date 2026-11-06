"""Undo only the glazing erroneously included in the October 16 wall finish.

The original exact delta is the authority for each coordinate and prior state.
Run against a closed world; command-room walls and other finishes are retained.
"""
import argparse
import gzip
import json
from pathlib import Path
from query_blocks import read_box
import regional_voxels as vox


def restore(world, journal, output):
    rows = json.loads(gzip.decompress(journal.read_bytes()))
    rows = [r for r in rows
            if r['reason'] == 'reported_complete_corridor_wall_finish'
            and r['before'] == 'projectseele:clear_glass']
    if not rows:
        raise ValueError('No original glazing in the supplied edit journal')
    lo = tuple(min(r['pos'][i] for r in rows) for i in range(3))
    hi = tuple(max(r['pos'][i] for r in rows) for i in range(3))
    actual = read_box(world, 'projectseele:geofront', lo, hi)
    pending = []
    for row in rows:
        state = actual[tuple(row['pos'])]
        if state == row['before']:
            continue
        if state != row['after']:
            raise ValueError(f"Subsequent edit at {row['pos']}: {state}")
        pending.append(row)
    vox.WORLD = world
    vox.DIM = 'projectseele:geofront'
    vox.OUT = output
    painter = vox.Painter(vertical_bounds=(-1440, 320))
    for row in pending:
        p = row['pos']
        painter.exact((*p, *p), row['after'], row['before'],
                      'restore_original_corridor_glazing')
    if pending:
        painter.apply('restore_original_corridor_glazing')
    actual = read_box(world, vox.DIM, lo, hi)
    assert all(actual[tuple(r['pos'])] == r['before'] for r in rows)
    print(json.dumps(dict(restored=len(pending), verified=len(rows))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    restore(args.world, args.journal, args.output)
