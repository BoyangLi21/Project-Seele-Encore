"""Minimal read-only access to a copy of the geofront region files."""
import io, math, os, zlib
from pathlib import Path
import nbtlib
import numpy as np

# the world copy to read; set BUILDINGS_WORLD to scan another stopped world
WORLD = os.environ.get('BUILDINGS_WORLD', 'E:/eva-map-buildings/client/saves/MAP_REVIEW')
REGION = WORLD + '/dimensions/projectseele/geofront/region'
AIR = {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'}


def state_name(entry):
    name = str(entry['Name'])
    props = entry.get('Properties')
    if not props:
        return name
    return name + '[' + ','.join(f'{k}={props[k]}' for k in sorted(props)) + ']'


def decode(states):
    palette = [state_name(p) for p in states['palette']]
    data = states.get('data')
    if data is None or len(palette) == 1:
        return np.zeros(4096, np.int32), palette
    bits = max(4, math.ceil(math.log2(len(palette))))
    per = 64 // bits
    words = np.array(data, dtype=np.int64).astype(np.uint64)
    at = np.arange(4096)
    return ((words[at // per] >> ((at % per) * bits).astype(np.uint64)) & np.uint64((1 << bits) - 1)).astype(np.int32), palette


def raw_chunks(path):
    """Yield (cx, cz, raw nbt bytes) for every generated chunk in one region file."""
    buf = Path(path).read_bytes()
    if len(buf) < 8192:
        return
    rx, rz = (int(v) for v in Path(path).name.split('.')[1:3])
    for i in range(1024):
        loc, count = int.from_bytes(buf[4 * i:4 * i + 3], 'big'), buf[4 * i + 3]
        if not loc:
            continue
        length = int.from_bytes(buf[loc * 4096:loc * 4096 + 4], 'big')
        if buf[loc * 4096 + 4] != 2:
            continue
        yield rx * 32 + (i & 31), rz * 32 + (i >> 5), zlib.decompress(buf[loc * 4096 + 5:loc * 4096 + 4 + length])


class World:
    """Block lookups across chunks with a small cache; None for ungenerated chunks."""

    def __init__(self, region_dir):
        self.dir = Path(region_dir)
        self.regions = {}
        self.chunks = {}

    def _region(self, rx, rz):
        key = (rx, rz)
        if key not in self.regions:
            p = self.dir / f'r.{rx}.{rz}.mca'
            self.regions[key] = p.read_bytes() if p.exists() else None
        return self.regions[key]

    def chunk(self, cx, cz):
        key = (cx, cz)
        if key in self.chunks:
            return self.chunks[key]
        if len(self.chunks) > 3000:
            self.chunks.clear()
        buf = self._region(cx >> 5, cz >> 5)
        result = None
        if buf is not None:
            i = 4 * ((cx & 31) + (cz & 31) * 32)
            loc = int.from_bytes(buf[i:i + 3], 'big')
            if loc:
                length = int.from_bytes(buf[loc * 4096:loc * 4096 + 4], 'big')
                root = nbtlib.File.parse(io.BytesIO(zlib.decompress(buf[loc * 4096 + 5:loc * 4096 + 4 + length])))
                result = self.load_root(root)
        self.chunks[key] = result
        return result

    @staticmethod
    def load_root(root):
        secs = {}
        for s in root['sections']:
            if 'block_states' in s:
                secs[int(s['Y'])] = decode(s['block_states'])
        bes = {(int(e['x']), int(e['y']), int(e['z'])): str(e['id']) for e in root.get('block_entities', [])}
        status = str(root.get('Status', ''))
        return secs, bes, status

    def get(self, x, y, z):
        c = self.chunk(x >> 4, z >> 4)
        if c is None:
            return None
        sec = c[0].get(y >> 4)
        if sec is None:
            return 'minecraft:air'
        ids, pal = sec
        return pal[ids[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)]]

    def block_entity(self, x, y, z):
        c = self.chunk(x >> 4, z >> 4)
        return None if c is None else c[1].get((x, y, z))
