"""GeckoLib forward kinematics in model space (blocks / 16 px, X mirrored).

A baked GeckoLib bone keeps its geo pivot with X negated and its initial
rotation with X and Y negated.  Drawing it applies, from the parent:
translate(-posX, posY, posZ) / 16, translate(pivot), Rz * Ry * Rx, scale,
translate(-pivot).  Recorded channels are the final getRot*/getPos* values,
initial rotation included, then optionally a hidden flag and the scale.
"""

import json
import math

import numpy as np


def load_rig(geo_path):
    g = json.load(open(geo_path, encoding="utf-8"))
    rig = {}
    for b in g["minecraft:geometry"][0]["bones"]:
        p = b.get("pivot", [0, 0, 0])
        r = [math.radians(v) for v in (b.get("rotation") or [0, 0, 0])]
        rig[b["name"]] = {"parent": b.get("parent"), "pivot": np.array([-p[0], p[1], p[2]], float) / 16.0,
                          "bind": (-r[0], -r[1], r[2])}
    return rig


def euler_quat(rx, ry, rz):
    """Rz * Ry * Rx as a (w, x, y, z) quaternion."""
    cx, sx = math.cos(rx / 2), math.sin(rx / 2)
    cy, sy = math.cos(ry / 2), math.sin(ry / 2)
    cz, sz = math.cos(rz / 2), math.sin(rz / 2)
    return np.array([cz * cy * cx + sz * sy * sx, cz * cy * sx - sz * sy * cx,
                     cz * sy * cx + sz * cy * sx, sz * cy * cx - cz * sy * sx])


def quat_slerp(a, b, t):
    d = float(np.dot(a, b))
    if d < 0:
        b, d = -b, -d
    if d > 0.9995:
        q = a + (b - a) * t
        return q / np.linalg.norm(q)
    th = math.acos(min(1.0, d))
    return (math.sin((1 - t) * th) * a + math.sin(t * th) * b) / math.sin(th)


def quat_matrix(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def channel_state(ch):
    """Recorded [rx, ry, rz, px, py, pz(, hidden(, sx, sy, sz))] -> (quaternion, model-space offset, scale)."""
    scale = np.array(ch[7:10], float) if len(ch) >= 10 else np.ones(3)
    return euler_quat(ch[0], ch[1], ch[2]), np.array([-ch[3], ch[4], ch[5]], float) / 16.0, scale


def blend_states(a, b, t):
    return quat_slerp(a[0], b[0], t), a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t


def model_matrices(rig, states):
    """states: bone -> (quaternion, offset, scale); bones without a state stay at bind."""
    out = {}

    def get(name):
        if name in out:
            return out[name]
        b = rig[name]
        q, pos, scale = states.get(name) or (euler_quat(*b["bind"]), np.zeros(3), np.ones(3))
        local = np.eye(4)
        local[:3, :3] = quat_matrix(q) * scale
        local[:3, 3] = pos + b["pivot"] - local[:3, :3] @ b["pivot"]
        out[name] = (get(b["parent"]) if b["parent"] else np.eye(4)) @ local
        return out[name]

    for name in rig:
        get(name)
    return out
