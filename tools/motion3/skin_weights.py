"""Author continuous joint skin weights for an EVA mesh (runtime jointSkins format).

python skin_weights.py --mesh eva_unit01.mesh.json --geo eva_unit01.geo.json --out eva_unit01.mesh.json

The weights come from one spatial field per joint (smoothstep across the joint
along the limb axis, limited laterally to the limb), evaluated at the rest
position of every vertex regardless of which part holds it.  Coincident
vertices in neighbouring parts therefore receive identical weights and move
together, so the shoulder, hip, knee and neck stop tearing like the seams the
runtime already welds.  Separate armour islands (every island but the largest of
a part) take, vertex by vertex, the weights of the nearest point on their own
part's body surface: a plate is glued to the surface it covers and cannot
separate at a joint, and plates away from joints stay rigid because the skin
under them is.
Weights are written as runtime-authored influences (no inverse bind: the
pivot rig's rest transforms are identity).
"""

import argparse
import json

import numpy as np

STRIDE = 8


def smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def unit(v):
    v = np.asarray(v, dtype=float)
    return v / max(np.linalg.norm(v), 1e-9)


def joints_for(piv):
    """(parent, child, centre, axis, blend radius, lateral reach) in geo pixels."""
    out = []

    def has(*names):
        return all(n in piv for n in names)

    if has("torso_lower", "torso_upper"):
        out.append(("torso_lower", "torso_upper", piv["torso_upper"], (0, 1, 0), 3.5, None))
    if has("torso_upper", "head"):
        out.append(("torso_upper", "head", piv["head"], (0, 1, 0), 3.0, 11.0))
    for s in ("l", "r"):
        if has("arm_" + s, "forearm_" + s):
            # armoured shoulder: only the socket blends, so the chest shell
            # does not follow the arm swing
            out.append(("torso_upper", "arm_" + s, piv["arm_" + s],
                        unit(piv["forearm_" + s] - piv["arm_" + s]), 3.5, 7.0))
            # the elbow turns about its hinge centre behind the forearm pivot
            # (EvaRigTransforms.elbow), not the pivot; blending there bent the shell
            elbow = np.array([23.489652 if s == "l" else -23.489652, 123.435069, 7.737214])
            out.append(("arm_" + s, "forearm_" + s, elbow,
                        unit(piv["wrist_" + s] - elbow), 4.5, 9.0))
        if has("forearm_" + s, "hand_" + s, "finger_middle_axis_" + s):
            out.append(("forearm_" + s, "hand_" + s, piv["hand_" + s],
                        unit(piv["finger_middle_axis_" + s] - piv["hand_" + s]), 2.5, 6.0))
        if has("leg_" + s, "shin_" + s, "ankle_" + s):
            out.append(("torso_lower", "leg_" + s, piv["leg_" + s],
                        unit(piv["shin_" + s] - piv["leg_" + s]), 6.0, 12.0))
            # likewise the knee turns 11.4 px above the shin pivot (EvaRigTransforms.knee)
            knee = piv["shin_" + s] + np.array([0, 11.4, 0])
            out.append(("leg_" + s, "shin_" + s, knee,
                        unit(piv["ankle_" + s] - knee), 5.0, 9.0))
        if has("shin_" + s, "foot_" + s):
            out.append(("shin_" + s, "foot_" + s, piv["foot_" + s], (0, -1, 0), 2.5, 7.0))
    return out


