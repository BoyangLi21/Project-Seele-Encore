"""Audit DH 2.3.4 columns and queue native merges into a stopped staging DB. Requires numpy and lz4."""
import argparse
import collections
import json
import sqlite3
import struct
from pathlib import Path

import numpy as np

from bake_surface_cover_r65 import unpack


def payload_mask(blob, encoding):
    data = unpack(blob, encoding)
    at = 0
    result = bytearray(4096)
    for column in range(4096):
        count, = struct.unpack_from('>H', data, at)
        result[column] = count != 0
        at += 2 + count * 8
    if at != len(data):
        raise ValueError('DH column lengths do not match payload size')
    return np.frombuffer(result, dtype=np.uint8).reshape(64, 64) != 0


def audit(path, queue, verify_payload=False):
    mode = 'rw' if queue else 'ro'
    full = np.ones((64, 64), dtype=bool)
    empty = np.zeros_like(full)
    missing = collections.Counter()
    empty_payloads = collections.Counter()
    dirty_children = []
    with sqlite3.connect(path.resolve().as_uri() + '?mode=' + mode, uri=True, timeout=4) as db:
        db.execute('BEGIN IMMEDIATE' if queue else 'BEGIN')
        max_level, = db.execute('SELECT max(DetailLevel) FROM FullData').fetchone()
        children = {}
        for level in range(max_level + 1):
            parents = {}
            payload = 'Data' if verify_payload else 'NULL'
            for x, z, compressed, encoding, data in db.execute(
                    f'SELECT PosX, PosZ, ColumnGenerationStep, CompressionMode, {payload} FROM FullData WHERE DetailLevel=?', (level,)):
                if not compressed:
                    continue
                raw = unpack(compressed, encoding)
                mask = np.frombuffer(raw, np.uint8).reshape(64, 64) != 0
                if verify_payload:
                    occupied = payload_mask(data, encoding) if data else empty
                    inconsistent = int(np.count_nonzero(mask & ~occupied))
                    if inconsistent:
                        empty_payloads[level] += inconsistent
                    mask &= occupied
                parents[x, z] = full if mask.all() else mask if mask.any() else empty
            for (x, z), child in children.items():
                if child is empty:
                    continue
                # A parent sample is due when all four children carry generated data.
                parent = parents.get((x // 2, z // 2), empty)
                if parent is full:
                    continue
                available = child.reshape(32, 2, 32, 2).all(axis=(1, 3))
                ox, oz = (x % 2) * 32, (z % 2) * 32
                holes = int(np.count_nonzero(available & ~parent[ox:ox + 32, oz:oz + 32]))
                if holes:
                    missing[level] += holes
                    dirty_children.append((level - 1, x, z))
            children = parents
        if queue:
            db.executemany('UPDATE FullData SET ApplyToParent=1 WHERE DetailLevel=? AND PosX=? AND PosZ=?', dirty_children)
            db.commit()
        pending, = db.execute('SELECT count(*) FROM FullData WHERE ApplyToParent OR ApplyToChildren').fetchone()
    return dict(missing_parent_columns=dict(missing), generated_columns_without_spans=dict(empty_payloads),
                inspected_span_payloads=verify_payload, child_rows_to_propagate=len(dirty_children),
                queued=queue, pending=pending)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('--queue', action='store_true', help='mark only the affected child rows for native DH propagation')
    parser.add_argument('--verify-payload', action='store_true', help='also decode the span count of every child and parent column')
    args = parser.parse_args()
    print(json.dumps(audit(args.database, args.queue, args.verify_payload)))
