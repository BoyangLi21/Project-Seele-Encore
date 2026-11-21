"""Read the saved GeoFront rectangle from Anvil region headers and top-level chunk NBT."""
from collections import Counter
from pathlib import Path
import hashlib
import struct
import time
import zlib


def chunk_bounds(block_bounds):
    return tuple(int(v) >> 4 for v in block_bounds.split(','))


def _string(data, pos):
    size = struct.unpack_from('>H', data, pos)[0]
    end = pos + 2 + size
    if end > len(data):
        raise ValueError('Truncated NBT string')
    return data[pos + 2:end], end


def _skip(data, pos, tag):
    if 1 <= tag <= 6:
        return pos + (1, 2, 4, 8, 4, 8)[tag - 1]
    if tag == 8:
        return _string(data, pos)[1]
    if tag in (7, 11, 12):
        size = struct.unpack_from('>i', data, pos)[0]
        if size < 0:
            raise ValueError('Negative NBT array length')
        return pos + 4 + size * {7: 1, 11: 4, 12: 8}[tag]
    if tag == 9:
        item, n = struct.unpack_from('>Bi', data, pos)
        pos += 5
        for _ in range(n):
            pos = _skip(data, pos, item)
        return pos
    if tag == 10:
        while data[pos]:
            child = data[pos]
            _, pos = _string(data, pos + 1)
            pos = _skip(data, pos, child)
        return pos + 1
    raise ValueError('Unsupported NBT tag %d' % tag)


def _status(payload, codec):
    if codec not in (1, 2, 3):
        raise ValueError('Unsupported Anvil chunk compression %d' % codec)
    wbits = 31 if codec == 1 else 15
    # Vanilla 1.20.1 normally writes the root Status first, ahead of the large section list.
    prefix = payload[:128] if codec == 3 else zlib.decompressobj(wbits).decompress(payload, 128)
    if (prefix.startswith(b'\x0a\x00\x00\x08\x00\x06Status') and len(prefix) >= 14
            and 14 + struct.unpack_from('>H', prefix, 12)[0] <= len(prefix)):
        return _string(prefix, 12)[0].decode('ascii')
    data = payload if codec == 3 else zlib.decompress(payload, wbits)
    if data[0] != 10:
        raise ValueError('Chunk NBT root is not a compound')
    _, pos = _string(data, 1)
    while data[pos]:
        tag = data[pos]
        key, pos = _string(data, pos + 1)
        if tag == 8 and key == b'Status':
            return _string(data, pos)[0].decode('ascii')
        pos = _skip(data, pos, tag)
    raise ValueError('No root Status in a saved chunk')


def scan(region_dir, bounds):
    """One nonoverlapping row-major slot per requested coordinate. Missing, proto and FULL are distinct."""
    started = time.monotonic()
    x0, z0, x1, z1 = bounds
    width, height = x1 - x0 + 1, z1 - z0 + 1
    if width <= 0 or height <= 0:
        raise ValueError("Empty Anvil rectangle")
    mask = bytearray(width * height)
    counts = Counter()
    region_dir = Path(region_dir)
    for rz in range(z0 >> 5, (z1 >> 5) + 1):
        for rx in range(x0 >> 5, (x1 >> 5) + 1):
            path = region_dir / ('r.%d.%d.mca' % (rx, rz))
            if not path.is_file():
                continue
            data = path.read_bytes()
            if not data:  # Minecraft creates zero-byte placeholders for some visited empty regions.
                continue
            if len(data) < 8192:
                raise ValueError('Truncated region header: ' + str(path))
            offsets = set()
            for cz in range(max(z0, rz * 32), min(z1, rz * 32 + 31) + 1):
                for cx in range(max(x0, rx * 32), min(x1, rx * 32 + 31) + 1):
                    slot = (cz & 31) * 32 + (cx & 31)
                    loc = struct.unpack_from('>I', data, slot * 4)[0]
                    if not loc:
                        continue
                    offset = (loc >> 8) * 4096
                    sectors = loc & 255
                    if not sectors or offset < 8192 or offset + 5 > len(data) or offset in offsets:
                        raise ValueError('Invalid or duplicate Anvil offset: %s (%d,%d)' % (path, cx, cz))
                    offsets.add(offset)
                    length, codec = struct.unpack_from('>IB', data, offset)
                    if length < 1 or offset + 4 + length > len(data) or (sectors < 255 and length + 4 > sectors * 4096):
                        raise ValueError('Invalid Anvil length: %s (%d,%d)' % (path, cx, cz))
                    if codec & 128:
                        payload = (region_dir / ('c.%d.%d.mcc' % (cx, cz))).read_bytes()
                    else:
                        payload = data[offset + 5:offset + 4 + length]
                    status = _status(payload, codec & 127)
                    counts[status] += 1
                    if status == 'minecraft:full':
                        mask[(cz - z0) * width + cx - x0] = 1
    counts['not_saved'] = len(mask) - sum(counts.values())
    return mask, dict(chunk_bounds=list(bounds), width=width, height=height, coordinates=len(mask), full=mask.count(1),
                      status_counts=dict(sorted(counts.items())), mask_sha256=hashlib.sha256(mask).hexdigest(),
                      seconds=round(time.monotonic() - started, 2))


def incomplete_strips(mask, bounds, max_chunks):
    """Adjacent complete rows can be skipped. The returned inclusive rectangles never overlap."""
    x0, z0, x1, z1 = bounds
    width = x1 - x0 + 1
    if width <= 0 or z1 < z0 or len(mask) != width * (z1 - z0 + 1) or max_chunks < 1:
        raise ValueError("Invalid strip bounds, mask or chunk limit")
    rows_per_run = max(1, max_chunks // width)
    first = None
    for row in range(z1 - z0 + 2):
        pending = row <= z1 - z0 and 0 in mask[row * width:(row + 1) * width]
        if first is not None and (not pending or row - first >= rows_per_run):
            yield (x0, z0 + first, x1, z0 + row - 1)
            first = None
        if pending and first is None:
            first = row
