"""Contact sheet of a first_battle clip: python preview_clip.py clip.json out.png t1 t2 ...

Each time gets a side view, a three-quarter view and the clip's own camera.
"""
import sys

import numpy as np

import rig as R
import scene as S


def views(groups, mid, clip, t, size=(480, 300)):
    side = R.Camera(mid + np.array([-150, 35, 0]), mid + np.array([0, 28, 0]), 45, size)
    three = R.Camera(mid + np.array([95, 55, -95]), mid + np.array([0, 25, 0]), 50, size)
    out = [R.render(side, groups, label='t=%.2f side' % t),
           R.render(three, groups, label='t=%.2f 3/4' % t)]
    if clip is not None:
        e, target, fov = clip.camera(t)
        out.append(R.render(R.Camera(e, target, fov, size), groups, label='t=%.2f film' % t))
    return out


def main():
    path, out = sys.argv[1], sys.argv[2]
    times = [float(x) for x in sys.argv[3:]]
    actors = S.Actors()
    clip = S.Clip(path)
    images = []
    for t in times:
        groups, me, ma = S.clip_scene(actors, clip, t)
        mid = (me['root'][:3, 3] + ma['root'][:3, 3]) / 2
        mid[1] = 0
        images += views(groups, mid, clip, t)
    R.sheet(images, 3).save(out)
    print('wrote', out)


if __name__ == '__main__':
    main()
