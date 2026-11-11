"""Probe script for fixed camera views: each view looks at a target from a horizontal direction.

views: [{name, target: [x, y, z], dir: [dx, dz] (from target towards camera), dist, rise}]
"""
import json, math, sys


def view_steps(v, prefix):
    tx, ty, tz = v['target']
    dx, dz = v['dir']
    n = math.hypot(dx, dz)
    dx, dz = dx / n, dz / n
    d = v.get('dist', 6)
    rise = v.get('rise', 1.5)
    ex, ey, ez = tx + 0.5 + dx * d, ty + 0.5 + rise, tz + 0.5 + dz * d
    yaw = math.degrees(math.atan2(dx, -dz))          # looking back along -dir
    pitch = math.degrees(math.atan2(rise, d))
    return [dict(op='tp', x=round(ex, 2), y=round(ey - 1.62, 2), z=round(ez, 2), yaw=round(yaw, 1), pitch=round(pitch, 1), fly=True,
                 wait=v.get('wait', 60)),
            dict(op='shot', name=prefix + v['name'])]


def build(views, prefix, path):
    steps = []
    for v in views:
        steps += view_steps(v, prefix)
    json.dump(steps, open(path, 'w'), indent=0)
    return len(steps)


if __name__ == '__main__':
    views = json.load(open(sys.argv[1], encoding='utf8'))
    print(build(views, sys.argv[2], sys.argv[3]))
