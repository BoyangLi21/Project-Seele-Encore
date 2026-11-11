"""Read MTR station names and centres from the world copy (tiny msgpack reader)."""
import glob, json, struct, sys


def unpack(b, i=0):
    t = b[i]
    if t <= 0x7f: return t, i + 1
    if 0x80 <= t <= 0x8f: return _map(b, i + 1, t & 15)
    if 0x90 <= t <= 0x9f: return _arr(b, i + 1, t & 15)
    if 0xa0 <= t <= 0xbf: n = t & 31; return b[i + 1:i + 1 + n].decode('utf8', 'replace'), i + 1 + n
    if t >= 0xe0: return t - 256, i + 1
    if t == 0xc0: return None, i + 1
    if t == 0xc2: return False, i + 1
    if t == 0xc3: return True, i + 1
    fmt = {0xca: ('>f', 4), 0xcb: ('>d', 8), 0xcc: ('>B', 1), 0xcd: ('>H', 2), 0xce: ('>I', 4), 0xcf: ('>Q', 8),
           0xd0: ('>b', 1), 0xd1: ('>h', 2), 0xd2: ('>i', 4), 0xd3: ('>q', 8)}
    if t in fmt:
        f, n = fmt[t]; return struct.unpack(f, b[i + 1:i + 1 + n])[0], i + 1 + n
    if t in (0xd9, 0xda, 0xdb):
        k = {0xd9: 1, 0xda: 2, 0xdb: 4}[t]; n = int.from_bytes(b[i + 1:i + 1 + k], 'big'); s = i + 1 + k
        return b[s:s + n].decode('utf8', 'replace'), s + n
    if t in (0xc4, 0xc5, 0xc6):
        k = {0xc4: 1, 0xc5: 2, 0xc6: 4}[t]; n = int.from_bytes(b[i + 1:i + 1 + k], 'big'); s = i + 1 + k
        return b[s:s + n], s + n
    if t in (0xdc, 0xdd):
        k = 2 if t == 0xdc else 4; return _arr(b, i + 1 + k, int.from_bytes(b[i + 1:i + 1 + k], 'big'))
    if t in (0xde, 0xdf):
        k = 2 if t == 0xde else 4; return _map(b, i + 1 + k, int.from_bytes(b[i + 1:i + 1 + k], 'big'))
    raise ValueError(hex(t))


def _map(b, i, n):
    d = {}
    for _ in range(n):
        k, i = unpack(b, i); v, i = unpack(b, i); d[k] = v
    return d, i


def _arr(b, i, n):
    a = []
    for _ in range(n):
        v, i = unpack(b, i); a.append(v)
    return a, i


if __name__ == '__main__':
    out = []
    for f in glob.glob(sys.argv[1] + '/stations/*/*'):
        d = unpack(open(f, 'rb').read())[0]
        p1, p2 = d['position1'], d['position2']
        out.append(dict(name=d['name'].split('|')[0], x=(p1['x'] + p2['x']) / 2, z=(p1['z'] + p2['z']) / 2, y=(p1['y'] + p2['y']) / 2))
    json.dump(out, open(sys.argv[2], 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    print(len(out), out[:3])
