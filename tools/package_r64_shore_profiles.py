"""Write final shoreline ground and water surveys for the runtime chunk generator."""
import argparse
import gzip
import io
from pathlib import Path
import struct

import numpy as np


def pack(source, landscape, destination):
    destination.mkdir(parents=True, exist_ok=True)
    written = set()
    for path in sorted(source.glob('r.*.*.npz')):
        _, rx, rz, _ = path.name.split('.')
        region = f'{rx}_{rz}.bin.gz'
        if not (landscape / region).is_file():
            raise ValueError(f'No registered terrain region for {path.name}')
        with np.load(path, allow_pickle=False) as data:
            x, z, ground, water = (data[k].astype(np.int64) for k in ('x', 'z', 'ground', 'water'))
        if not (x.shape == z.shape == ground.shape == water.shape and x.ndim == 1 and x.size):
            raise ValueError(f'Incomplete survey in {path}')
        if np.any(x >> 9 != int(rx)) or np.any(z >> 9 != int(rz)):
            raise ValueError(f'Foreign coordinates in {path}')
        if np.any((water != -32768) & (water <= ground)) or np.any(ground < -32767) or np.any(np.maximum(ground, water) > 32767):
            raise ValueError(f'Invalid final profile in {path}')
        chunk = ((z >> 4) & 31) * 32 + ((x >> 4) & 31)
        local = (z & 15) * 16 + (x & 15)
        order = np.argsort(chunk * 256 + local)
        keys = (chunk * 256 + local)[order]
        if np.any(np.diff(keys) == 0):
            raise ValueError(f'Duplicate columns in {path}')
        output = io.BytesIO()
        chunks, counts = np.unique(chunk[order], return_counts=True)
        output.write(struct.pack('>4sH', b'SHR1', len(chunks)))
        start = 0
        for index, count in zip(chunks, counts):
            output.write(struct.pack('>HH', index, count))
            for at in order[start:start + count]:
                output.write(struct.pack('>Bhh', local[at], ground[at], water[at]))
            start += count
        packed = gzip.compress(output.getvalue(), compresslevel=6, mtime=0)
        target = destination / region
        temporary = target.with_suffix('.part')
        temporary.write_bytes(packed)
        temporary.replace(target)
        written.add(target.name)
    if not written or written != {p.name for p in destination.glob('*.bin.gz')}:
        raise ValueError('Survey and installed region sets differ')
    print(f'{len(written)} surveyed shoreline regions')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'landscape', 'destination'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    pack(args.source, args.landscape, args.destination)
