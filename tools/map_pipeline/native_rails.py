"""Read the actual MTR rail members from an offline native snapshot.

Cached native-curves.json predates most station batches, so a corridor check
against it can pass only because no rails are listed nearby. Chords are a
screening geometry: QUADRATIC and CABLE rails deviate from them, so anything
inside the screening distance needs the exact curve before it is cleared.
"""
from pathlib import Path

import numpy as np

from prepare_mtr_member_patch_r52 import Parser


def load_rails(snapshot, dimension='projectseele/geofront'):
    rows=[]
    for path in sorted((Path(snapshot)/dimension/'rails').rglob('*')):
        if not path.is_file():continue
        rail=Parser(path.read_bytes()).node().value
        rows.append(dict(a=[rail['position1'][k]for k in 'xyz'],b=[rail['position2'][k]for k in 'xyz'],
            mode=rail['transportMode'],shape=rail['shape'],platform=rail['isPlatform'],siding=rail['isSiding'],file=path.name))
    return rows


def chord_distance(rail,xz):
    """Horizontal distance from every Nx2 point to the rail chord."""
    a=np.asarray(rail['a'],float)[[0,2]];b=np.asarray(rail['b'],float)[[0,2]]
    q=np.asarray(xz,float);d=b-a;length=float(d@d)
    t=np.clip((q-a)@d/length,0,1)if length else np.zeros(len(q))
    return np.linalg.norm(q-(a+t[:,None]*d),axis=1)


def near_points(rails,xz,distance):
    """Rails whose chord passes within distance of any point, nearest first."""
    rows=[]
    for rail in rails:
        d=chord_distance(rail,xz);i=int(np.argmin(d))
        if d[i]<=distance:rows.append(dict(rail,distance=float(d[i]),nearest_point=[float(v)for v in np.asarray(xz)[i]]))
    return sorted(rows,key=lambda r:r['distance'])
