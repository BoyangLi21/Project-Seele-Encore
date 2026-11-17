"""Dump MTR 4 records (msgpack files under <world>/mtr/<ns>/<dim>/<kind>/xx/ID) to one JSON file, read-only.
No msgpack package needed: the small decoder below covers the types MTR writes.
usage: mtr_dump_records.py <world-mtr-dimension-dir> <out.json>"""
import json
import os
import struct
import sys


def unpack(b, i=0):
    t = b[i]
    if t <= 0x7f:
        return t, i + 1
    if 0x80 <= t <= 0x8f:
        return mapn(b, i + 1, t & 0x0f)
    if 0x90 <= t <= 0x9f:
        return arrn(b, i + 1, t & 0x0f)
    if 0xa0 <= t <= 0xbf:
        n = t & 0x1f
        return b[i + 1:i + 1 + n].decode('utf8', 'replace'), i + 1 + n
    if t >= 0xe0:
        return t - 256, i + 1
    if t == 0xc0:
        return None, i + 1
    if t == 0xc2:
        return False, i + 1
    if t == 0xc3:
        return True, i + 1
    if t in (0xc4, 0xc5, 0xc6):
        w = {0xc4: 1, 0xc5: 2, 0xc6: 4}[t]
        n = int.from_bytes(b[i + 1:i + 1 + w], 'big')
        return b[i + 1 + w:i + 1 + w + n].hex(), i + 1 + w + n
    if t == 0xca:
        return struct.unpack('>f', b[i + 1:i + 5])[0], i + 5
    if t == 0xcb:
        return struct.unpack('>d', b[i + 1:i + 9])[0], i + 9
    if t in (0xcc, 0xcd, 0xce, 0xcf):
        w = {0xcc: 1, 0xcd: 2, 0xce: 4, 0xcf: 8}[t]
        return int.from_bytes(b[i + 1:i + 1 + w], 'big'), i + 1 + w
    if t in (0xd0, 0xd1, 0xd2, 0xd3):
        w = {0xd0: 1, 0xd1: 2, 0xd2: 4, 0xd3: 8}[t]
        return int.from_bytes(b[i + 1:i + 1 + w], 'big', signed=True), i + 1 + w
    if t in (0xd9, 0xda, 0xdb):
        w = {0xd9: 1, 0xda: 2, 0xdb: 4}[t]
        n = int.from_bytes(b[i + 1:i + 1 + w], 'big')
        return b[i + 1 + w:i + 1 + w + n].decode('utf8', 'replace'), i + 1 + w + n
    if t in (0xdc, 0xdd):
        w = 2 if t == 0xdc else 4
        return arrn(b, i + 1 + w, int.from_bytes(b[i + 1:i + 1 + w], 'big'))
    if t in (0xde, 0xdf):
        w = 2 if t == 0xde else 4
        return mapn(b, i + 1 + w, int.from_bytes(b[i + 1:i + 1 + w], 'big'))
    raise ValueError(f'type {t:#x} at {i}')


def arrn(b, i, n):
    out = []
    for _ in range(n):
        v, i = unpack(b, i)
        out.append(v)
    return out, i


def mapn(b, i, n):
    out = {}
    for _ in range(n):
        k, i = unpack(b, i)
        v, i = unpack(b, i)
        out[str(k)] = v
    return out, i


if __name__ == '__main__':
    root = sys.argv[1]
    data = {}
    for kind in sorted(os.listdir(root)):
        recs = []
        for dp, dn, fn in os.walk(os.path.join(root, kind)):
            for f in fn:
                b = open(os.path.join(dp, f), 'rb').read()
                try:
                    v, _ = unpack(b)
                except Exception as e:
                    v = {'_error': str(e), '_file': f}
                recs.append(v)
        data[kind] = recs
    json.dump(data, open(sys.argv[2], 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print({k: len(v) for k, v in data.items()})
