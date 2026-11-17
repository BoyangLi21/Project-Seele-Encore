"""The ground points of a unit's mesh as the game chose them before R63, for comparison with the game's log line
"R63 ground points of <asset> taken ...": python groundpoints.py <mesh.json> [<mesh.json> ...]

Reads the file whole (so not UN-00's 860 MB one) and repeats what EvaGroundContactR56.hulls and
EvaFootPlacement.feet did in single precision:
  hulls  for each ground part, how far out it reaches along each of 26 directions (which of several equally far
         vertices stands for it changes nothing that ground contact reads); the reaches are summed
  soles  every vertex of each foot (here each once: the game used to keep the repeats, which changes no result);
         x + 2y + 3z is summed over them
and prints the counts and the two sums, the figures the log line carries.
"""
import json
import sys

import numpy as np

PARTS = ("foot_l", "foot_r", "shin_l", "shin_r", "leg_l", "leg_r", "torso_lower", "torso_upper", "arm_l", "arm_r", "forearm_l", "forearm_r",
         "hand_l", "hand_r", "head")
F = np.float32


def directions():
    out = []
    for x in (-1, 0, 1):
        for y in (-1, 0, 1):
            for z in (-1, 0, 1):
                if x or y or z:
                    v = np.array([x, y, z], F)
                    out.append(v / F(np.sqrt(F(x * x + y * y + z * z))))
    return out


def points(part, stride):
    a = np.array(part['vertices'], F)
    p = np.array(part['pivot'], F)
    n = len(a) // stride
    raw = a[:n * stride].reshape(n, stride)[:, :3]
    return np.stack([-(raw[:, 0] + p[0]) / F(16), (raw[:, 1] + p[1]) / F(16), (raw[:, 2] + p[2]) / F(16)], 1).astype(F)


def total(rows):
    return float(sum(float(v[0]) + 2.0 * float(v[1]) + 3.0 * float(v[2]) for v in rows))


def main():
    for path in sys.argv[1:]:
        d = json.load(open(path, encoding='utf8'))
        stride = d.get('stride', 8)
        dirs = directions()
        hull_sum, hull_parts = 0.0, 0
        for name in PARTS:
            if name not in d['parts']:
                continue
            pts = points(d['parts'][name], stride)
            for v in dirs:
                hull_sum += float(np.max(pts.astype(np.float64) @ v.astype(np.float64)))
            hull_parts += 1
        feet_sum, counts = 0.0, []
        for side in 'lr':
            pts = points(d['parts']['foot_' + side], 8)
            seen, rows = set(), []
            for v in pts:
                key = v.tobytes()
                if key not in seen:
                    seen.add(key)
                    rows.append(v)
            counts.append(len(rows))
            feet_sum += total(rows)
        print('%s: %d hull parts (reach %.3f), soles of %d and %d vertices (sum %.3f)' % (path.replace('\\', '/').split('/')[-1], hull_parts, hull_sum, counts[0], counts[1], feet_sum))


if __name__ == '__main__':
    main()
