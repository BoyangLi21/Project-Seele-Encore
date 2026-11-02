"""Cold map-edit guard from the installed launch authority, without hashes.

Use the SPACE cells actually referenced by the eighteen launch/recovery routes,
not the much larger permission domains for air traffic. These are finite XYZ
volumes; they must never become a two-dimensional terrain hold mask.
"""
from collections import defaultdict
from pathlib import Path
import gzip
import json
import re
import numpy as np

CELL = re.compile(r'space/c(-?\d+)_(-?\d+)_(-?\d+)\Z')
AUTHORITY = ('ROOT_RUNTIME_DIRECTORY.json', 'ROOT_MECHANICAL_OWNER.json',
             'UPRIGHT_GUIDEWAY_SOURCE.json', 'ROOT_ASSEMBLY_BUNDLE.json',
             'ROOT_AIR_TRANSPORT.json', 'launch_hatch_layers_r54.json')


def read_json(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)


class LaunchProtection:
    def __init__(self, boxes, report=None):
        self.boxes = boxes
        self.report = report or {}
        self.by_chunk = defaultdict(list)
        for identity, bounds in boxes:
            x, y, z, X, Y, Z = bounds
            if y > Y or x > X or z > Z:
                raise ValueError(('Invalid protected volume', identity, bounds))
            for cx in range(x // 16, X // 16 + 1):
                for cz in range(z // 16, Z // 16 + 1):
                    self.by_chunk[cx, cz].append((identity, bounds))

    def assert_positions(self, positions):
        groups = defaultdict(list)
        for x, y, z in positions:
            groups[int(x) // 16, int(z) // 16].append((x, y, z))
        for key, points in groups.items():
            p = np.asarray(points)
            for identity, b in self.by_chunk.get(key, ()):
                hit = np.all((p >= b[:3]) & (p <= b[3:]), axis=1)
                if hit.any():
                    raise ValueError(('EVA launch protection', identity, p[hit][0].tolist()))

    def chunk_mask(self, cx, cz, y0=-128, height=448):
        mask = np.zeros((height, 16, 16), bool)
        for _, (x, y, z, X, Y, Z) in self.by_chunk.get((cx, cz), ()):
            l, r = max(0, y-y0), min(height, Y-y0+1)
            if l < r:
                mask[l:r, max(0, z-cz*16):min(16, Z-cz*16+1),
                     max(0, x-cx*16):min(16, X-cx*16+1)] = True
        return mask

    def assert_delta(self, path, y0=-128, height=448):
        checked = 0
        with np.load(path) as d:
            coordinates,ranges,indices,before,after=(d[k]for k in('coordinates','ranges','indices','before','after'))
            for i, (cx, cz) in enumerate(coordinates):
                a, b = ranges[i:i + 2]
                at = indices[a:b].astype(np.int64)
                if np.any((at < 0) | (at >= height * 256)):
                    raise ValueError('Map delta exceeds its declared vertical extent')
                # An unchanged entry does not grant permission to change later.
                at = at[before[a:b] != after[a:b]]
                key=int(cx),int(cz)
                if key in self.by_chunk:
                    # Large natural-terrain batches contain millions of cells
                    # far from any launch volume. Use the same exact finite
                    # mask for this chunk before constructing point records.
                    protected=self.chunk_mask(*key,y0=y0,height=height).reshape(-1)[at]
                    if protected.any():
                        offset=int(at[np.flatnonzero(protected)[0]])
                        self.assert_positions([(key[0]*16+offset%16,y0+offset//256,
                                                key[1]*16+(offset//16)%16)])
                checked += len(at)
        return checked


def load(world):
    world = Path(world)
    directory = read_json(world / AUTHORITY[0])
    owner = read_json(world / AUTHORITY[1])
    if directory.get('status') != 'installed' or owner.get('status') != 'installed':
        raise ValueError('Installed launch authority is required for map work')
    routes = directory['routes']
    if len(routes) != 18 or len(directory['ports']) != 9:
        raise ValueError('Unexpected launch topology; review the changed authority')
    legs = {r['id']: r for r in directory['legs']}
    used = {name for route in routes for name in route['legs']}
    cells = {name for identity in used for name in legs[identity]['occupancy']}
    boxes = []
    for name in sorted(cells):
        match = CELL.fullmatch(name)
        if not match:
            raise ValueError(('Unrecognized launch occupancy', name))
        x, y, z = (int(v) * 32 for v in match.groups())
        boxes.append((name, [x, y, z, x+31, y+31, z+31]))

    points = set()
    def gather(value):
        if isinstance(value, dict):
            p = value.get('position')
            if p is not None and ('state' in value or 'closed' in value):
                points.add(tuple(int(v) for v in p))
            for key, item in value.items():
                if key == 'cells_file':
                    relative = Path(item)
                    if relative.is_absolute() or '..' in relative.parts:
                        raise ValueError('Unsafe mechanical cell-table path')
                    gather(read_json(world / relative))
                elif key not in ('mechanism_sources', 'ground_guides'):
                    gather(item)
        elif isinstance(value, list):
            for item in value:
                gather(item)
    # Native support blocks, every door collision layer, and receiver seats.
    gather(owner)
    gather(read_json(world / 'launch_hatch_layers_r54.json'))
    for binding in directory['runtime']['bindings']:
        gather(binding.get('cells', []))
    guideway = read_json(world / 'UPRIGHT_GUIDEWAY_SOURCE.json')
    for anchor in guideway['anchors']:
        points.add(tuple(int(v) for v in anchor['at']))
    del guideway
    for p in sorted(points):
        boxes.append(('mechanical-cell', [*p, *p]))
    # The separately retained underground airshaft is not a launch route leg.
    # Its actual two gates specify the complete intervening opening volume.
    gates = [g for g in owner['gates'] if g['resource'].startswith('remote_airshaft_')]
    if gates:
        bounds = []
        for g in gates:
            x, y, z = g['frame']['position']; h = g['silo_hatch']
            bounds.append([int(np.floor(x-h['opening_x']/2-2)), int(np.floor(y-3)),
                           int(np.floor(z-h['opening_z']/2-2)),
                           int(np.ceil(x+h['opening_x']/2+2)), int(np.ceil(y+3)),
                           int(np.ceil(z+h['opening_z']/2+2))])
        a = np.asarray(bounds)
        boxes.append(('retained-airshaft', [*a[:, :3].min(0).tolist(), *a[:, 3:].max(0).tolist()]))
    return LaunchProtection(boxes, dict(source='installed ROOT route and mechanical authority',
        routes=len(routes), ports=len(directory['ports']), legs=len(used),
        finite_occupied_cells=len(cells), native_mechanical_cells=len(points),
        column_freeze=False, runtime_scan=False))


def check_candidate(guard, candidate):
    count = sum(guard.assert_delta(p) for p in (candidate/'delta').glob('*.npz'))
    import nbtlib
    path = candidate/'block-entities.dat'
    if path.exists():
        for change in nbtlib.load(path)['Changes']:
            for key in ('Before', 'After'):
                if key in change:
                    guard.assert_positions([tuple(int(change[key][k]) for k in ('x', 'y', 'z'))])
    # Map-only publication must not carry a copy of mechanical authority or
    # runtime state. Launch data is neither migrated nor reset by terrain work.
    forbidden = {'eva', 'nerv', 'launch', 'entry_plug', 'sortie', 'mechanical'}
    for path in (candidate/'after').rglob('*'):
        if not path.is_file():
            continue
        name = path.name.lower()
        if path.name in AUTHORITY or any(token in name for token in forbidden):
            raise ValueError(('Map candidate attempts to replace launch state', str(path)))
    return dict(**guard.report, checked_changed_cells=count, protected_edits=0)
