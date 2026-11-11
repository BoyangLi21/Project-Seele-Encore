"""MTR rail paths sampled per block (quadratic through the tangent intersection), as a column -> rail y map."""
import glob, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from stations import unpack
from mca import WORLD

ORDER = ['E', 'SEE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'SWW', 'W', 'NWW', 'NW', 'NNW', 'N', 'NNE', 'NE', 'NEE']


def vec(name):
    a = ORDER.index(name) * math.pi / 8          # E = +x, S = +z
    return math.cos(a), math.sin(a)


def path(d):
    p0, p2 = d['position1'], d['position2']
    x0, z0, y0 = p0['x'] + 0.5, p0['z'] + 0.5, p0['y']
    x2, z2, y2 = p2['x'] + 0.5, p2['z'] + 0.5, p2['y']
    u = vec(d['angle1'])
    v = vec(d['angle2'])
    det = u[0] * (-v[1]) - u[1] * (-v[0])
    ctrl = None
    if abs(det) > 1e-6:
        t = ((x2 - x0) * (-v[1]) - (z2 - z0) * (-v[0])) / det
        if t > 0:
            ctrl = (x0 + u[0] * t, z0 + u[1] * t)
    length = math.hypot(x2 - x0, z2 - z0)
    n = max(2, int(length * 1.5))
    for i in range(n + 1):
        s = i / n
        if ctrl:
            x = (1 - s) ** 2 * x0 + 2 * (1 - s) * s * ctrl[0] + s * s * x2
            z = (1 - s) ** 2 * z0 + 2 * (1 - s) * s * ctrl[1] + s * s * z2
        else:
            x, z = x0 + (x2 - x0) * s, z0 + (z2 - z0) * s
        yield x, z, y0 + (y2 - y0) * s


def rail_columns(band=3):
    cols = {}
    for f in glob.glob(WORLD + '/mtr/projectseele/geofront/rails/*/*'):
        d = unpack(open(f, 'rb').read())[0]
        for x, z, y in path(d):
            for dx in range(-band, band + 1):
                for dz in range(-band, band + 1):
                    cols.setdefault((int(math.floor(x)) + dx, int(math.floor(z)) + dz), []).append(y)
    return cols