def islands(pts, tri_count, eps=0.01):
    """Connected components of a triangle soup (vertices welded by position)."""
    key = np.round(pts / eps).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    parent = np.arange(inv.max() + 1)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for t in range(tri_count):
        a, b, c = inv[3 * t], inv[3 * t + 1], inv[3 * t + 2]
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[find(rc)] = ra
    roots = np.array([find(i) for i in inv])
    _, comp = np.unique(roots, return_inverse=True)
    return comp.ravel()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--geo", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.mesh, encoding="utf-8") as f:
        mesh = json.load(f)
    with open(a.geo, encoding="utf-8") as f:
        geo = json.load(f)["minecraft:geometry"][0]["bones"]
    piv = {b["name"]: np.array(b.get("pivot", [0, 0, 0]), dtype=float) for b in geo}
    zones = joints_for(piv)
    skins = mesh.setdefault("jointSkins", {})
    stats = {}

    def field(name, sample):
        """Joint-field weights for points owned by part `name`."""
        n = len(sample)
        weights = {name: np.ones(n)}
        for parent, child, centre, axis, r, reach in [z for z in zones if name in (z[0], z[1])]:
            axis = unit(axis)
            d = (sample - centre) @ axis
            lat = np.linalg.norm((sample - centre) - np.outer(d, axis), axis=1)
            f = smooth((d + r) / (2 * r))
            g = np.ones(n) if reach is None else 1 - smooth((lat - reach) / (0.35 * reach))
            if name == parent:
                share = weights[name] * f * g
                weights[name] = weights[name] - share
                weights[child] = weights.get(child, np.zeros(n)) + share
            else:
                share = weights[name] * (1 - f) * g
                weights[name] = weights[name] - share
                weights[parent] = weights.get(parent, np.zeros(n)) + share
        return weights

    # pass 1: split every part into its body-suit surface (largest island) and
    # armour plates (all other islands); the surfaces of all parts together form
    # the skin the plates are glued to
    geom = {}
    surf_pts, surf_owner = [], []
    for name, part in mesh["parts"].items():
        v = np.asarray(part["vertices"], dtype=float).reshape(-1, STRIDE)
        pts = v[:, :3] + np.asarray(part["pivot"], dtype=float)
        comp = islands(pts, len(pts) // 3)
        ids, counts = np.unique(comp, return_counts=True)
        plate = comp != ids[np.argmax(counts)]
        geom[name] = (pts, plate, len(ids) - 1)
        surf_pts.append(pts[~plate])
        surf_owner += [name] * int((~plate).sum())
    surf_pts = np.concatenate(surf_pts)
    surf_owner = np.array(surf_owner)

    # only the articulated body takes part: pylons, the dorsal hatch and the jaw
    # keep their own animated bones untouched
    skin_parts = {p for z in zones for p in z[:2]} & set(mesh["parts"])

    def nearest_surface(points, allowed):
        cand = np.nonzero(np.isin(surf_owner, list(allowed)))[0]
        idx = np.empty(len(points), dtype=int)
        for s in range(0, len(points), 256):
            chunk = points[s:s + 256]
            d2 = ((chunk[:, None, :] - surf_pts[cand][None, :, :]) ** 2).sum(-1)
            idx[s:s + 256] = cand[d2.argmin(1)]
        return idx

    # pass 2: surfaces sample the field where they are; every plate vertex takes
    # the weights of the nearest body-surface point, so a plate stays glued to
    # whatever it covers and cannot separate when the joint bends
    for name in sorted(skin_parts):
        pts, plate, rigid = geom[name]
        n = len(pts)
        weights = {k: w for k, w in field(name, pts).items()}
        if plate.any():
            pidx = np.nonzero(plate)[0]
            # own surface only: a chest plate beside the shoulder must not
            # pick up the arm's weights from the arm surface next to it
            near = nearest_surface(pts[pidx], {name})
            for k in weights:
                weights[k][pidx] = 0.0
            for owner in [str(o) for o in np.unique(surf_owner[near])]:
                sel = surf_owner[near] == owner
                for k, w in field(owner, surf_pts[near[sel]]).items():
                    weights.setdefault(k, np.zeros(n))[pidx[sel]] += w
        weights = {k: w for k, w in weights.items() if w.max() > 1e-4}
        if len(weights) == 1:
            continue
        total = sum(weights.values())
        rounded = {k: np.round(w / total, 6) for k, w in weights.items()}
        # make every row sum to exactly one after rounding
        resid = 1.0 - sum(rounded.values())
        rounded[name] = np.round(rounded[name] + resid, 6)
        skins[name] = {"influences": {k: [float(x) for x in w] for k, w in rounded.items()},
                       "source": "tools/motion3/skin_weights.py continuous joint field"}
        stats[name] = (n, sorted(weights.keys()), rigid)
    mesh["skin_revision"] = "motion3-field-v1"
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(mesh, f, separators=(",", ":"))
    for k, (n, bones, rigid) in stats.items():
        print(f"{k:14s} verts {n:6d} rigid islands {rigid:3d} palette {bones}")


if __name__ == "__main__":
    main()
