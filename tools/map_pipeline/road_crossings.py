"""Where a road may cross railway track on the level: the real level crossings.

GSI road and rail centrelines that meet with both at ground level (vt_lvorder 0, the rail
not on a bridge or in a tunnel) are level crossings. Each is snapped to the installed
track it belongs to; a link crosses track only there, so the map keeps the real crossing
places instead of whichever gap in the track is shortest.
"""
import gzip
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import shape
from shapely.strtree import STRtree

from map_pipeline.native_rails import load_rails

# Trackbed a crossing deck replaces under existing rails: ballast is soil already, the
# half-block ballast step is not.
TRACKBED = {'minecraft:gravel', 'minecraft:andesite_slab'}
OPEN = {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'}


def track_samples(snapshot):
    """Installed train track as metre samples: x, z at block centres and rail height."""
    rows = []
    for rail in load_rails(snapshot):
        if rail['mode'] == 'TRAIN':
            a, b = np.array(rail['a'], float), np.array(rail['b'], float)
            rows.append(a + np.linspace(0, 1, max(2, int(np.linalg.norm(b - a)) + 1))[:, None] * (b - a))
    points = np.vstack(rows)
    return np.c_[points[:, 0] + .5, points[:, 2] + .5, points[:, 1]]


def real_level_crossings(features, snapshot, snap=12.0):
    """Level crossings as rows of x, z, rail height on the installed track they belong to."""
    roads, rails = [], []
    for path in features:
        with gzip.open(path, 'rt', encoding='utf8') as stream:
            for row in json.load(stream)['features']:
                p = row['properties']
                if p.get('source_layer') == 'RdCL' and p.get('vt_lvorder', 0) == 0:
                    roads.append(shape(row['geometry']))
                elif (p.get('source_layer') == 'RailCL' and p.get('vt_lvorder', 0) == 0
                      and not any(k in p.get('vt_railstate', '') for k in ('橋', 'トンネル', '地下'))):
                    rails.append(shape(row['geometry']))
    tree = STRtree(roads)
    points = []
    for rail in rails:
        for i in tree.query(rail, predicate='intersects'):
            meet = rail.intersection(roads[i])
            points += [(q.x, q.y) for q in getattr(meet, 'geoms', [meet]) if q.geom_type == 'Point']
    if not points:
        return np.zeros((0, 3))
    track = track_samples(snapshot)
    distance, nearest = cKDTree(track[:, :2]).query(np.array(points))
    found = track[nearest[distance <= snap]]
    # Overlapping tiles repeat a crossing; keep one per two metres.
    keep = []
    for row in found[np.lexsort((found[:, 1], found[:, 0]))]:
        if not keep or np.hypot(*(row[:2] - keep[-1][:2])) > 2:
            keep.append(row)
    return np.array(keep)


def lower_tops_under_decks(capture, snapshot):
    """Set the measured ground of track on an open viaduct to the real ground below it.

    A capture's top is the highest soil block, and ballast is soil, so a column under a raised
    line measures as if the ground were at the deck: the road planner then reads the open space
    beneath as solid and, worse, would dig the ballast as a cutting.
    """
    top, full = capture.measured['top'], capture.measured['full']
    bx, bz, bX, bZ = capture.bounds
    seen, lowered = set(), 0
    for x_, z_, rail_y in track_samples(snapshot):
        for dx in range(-3, 4):
            for dz in range(-3, 4):
                x, z = int(np.floor(x_)) + dx, int(np.floor(z_)) + dz
                if (x, z) in seen or not (bx <= x <= bX and bz <= z <= bZ):
                    continue
                seen.add((x, z))
                t = int(top[z - bz, x - bx])
                if not full[z - bz, x - bx] or abs(t - rail_y) > 4:
                    continue
                y = t - 1
                while y > t - 6 and capture.state(x, y, z).split('[')[0] not in OPEN:
                    y -= 1
                if not all(capture.state(x, y - k, z).split('[')[0] in OPEN for k in range(3)):
                    continue
                while y > -127 and capture.state(x, y, z).split('[')[0] in OPEN:
                    y -= 1
                top[z - bz, x - bx] = y
                lowered += 1
    return lowered
