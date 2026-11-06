"""Whole-floor passenger review of every retained station from measured voxels.

Walkable nodes come from real collision boxes, not from declared routes. Each
registered platform must reach a declared public street through nodes a player
body fits in. Doors and gates count as passable and are listed; lifts are not
walked, so a platform that needs one reports its nearest floors instead of a
failure hidden as success. Routes are written for replay in the running game.
"""
import argparse
from collections import Counter, deque
import json
import math
from pathlib import Path

import numpy as np

from audit_hakone_station_walks import Walker
from author_station_layout import collision
from map_pipeline.native_rails import chord_distance, load_rails
from prepare_mtr_member_patch_r52 import Parser

DOORS = ('_door[', '_gate[', 'apg_door', 'psd_door', 'turnstile', 'fare_')
STEP = .6
JUMP = 1.1


def platforms(snapshot, dimension='projectseele/geofront'):
    rows = []
    for path in sorted((Path(snapshot) / dimension / 'platforms').rglob('*')):
        if path.is_file():
            rows.append(Parser(path.read_bytes()).node().value)
    return rows


class Floors:
    """Standing heights per column inside one site box."""

    def __init__(self, walker, bounds, rails=()):
        self.w = walker
        self.bounds = bounds
        self.rails = rails
        self.step = STEP
        self.cache = {}
        self.doors = Counter()

    def boxes(self, x, y, z):
        """States newer than the collision export fall back to their plain block shape."""
        state, boxes = self.w.boxes(x, y, z)
        if boxes is None and state is not None and '_stairs[' not in state:
            boxes = collision(state)
        return state, boxes

    def passable_door(self, state):
        return state is not None and any(mark in state for mark in DOORS)

    def blocked(self, x, y, z):
        """Body test at a cell centre; doors do not block a passenger."""
        lo, hi = (x + .2, y + .0001, z + .2), (x + .8, y + 1.7999, z + .8)
        for Y in range(math.floor(lo[1]), math.floor(hi[1]) + 1):
            state, boxes = self.boxes(x, Y, z)
            if boxes is None:
                return True
            if self.passable_door(state):
                self.doors[state.split('[')[0]] += 1
                continue
            for b in boxes:
                if lo[1] < Y + b[4] and hi[1] > Y + b[1] and lo[0] < x + b[3] and hi[0] > x + b[0] \
                        and lo[2] < z + b[5] and hi[2] > z + b[2]:
                    return True
        return False

    def column(self, x, z):
        key = x, z
        if key in self.cache:
            return self.cache[key]
        a, b, c, A, B, C = self.bounds
        heights = []
        if a <= x <= A and c <= z <= C:
            for y in range(b, B):
                state, boxes = self.boxes(x, y, z)
                if not boxes or self.passable_door(state):
                    continue
                for top in sorted({y + q[4] for q in boxes}):
                    if not self.blocked(x, top, z) and top not in heights and not self.trackbed(x, top, z):
                        heights.append(top)
        self.cache[key] = heights
        return heights

    def trackbed(self, x, z, h):
        """Running track is not a passenger route out of a station."""
        point = np.array([[x + .5, z + .5]])
        return any(float(chord_distance(rail, point)[0]) < 2.2 and -2 <= h - rail['a'][1] <= 2.5 for rail in self.rails)

    def neighbours(self, x, z, h):
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            X, Z = x + dx, z + dz
            for H in self.column(X, Z):
                if abs(H - h) <= self.step + 1e-6:
                    yield X, Z, H


def boarding_nodes(floors, platform):
    p, q = [np.array([platform[k][a] for a in 'xyz'], float) for k in ('position1', 'position2')]
    length = max(1, int(np.linalg.norm((q - p)[[0, 2]])))
    u = (q - p)[[0, 2]] / length if length else np.zeros(2)
    normal = np.array([-u[1], u[0]])
    nodes = set()
    for s in np.linspace(0, length, length + 1):
        at = p[[0, 2]] + u * s + .5
        for side in (-1, 1):
            for offset in np.arange(1.5, 5.1, .5):
                x, z = map(math.floor, at + normal * side * offset)
                nodes.update((x, z, h) for h in floors.column(x, z) if p[1] - 2 <= h <= p[1] + 1.5)
    return nodes


def search(floors, starts, goal):
    parent = {n: None for n in starts}
    queue = deque(starts)
    while queue:
        node = queue.popleft()
        if goal(node):
            path = []
            while node is not None:
                path.append(node)
                node = parent[node]
            return path[::-1], len(parent)
        for n in floors.neighbours(*node):
            if n not in parent:
                parent[n] = node
                queue.append(n)
    return None, len(parent)


