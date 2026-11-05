"""Render the authored scene: python review.py out.png [view,...] t1 t2 ...

Views: side (Unit-01's right), left, front34, back34, top, film.
"""
import math
import sys

import numpy as np

import chor
import rig as R
import scene as S

DEATH = 18.6

OCT = [(math.cos(math.radians(22.5 + 45 * i)) * 25.5 / math.cos(math.radians(22.5)),
        math.sin(math.radians(22.5 + 45 * i)) * 25.5 / math.cos(math.radians(22.5))) for i in range(8)]


def field_lines(t):
    if not (0.5 < t < 5.1):
        return []
    gap = chor.field_x(t)
    out = []
    for i in range(8):
        a, b = OCT[i], OCT[(i + 1) % 8]
        for k in range(8):
            u, v = k / 8, (k + 1) / 8
            x0, y0 = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
            x1, y1 = a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v
            if abs((x0 + x1) / 2) < gap * max(0, 1 - abs((y0 + y1) / 2) / 24):
                continue
            out.append(((x0 * .7, chor.FIELD_Y + y0 * .7, chor.FIELD_Z), (x1 * .7, chor.FIELD_Y + y1 * .7, chor.FIELD_Z), (255, 150, 30)))
    return out


def scene_groups(sc, t):
    s = sc.solve(t)
    em, am = s['eva'][2], s['angel'][2]
    groups = [sc.actors.eva_mesh.triangles(em, np.eye(4))]
    if t < DEATH:
        groups.append(sc.actors.angel_mesh.triangles(am, np.eye(4)))
    return groups, s


def camera(view, mid, size):
    if view == 'side':
        return R.Camera(mid + np.array([-135, 30, 0]), mid + np.array([0, 26, 0]), 40, size)
    if view == 'left':
        return R.Camera(mid + np.array([135, 30, 0]), mid + np.array([0, 26, 0]), 40, size)
    if view == 'front34':
        return R.Camera(mid + np.array([-80, 45, 95]), mid + np.array([0, 26, 0]), 45, size)
    if view == 'back34':
        return R.Camera(mid + np.array([70, 50, -95]), mid + np.array([0, 26, 0]), 45, size)
    if view == 'top':
        return R.Camera(mid + np.array([-1, 170, 0]), mid + np.array([0, 0, 0.01]), 50, size)
    raise ValueError(view)


def render_times(sc, times, views, size=(420, 300), mid=None):
    images = []
    for t in times:
        groups, s = scene_groups(sc, t)
        m = mid if mid is not None else np.array([0, 0, 21.0])
        for v in views:
            info = s['eva'][3]
            label = 't=%.2f %s  kL%.0f kR%.0f eL%.0f eR%.0f' % (t, v, info['knee_l'], info['knee_r'], info['elbow_l'], info['elbow_r'])
            images.append(R.render(camera(v, m, size), groups, label=label, lines=field_lines(t),
                                   ground=(-80, 80, -40, 120)))
    return images


def main():
    out = sys.argv[1]
    views = sys.argv[2].split(',')
    times = [float(x) for x in sys.argv[3:]]
    sc = chor.Scene(S.Actors())
    R.sheet(render_times(sc, times, views), len(views)).save(out)
    print('wrote', out)


if __name__ == '__main__':
    main()
