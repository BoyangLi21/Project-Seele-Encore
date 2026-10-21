"""Read-only audit of DH parent spans above the actual dimension build limit."""
import argparse
import hashlib
import json
import lzma
import sqlite3
import struct
from pathlib import Path


def project(data, maximum):
    raw = lzma.LZMADecompressor().decompress(data)
    cursor = 0
    digest = hashlib.sha256()
    removed = columns = highest = 0
    outside_ids = set()
    for _ in range(4096):
        count = struct.unpack_from('>H', raw, cursor)[0]
        cursor += 2
        values = struct.unpack_from('>' + str(count) + 'Q', raw, cursor)
        cursor += count * 8
        keep = []
        changed = False
        for value in values:
            bottom, height = (value >> 44) & 4095, (value >> 32) & 4095
            top = bottom + height
            highest = max(highest, top)
            if top > maximum:
                outside_ids.add(value & 0x7fffffff)
                changed = True
                removed += top - max(maximum, bottom)
                height = max(0, maximum - bottom)
                value = (value & ~(4095 << 32)) | (height << 32)
            if height:
                keep.append(value)
        columns += changed
        digest.update(struct.pack('>H', len(keep)))
        digest.update(struct.pack('>' + str(len(keep)) + 'Q', *keep))
    if cursor != len(raw):
        raise ValueError('Unexpected full-column payload length')
    return digest.hexdigest(), columns, removed, highest, outside_ids


def palette(data):
    raw = lzma.LZMADecompressor().decompress(data)
    count = struct.unpack_from('>I', raw)[0]
    cursor, entries = 4, []
    for _ in range(count):
        length = struct.unpack_from('>H', raw, cursor)[0]
        cursor += 2
        entries.append(raw[cursor:cursor + length].decode('utf8'))
        cursor += length
    return entries


def audit(database, min_y, max_y):
    rows = []
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as sql:
        for detail, x, z, minimum, data, mapping, mode in sql.execute(
                'select DetailLevel,PosX,PosZ,MinY,Data,Mapping,CompressionMode '
                'from FullData order by DetailLevel,PosX,PosZ'):
            row = dict(tile=[detail, x, z], data_sha256=hashlib.sha256(data).hexdigest(),
                       mapping_sha256=hashlib.sha256(mapping).hexdigest())
            if detail > 0:
                if mode != 3:
                    raise ValueError(f'Unsupported compression mode {mode}')
                # DH 2.3.4 leaves DTO MinY at zero; spans are relative to the
                # level wrapper's actual minimum, not that unused DTO field.
                digest, columns, removed, highest, outside_ids = project(data, max_y - min_y)
                names = palette(mapping)
                outside_states = sorted({names[i] for i in outside_ids})
                outside_solid = any(not s.endswith('_DH-BSW_AIR') for s in outside_states)
                row.update(valid_projection_sha256=digest, outside_columns=columns,
                           outside_voxels=removed, highest_exclusive=highest + min_y,
                           outside_states=outside_states, outside_solid=outside_solid)
            rows.append(row)
    return dict(database=str(database), min_y=min_y, max_y_exclusive=max_y, rows=rows,
                affected_parents=[r['tile'] for r in rows if r.get('outside_solid', False)],
                base_tiles=sum(r['tile'][0] == 0 for r in rows), written=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('report', type=Path)
    parser.add_argument('--max-y', type=int, required=True)
    parser.add_argument('--min-y', type=int, required=True)
    args = parser.parse_args()
    result = audit(args.database, args.min_y, args.max_y)
    args.report.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(dict(rows=len(result['rows']), base_tiles=result['base_tiles'],
                          affected_parents=len(result['affected_parents']))))