def clear_width(floors, path):
    """Narrowest cross section on the route, counted in standing cells."""
    narrowest = 99
    for x, z, h in path[::3]:
        best = 0
        for dx, dz in ((1, 0), (0, 1)):
            run = 1
            for sign in (1, -1):
                X, Z, H = x, z, h
                while run < 9:
                    X, Z = X + dx * sign, Z + dz * sign
                    near = [q for q in floors.column(X, Z) if abs(q - H) <= STEP + 1e-6]
                    if not near:
                        break
                    H = near[0]
                    run += 1
            best = max(best, run)
        narrowest = min(narrowest, best)
    return narrowest


def review(a):
    shapes = json.loads((a.metadata / 'native_collision_shapes.json').read_text('utf8'))
    walker = Walker(a.source, shapes)
    sites = json.loads(a.sites.read_text('utf8'))
    native = platforms(a.native)
    rails = [r for r in load_rails(a.native) if r['mode'] != 'CABLE_CAR']
    with np.load(a.authority / 'network.npz') as f:
        ax, az, _, _ = map(int, f['bounds'])
        public = f['walk'] | f['road']
        grade = f['grade2'].copy()
    rows = []
    for site in sites:
        if site['kind'] != 'existing' or (a.only and site['name'] not in a.only):
            continue
        a0, b0, c0, A0, B0, C0 = site['station_bounds']
        near = [r for r in rails if not (max(r['a'][0], r['b'][0]) < site['bounds'][0] - 3 or min(r['a'][0], r['b'][0]) > site['bounds'][3] + 3
                                         or max(r['a'][2], r['b'][2]) < site['bounds'][2] - 3 or min(r['a'][2], r['b'][2]) > site['bounds'][5] + 3)]
        floors = Floors(walker, site['bounds'], near)
        owned = [p for p in native if a0 - 1 <= (p['position1']['x'] + p['position2']['x']) / 2 <= A0 + 1
                 and c0 - 1 <= (p['position1']['z'] + p['position2']['z']) / 2 <= C0 + 1
                 and b0 - 1 <= p['position1']['y'] <= B0 + 1]

        def street(node):
            x, z, h = node
            i, j = z - az, x - ax
            if not (0 <= i < public.shape[0] and 0 <= j < public.shape[1] and public[i, j]):
                return False
            return abs((int(grade[i, j]) + 1) // 2 + (1 if grade[i, j] % 2 == 0 else .5) - h) <= 1

        def outside(node):
            x, z, h = node
            a, b, c, A, B, C = site['bounds']
            # Station floors are declared public too, so a street must lie past the platform.
            away = min(float(chord_distance(dict(a=[q['position1'][k] for k in 'xyz'], b=[q['position2'][k] for k in 'xyz']),
                                            np.array([[x, z]]))[0]) for q in owned) > 14
            return (street(node) and away) or (x <= a + 1 or x >= A - 1 or z <= c + 1 or z >= C - 1)

        results = []
        for p in owned:
            nodes = boarding_nodes(floors, p)
            mode = p['transportMode']
            if not nodes:
                results.append(dict(platform=str(p['id']), name=p['name'], mode=mode, status='no_boarding_floor'))
                continue
            nodes = {n for n in nodes if not floors.trackbed(*n)}
            path, seen = search(floors, sorted(nodes), outside)
            row = dict(platform=str(p['id']), name=p['name'], mode=mode, boarding_cells=len(nodes), reached_nodes=seen)
            if path:
                row.update(status='reaches_street' if street(path[-1]) else 'leaves_review_box', length=len(path), minimum_width=clear_width(floors, path),
                           route=[[q[0] + .5, q[1] + .5, q[2]] for q in path])
            else:
                # Pontoons and thresholds can need a jump; never count that as a step-free route.
                floors.step = JUMP
                path, seen = search(floors, sorted(nodes), outside)
                floors.step = STEP
                row['status'] = 'reaches_only_by_jumping' if path else 'no_street_without_lift'
                if path:
                    row.update(length=len(path), route=[[q[0] + .5, q[1] + .5, q[2]] for q in path],
                               jumps=[list(q) for q, r in zip(path, path[1:]) if abs(q[2] - r[2]) > STEP + 1e-6])
            results.append(row)
        rows.append(dict(name=site['name'], bounds=site['bounds'], registered=len(owned), platforms=results,
                         doors=dict(floors.doors), counts=dict(Counter(r['status'] for r in results))))
        print(site['name'], len(owned), rows[-1]['counts'],
              min((r['minimum_width'] for r in results if 'minimum_width' in r), default=None), flush=True)
    a.out.mkdir(exist_ok=False)
    (a.out / 'review.json').write_text(json.dumps(dict(stations=rows, source=str(a.source), world_written=False,
        counts=dict(Counter(r['status'] for s in rows for r in s['platforms']))), ensure_ascii=False, indent=1), 'utf8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'metadata', 'sites', 'native', 'authority', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--only', nargs='*')
    review(parser.parse_args())
