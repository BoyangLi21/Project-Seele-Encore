"""EVA runtime rig (pivot skeleton) in model space, numpy forward kinematics.

Model space: blocks, +Y up, the EVA faces -Z, its left side is -X.
Bone local matrix = T(pos) T(pivot) R T(-pivot); world = parent_world @ local.
"""

import json

import numpy as np


def px_to_model(p):
    return np.array([-p[0] / 16.0, p[1] / 16.0, p[2] / 16.0])


def euler_zyx_bind(deg):
    """Geo bind rotation (deg) -> model rotation matrix, JOML rotationZYX(z, -y, -x)."""
    x, y, z = np.radians(deg)
    return rot_z(z) @ rot_y(-y) @ rot_x(-x)


def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


class Rig:
    def __init__(self, bones):
        """bones: list of dicts {name, parent, pivot(px), rotation(deg)?}."""
        self.names = []
        self.parent = {}
        self.pivot = {}
        self.bind = {}
        pending = {b["name"]: b for b in bones}
        placed = set()
        while pending:
            progressed = False
            for name in list(pending):
                b = pending[name]
                p = b.get("parent")
                if p is None or p in placed or p not in {x["name"] for x in bones}:
                    self.names.append(name)
                    self.parent[name] = p if p in {x["name"] for x in bones} else None
                    self.pivot[name] = px_to_model(b["pivot"])
                    rot = b.get("rotation") or b.get("bindRotationDegrees")
                    self.bind[name] = euler_zyx_bind(rot) if rot else np.eye(3)
                    placed.add(name)
                    del pending[name]
                    progressed = True
            if not progressed:
                raise ValueError("cyclic rig")
        self.index = {n: i for i, n in enumerate(self.names)}

    @staticmethod
    def from_body_profile(path, variant):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return Rig(d["rigs"][str(variant)])

    def children(self, name):
        return [n for n in self.names if self.parent[n] == name]

    def fk(self, local_rot, local_pos=None):
        """local_rot: name -> (n,3,3); local_pos: name -> (n,3). Returns world rot, world pivot pos."""
        n = next(iter(local_rot.values())).shape[0]
        wr, wp = {}, {}
        for name in self.names:
            r = local_rot.get(name)
            if r is None:
                r = np.tile(self.bind[name] if "_axis_" in name else np.eye(3), (n, 1, 1))
            t = np.zeros((n, 3)) if local_pos is None or name not in local_pos else local_pos[name]
            p = self.parent[name]
            piv = self.pivot[name]
            if p is None:
                wr[name] = r
                wp[name] = t + piv
                self._root_pivot = piv
            else:
                # world pivot = parent world transform applied to (pivot + t)
                pr, pp = wr[p], wp[p]
                ppiv = self.pivot[p]
                wp[name] = pp + np.einsum("nij,nj->ni", pr, piv + t - ppiv)
                wr[name] = pr @ r
        return wr, wp


def basis(d, a):
    """Orthonormal frame (n,3,3) with columns [d, a', d x a'] from direction d and reference a."""
    d = d / np.linalg.norm(d, axis=-1, keepdims=True)
    a = a - d * np.sum(a * d, axis=-1, keepdims=True)
    na = np.linalg.norm(a, axis=-1, keepdims=True)
    a = a / np.maximum(na, 1e-9)
    c = np.cross(d, a)
    return np.stack([d, a, c], axis=-1)


def align(d_rest, a_rest, d_post, a_post):
    """World rotation taking the rest frame (d_rest, a_rest) onto (d_post, a_post)."""
    n = d_post.shape[0]
    br = basis(np.tile(d_rest, (n, 1)), np.tile(a_rest, (n, 1)))
    bp = basis(d_post, a_post)
    return bp @ np.transpose(br, (0, 2, 1))


def swing_to(rot, d_rest, d_post):
    """Pre-rotate world rotations so rot @ d_rest points along d_post (minimal swing)."""
    cur = np.einsum("nij,j->ni", rot, d_rest)
    cur /= np.linalg.norm(cur, axis=-1, keepdims=True)
    tgt = d_post / np.linalg.norm(d_post, axis=-1, keepdims=True)
    axis = np.cross(cur, tgt)
    s = np.linalg.norm(axis, axis=-1)
    c = np.clip(np.sum(cur * tgt, axis=-1), -1, 1)
    out = np.empty_like(rot)
    for i in range(rot.shape[0]):
        if s[i] < 1e-9:
            out[i] = rot[i]
            continue
        k = axis[i] / s[i]
        ang = np.arctan2(s[i], c[i])
        out[i] = axis_angle(k, ang) @ rot[i]
    return out


def axis_angle(k, a):
    k = np.asarray(k, dtype=float)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * (K @ K)


def mat_to_quat(m):
    """(n,3,3) -> (n,4) quaternion w,x,y,z, sign-continuous."""
    n = m.shape[0]
    q = np.empty((n, 4))
    for i in range(n):
        a = m[i]
        t = np.trace(a)
        if t > 0:
            s = np.sqrt(t + 1.0) * 2
            q[i] = [0.25 * s, (a[2, 1] - a[1, 2]) / s, (a[0, 2] - a[2, 0]) / s, (a[1, 0] - a[0, 1]) / s]
        elif a[0, 0] > a[1, 1] and a[0, 0] > a[2, 2]:
            s = np.sqrt(1.0 + a[0, 0] - a[1, 1] - a[2, 2]) * 2
            q[i] = [(a[2, 1] - a[1, 2]) / s, 0.25 * s, (a[0, 1] + a[1, 0]) / s, (a[0, 2] + a[2, 0]) / s]
        elif a[1, 1] > a[2, 2]:
            s = np.sqrt(1.0 + a[1, 1] - a[0, 0] - a[2, 2]) * 2
            q[i] = [(a[0, 2] - a[2, 0]) / s, (a[0, 1] + a[1, 0]) / s, 0.25 * s, (a[1, 2] + a[2, 1]) / s]
        else:
            s = np.sqrt(1.0 + a[2, 2] - a[0, 0] - a[1, 1]) * 2
            q[i] = [(a[1, 0] - a[0, 1]) / s, (a[0, 2] + a[2, 0]) / s, (a[1, 2] + a[2, 1]) / s, 0.25 * s]
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    for i in range(1, n):
        if np.dot(q[i], q[i - 1]) < 0:
            q[i] = -q[i]
    return q


def quat_to_mat(q):
    q = q / np.linalg.norm(q, axis=-1, keepdims=True)
    w, x, y, z = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    m = np.empty(q.shape[:-1] + (3, 3))
    m[..., 0, 0] = 1 - 2 * (y * y + z * z); m[..., 0, 1] = 2 * (x * y - z * w); m[..., 0, 2] = 2 * (x * z + y * w)
    m[..., 1, 0] = 2 * (x * y + z * w); m[..., 1, 1] = 1 - 2 * (x * x + z * z); m[..., 1, 2] = 2 * (y * z - x * w)
    m[..., 2, 0] = 2 * (x * z - y * w); m[..., 2, 1] = 2 * (y * z + x * w); m[..., 2, 2] = 1 - 2 * (x * x + y * y)
    return m
