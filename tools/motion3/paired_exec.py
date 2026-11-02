"""Retarget a paired capture (attacker + victim takes of one recording) onto an
EVA and an Angel, placed facing each other.

python paired_exec.py --body eva_body_r44.json --angel-geo sachiel.geo.json --variant 1 \
    --attacker <a.npz> --victim <v.npz> --out paired.json [--grab 15:40]

Mixamo exports each side of a paired move at its own origin, both facing
forward.  The victim is turned to face the attacker and set at the
distance (searched in the source) where the attacker's hands meet the
victim's legs/hips over the grab window.  Output: per actor the bone list,
local quaternions per frame, root translation per frame (model units) and
the actor's placement (yaw, offset), at the source frame rate.
"""

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from angel_rig import AngelRetargeter  # noqa: E402
from baked import Baked  # noqa: E402
from evarig import Rig, mat_to_quat  # noqa: E402
from retarget import Retargeter, Source  # noqa: E402

R180 = np.diag([-1.0, 1.0, -1.0])


def solve_distance(sa, sv, window):
    a, b = window
    best = None
    for d in np.linspace(0.1, 2.5, 241):
        err = []
        for f in range(a, min(b, sa.n, sv.n)):
            targets = [R180 @ sv.P[k][f] + np.array([0, 0, -d]) for k in ("thigh_l", "thigh_r", "hips", "shin_l", "shin_r")]
            for h in ("hand_l", "hand_r"):
                err.append(min(np.linalg.norm(sa.P[h][f] - t) for t in targets))
        e = float(np.mean(err))
        if best is None or e < best[0]:
            best = (e, d)
    return best[1], best[0]


def track(res, names):
    q = {n: mat_to_quat(res["local"][n]) for n in names if n in res["local"]}
    bones = list(q)
    rot = np.stack([q[n] for n in bones], axis=1)
    return {"bones": bones, "rot": [round(float(x), 5) for x in rot.reshape(-1)],
            "root": [round(float(x), 5) for x in np.asarray(res["root"]).reshape(-1)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True)
    ap.add_argument("--angel-geo", required=True)
    ap.add_argument("--variant", type=int, default=1)
    ap.add_argument("--attacker", required=True)
    ap.add_argument("--victim", required=True)
    ap.add_argument("--grab", default="15:40")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    A, V = Baked(a.attacker), Baked(a.victim)
    sa, sv = Source(A, "mixamo", align_frame=0), Source(V, "mixamo", align_frame=0)
    d, err = solve_distance(sa, sv, tuple(int(x) for x in a.grab.split(":")))
    eva = Retargeter(Rig.from_body_profile(a.body, a.variant))
    angel = AngelRetargeter(a.angel_geo)
    ra, rv = eva.run(sa, None), angel.run(sv)
    n = min(sa.n, sv.n)
    out = {"fps": sa.rate, "frames": n, "source_distance_m": d, "grab_error_m": err,
           "scale": {"eva": ra["scale"], "angel": rv["scale"]},
           "eva": track(ra, list(eva.rig.names)) | {"yaw": 0.0, "offset": [0.0, 0.0, 0.0]},
           "angel": track(rv, list(angel.rig.names)) | {"yaw": 180.0, "offset": [0.0, 0.0, -d * ra["scale"]]}}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print("distance", round(d, 3), "m  grab error", round(err, 3), "m  scales", round(ra["scale"], 3), round(rv["scale"], 3),
          "frames", n, "->", a.out)


if __name__ == "__main__":
    main()
