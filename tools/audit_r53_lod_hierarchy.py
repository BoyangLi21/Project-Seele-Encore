"""Check that existing DH child columns remain represented in parent tiles."""
import argparse
import json
import lzma
import sqlite3
import struct
from pathlib import Path

import numpy as np


def audit(sql, center=None, radius=None):
    pending = sql.execute('select count(*) from FullData where ApplyToParent=1').fetchone()[0]
    if pending:
        raise ValueError(f'DH still has {pending} pending parent updates')
    columns = {}
    for detail, x, z, data, compression in sql.execute(
            'select DetailLevel,PosX,PosZ,Data,CompressionMode from FullData'):
        if compression != 3:
            raise ValueError(f'Unsupported DH compression mode: {compression}')
        raw = lzma.LZMADecompressor().decompress(data)
        occupied = np.zeros(4096, dtype=bool)
        offset = 0
        for i in range(4096):
            count = struct.unpack_from('>H', raw, offset)[0]
            occupied[i] = count != 0
            offset += 2 + count * 8
        if offset != len(raw):
            raise ValueError('Unexpected DH column payload length')
        columns[detail, x, z] = occupied.reshape(64, 64)
    maximum = max(key[0] for key in columns)
    missing = []
    outside = []
    checked = 0
    for (detail, x, z), child in columns.items():
        if detail == maximum:
            continue
        expected = child.reshape(32, 2, 32, 2).any(axis=(1, 3))
        parent = columns.get((detail+1, x//2, z//2))
        actual = (np.zeros((32, 32), dtype=bool) if parent is None else
                  parent[(x%2)*32:(x%2+1)*32, (z%2)*32:(z%2+1)*32])
        covered = np.ones((32, 32), dtype=bool)
        if center is not None and radius is not None:
            ix, iz = np.indices((32, 32))
            width = 2 << detail
            xmin, zmin = (x*64 + ix*2)*(1 << detail), (z*64 + iz*2)*(1 << detail)
            dx = np.maximum(np.maximum(xmin-center[0], center[0]-(xmin+width)), 0)
            dz = np.maximum(np.maximum(zmin-center[1], center[1]-(zmin+width)), 0)
            covered = dx*dx + dz*dz <= radius*radius
        absent = expected & ~actual
        count = int((absent & covered).sum())
        checked += int((expected & covered).sum())
        if count:
            missing.append({'child': [detail, x, z], 'missing_parent_columns': count})
        if np.any(absent & ~covered):
            outside.append({'child': [detail, x, z], 'missing_parent_columns': int((absent & ~covered).sum())})
    return {'tiles': len(columns), 'represented_columns_checked': checked,
            'coverage_center': center, 'coverage_radius': radius,
            'missing': missing, 'outside_coverage_missing': outside, 'verified': not missing}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    with sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro', uri=True) as sql:
        result = audit(sql)
    args.report.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result))
