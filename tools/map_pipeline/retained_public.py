"""Keep adjacent retained streets at their measured vertical layer."""
import numpy as np
from hakone_earthworks import road_blocks


def reserved_column(walk, grade2, road, j, i, y):
    if not (0 <= j < walk.shape[0] and 0 <= i < walk.shape[1]) or not walk[j, i]:
        return False
    floor = int(road_blocks(grade2[j, i])[0])
    return floor - 2 <= y <= floor + (4 if road[j, i] else 3)


def load_guard(candidate):
    path = candidate / 'plan/retained-public.npz'
    if not path.exists():
        return lambda pos: False
    with np.load(path) as f:
        d = {k: f[k] for k in f.files}
    x, z, _, _ = map(int, d['bounds'])
    return lambda p: reserved_column(d['walk'], d['grade2'], d['road'], p[2]-z, p[0]-x, p[1])


def verify(candidate, editor):
    path = candidate / 'plan/retained-public.npz'
    if not path.exists():
        return dict(columns=0, cells=0, errors=[])
    with np.load(path) as f:
        d = {k: f[k] for k in f.files}
    x, z, _, _ = map(int, d['bounds'])
    errors = []; count = 0
    for j, i in np.argwhere(d['walk']):
        floor = int(road_blocks(d['grade2'][j, i])[0])
        for y in range(floor-2, floor+(5 if d['road'][j, i] else 4)):
            p = (int(i+x), y, int(j+z)); count += 1
            if editor.state(*p) != editor.state(*p, original=True):
                errors.append(['retained public layer changed', *p])
    return dict(columns=int(d['walk'].sum()), cells=count, errors=errors)
