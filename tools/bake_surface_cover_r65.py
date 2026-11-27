"""Bake the private GeoFront streaming fallback from the shipped DH 2.3.4 database (requires lz4)."""
import argparse
import gzip
import lzma
import sqlite3
import struct
from pathlib import Path

import lz4.frame
import numpy as np


def unpack(blob, mode):
    # DH flushes its final LZ4 block before copying the stream, without the four-byte end mark.
    if mode == 1:
        return lz4.frame.LZ4FrameDecompressor().decompress(blob + bytes(4))
    if mode == 3:
        return lzma.LZMADecompressor().decompress(blob)
    if mode == 0:
        return blob
    raise ValueError(f"Unsupported DH compression {mode}")


def material_ids(blob, names):
    size, = struct.unpack_from('>I', blob)
    at = 4
    ids = []
    for _ in range(size):
        length, = struct.unpack_from('>H', blob, at)
        name = blob[at + 2:at + 2 + length].decode().split('_DH-BSW_')[1].split('_STATE_')[0]
        at += 2 + length
        if name in ('AIR', 'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air',
                    'minecraft:light', 'minecraft:barrier', 'minecraft:structure_void',
                    'projectseele:collector_structure'):
            ids.append(0)
        else:
            ids.append(names.setdefault(name, len(names) + 1))
    return ids


def bake(db_path, output):
    detail = 3
    step = 1 << detail
    names = {}
    with sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        x0, z0, x1, z1 = db.execute('SELECT min(PosX), min(PosZ), max(PosX), max(PosZ) '
                                    'FROM FullData WHERE DetailLevel=?', (detail,)).fetchone()
        width, height = (x1 + 1 - x0) * 64, (z1 + 1 - z0) * 64
        if not (0 < width <= 8192 and 0 < height <= 8192):
            raise ValueError(f'Unexpected survey bounds {width} x {height}')
        pixels = bytearray(width * height * 4)
        used = 0
        for x, z, raw_data, raw_map, mode in db.execute(
                'SELECT PosX,PosZ,Data,Mapping,CompressionMode FROM FullData WHERE DetailLevel=?', (detail,)):
            if not raw_data or not raw_map:
                continue
            data = unpack(raw_data, mode)
            ids = material_ids(unpack(raw_map, mode), names)
            at = 0
            for column in range(4096):
                count, = struct.unpack_from('>H', data, at)
                at += 2
                for cursor in range(at, at + count * 8, 8):
                    span, = struct.unpack_from('>Q', data, cursor)
                    mat = ids[span & 0x7fffffff]
                    if mat:
                        top = (span >> 44 & 4095) + (span >> 32 & 4095)
                        # The stored top is relative to GeoFront's -1344 build floor.
                        index = ((z - z0) * 64 + column % 64) * width + (x - x0) * 64 + column // 64
                        struct.pack_into('>HH', pixels, index * 4, top, mat)
                        used += 1
                        break
                at += count * 8
            if at != len(data):
                raise ValueError(f'Trailing data at {x},{z}')
        # A legacy db can contain a non-empty parent row with entire quadrants never
        # propagated. Recover those samples from the current finest survey, including
        # newly explored land. Never enlarge the surveyed area using a guessed height.
        grid = np.frombuffer(pixels, '>u2').reshape(height, width, 2)
        missing_tiles = {(ix, iz) for ix, iz in zip(*np.where(
            ~(grid[:, :, 0] != 0).reshape(height // 8, 8, width // 8, 8).all(axis=(1, 3)).T))}
        recovered = 0
        for lx, lz in db.execute('SELECT PosX,PosZ FROM FullData WHERE DetailLevel=0'):
            tx, tz = lx - x0 * 8, lz - z0 * 8
            if (tx, tz) not in missing_tiles:
                continue
            raw_data, raw_map, mode = db.execute('SELECT Data,Mapping,CompressionMode FROM FullData '
                                                 'WHERE DetailLevel=0 AND PosX=? AND PosZ=?', (lx, lz)).fetchone()
            if not raw_data or not raw_map:
                continue
            data = unpack(raw_data, mode)
            ids = material_ids(unpack(raw_map, mode), names)
            at = 0
            for column in range(4096):
                count, = struct.unpack_from('>H', data, at)
                at += 2
                sx, sz = divmod(column, 64)
                if sx % 8 == 4 and sz % 8 == 4:
                    index = ((tz * 8 + sz // 8) * width + tx * 8 + sx // 8) * 4
                    if not (pixels[index] or pixels[index + 1]):
                        for cursor in range(at, at + count * 8, 8):
                            span, = struct.unpack_from('>Q', data, cursor)
                            mat = ids[span & 0x7fffffff]
                            if mat:
                                top = (span >> 44 & 4095) + (span >> 32 & 4095)
                                struct.pack_into('>HH', pixels, index, top, mat)
                                recovered += 1
                                break
                at += count * 8
    with gzip.open(output, 'wb', compresslevel=5) as out:
        out.write(struct.pack('>4siiiiiiH', b'SFS1', x0 * 64 * step, z0 * 64 * step,
                              width, height, step, -1344, len(names)))
        for name in names:
            raw = name.encode('ascii')
            out.write(struct.pack('>H', len(raw)) + raw)
        out.write(pixels)
    print(f'{used + recovered:,} surveyed surface samples ({recovered:,} recovered from L0), '
          f'{len(names)} materials, {width} x {height}, {output.stat().st_size:,} bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    bake(args.database, args.output)
