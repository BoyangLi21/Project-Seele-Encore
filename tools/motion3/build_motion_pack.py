"""Build the SEELE motion pack (locomotion set) for the four piloted EVAs.

python build_motion_pack.py --body eva_body_r44.json --bandai <dataset-1/data> --out seele_motion_pack.json

Pack format (version 1): per rig key, model-space data the runtime samples
directly -- quaternions w,x,y,z per animated bone per frame, root translation
in model blocks, per-frame foot contacts, loop cycles stored in place with the
stride (model blocks travelled per cycle).
"""

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bvh import Bvh  # noqa: E402
from evarig import Rig, mat_to_quat, quat_to_mat  # noqa: E402
from retarget import Calibration, Retargeter, Source, foot_contacts  # noqa: E402

VARIANTS = (0, 1, 2, 4)
# forward chest lean (degrees) per clip; faster gaits drive the chest further over the hips
LEAN = {"idle": 5.0, "walk": 8.0, "run": 11.0, "sprint": 14.0, "walk_back": 3.0}
ANIMATED = ("root", "torso_lower", "torso_upper", "aim_pitch", "neck", "head",
            "clavicle_l", "arm_l", "forearm_l", "wrist_l", "hand_l",
            "clavicle_r", "arm_r", "forearm_r", "wrist_r", "hand_r",
            "leg_l", "shin_l", "ankle_l", "foot_l", "leg_r", "shin_r", "ankle_r", "foot_r")


def onsets(c):
    return [i for i in range(1, len(c)) if c[i] and not c[i - 1]]


def pick_cycle(src):
    """One full gait cycle from a left-foot strike to the next, nearest the middle."""
    cl = foot_contacts(src, "l")
    on = onsets(cl)
    if len(on) < 2:
        raise ValueError("no full cycle")
    mid = src.n / 2
    best = None
    for a, b in zip(on, on[1:]):
        if b - a < 10:
            continue
        score = abs((a + b) / 2 - mid)
        if best is None or score < best[0]:
            best = (score, a, b)
    return best[1], best[2]


def slerp_q(a, b, t):
    d = np.sum(a * b, axis=-1, keepdims=True)
    b = np.where(d < 0, -b, b)
    d = np.abs(d)
    th = np.arccos(np.clip(d, -1, 1))
    s = np.sin(th)
    t = np.asarray(t)[..., None] if np.ndim(t) else t
    w1 = np.where(s > 1e-6, np.sin((1 - t) * th) / np.maximum(s, 1e-9), 1 - t)
    w2 = np.where(s > 1e-6, np.sin(t * th) / np.maximum(s, 1e-9), t)
    q = a * w1 + b * w2
    return q / np.linalg.norm(q, axis=-1, keepdims=True)


def cycle_clip(res, src, a, b, blend=6, rate_out=60):
    """Loop frames [a, b) in place; cross-fade the seam using the frames before a."""
    L = b - a
    quats = {n: mat_to_quat(res["local"][n]) for n in ANIMATED if n in res["local"]}
    root = res["root"].copy()
    travel = root[b] - root[a]
    stride = float(np.hypot(travel[0], travel[2]))
    out_q = {}
    for n, q in quats.items():
        seg = q[a:b].copy()
        for k in range(blend):
            i = L - blend + k
            w = (k + 1) / (blend + 1)
            w = w * w * (3 - 2 * w)
            seg[i] = slerp_q(seg[i], q[a - blend + k], w)
        out_q[n] = seg
    seg_root = root[a:b].copy()
    t = np.arange(L) / L
    # in place horizontally only; the height carries the knee bend
    base = root[a] * np.array([1.0, 0.0, 1.0])
    seg_root -= base
    seg_root[:, 0] -= travel[0] * t
    seg_root[:, 2] -= travel[2] * t
    # seam for the vertical/lateral residue
    pre = root[a - blend:a] - base - (travel * (np.arange(-blend, 0) / L)[:, None]) * np.array([1, 0, 1])
    for k in range(blend):
        i = L - blend + k
        w = (k + 1) / (blend + 1)
        w = w * w * (3 - 2 * w)
        seg_root[i] = seg_root[i] * (1 - w) + pre[k] * w
    seg_root[:, 0] -= seg_root[:, 0].mean()
    cl = foot_contacts(src, "l")[a:b]
    cr = foot_contacts(src, "r")[a:b]
    # resample to rate_out over the closed loop
    dur = L / src.rate
    m = max(2, int(round(dur * rate_out)))
    pos = np.arange(m) / m * L
    i0 = np.floor(pos).astype(int)
    fr = pos - i0
    i1 = (i0 + 1) % L
    rq = {n: slerp_q(q[i0], q[i1], fr) for n, q in out_q.items()}
    rr = seg_root[i0] * (1 - fr)[:, None] + seg_root[i1] * fr[:, None]
    rc = np.stack([cl[np.round(pos).astype(int) % L], cr[np.round(pos).astype(int) % L]], axis=1)
    return {"rate": rate_out, "loop": True, "frames": m, "duration": dur, "stride": stride,
            "q": rq, "root": rr, "contact": rc}


def hold_clip(res, src, frame, seconds=4.0, rate_out=60, breathe=True):
    """A standing idle loop from one source frame with a slow breathing layer."""
    m = int(seconds * rate_out)
    t = np.arange(m) / m
    out = {}
    for n in ANIMATED:
        if n not in res["local"]:
            continue
        q = mat_to_quat(res["local"][n][frame:frame + 1])[0]
        out[n] = np.tile(q, (m, 1))
    root = np.tile(res["root"][frame] * np.array([0, 1, 0]), (m, 1))
    if breathe:
        ph = 2 * np.pi * t
        def rot_x(a):
            c, s = np.cos(a / 2), np.sin(a / 2)
            return np.stack([c, s, np.zeros_like(a), np.zeros_like(a)], axis=1)
        def qmul(a, b):
            w1, x1, y1, z1 = a.T
            w2, x2, y2, z2 = b.T
            return np.stack([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                             w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2], axis=1)
        # chest expands (slight extension) and the head counters it
        out["torso_upper"] = qmul(out["torso_upper"], rot_x(np.radians(1.1) * np.sin(ph)))
        out["head"] = qmul(out["head"], rot_x(np.radians(-0.8) * np.sin(ph)))
        out["arm_l"] = qmul(out["arm_l"], rot_x(np.radians(0.9) * np.sin(ph + 0.6)))
        out["arm_r"] = qmul(out["arm_r"], rot_x(np.radians(0.9) * np.sin(ph + 0.6)))
        root[:, 1] += 0.015 * np.sin(ph)
    return {"rate": rate_out, "loop": True, "frames": m, "duration": seconds, "stride": 0.0,
            "q": out, "root": root, "contact": np.ones((m, 2), dtype=bool)}


def _qmul(a, b):
    w1, x1, y1, z1 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    w2, x2, y2, z2 = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2], axis=-1)


def _qx(deg):
    a = np.radians(deg) / 2
    return np.array([np.cos(a), np.sin(a), 0.0, 0.0])


def stylize(clip, lean=7.0, head_keep=0.8, arm_keep=0.7):
    """EVA posture: the chest pitches forward over the pelvis (the source giant
    style carries its chest back).  Head and arms counter most of the lean so
    the gaze stays level and the arms still hang under gravity.  Legs attach to
    the pelvis and are untouched, so ground contact is preserved."""
    q = clip["q"]
    if "torso_upper" in q:
        # pre-multiply: rotation about the parent (pelvis) X axis; EVA faces -Z
        q["torso_upper"] = _qmul(_qx(-lean), q["torso_upper"])
    if "head" in q:
        q["head"] = _qmul(_qx(lean * head_keep), q["head"])
    for side in ("l", "r"):
        if "arm_" + side in q:
            q["arm_" + side] = _qmul(_qx(lean * arm_keep), q["arm_" + side])
    return clip


def encode(clip):
    names = [n for n in ANIMATED if n in clip["q"]]
    q = np.stack([clip["q"][n] for n in names], axis=1)  # frames, bones, 4
    return {
        "rate": clip["rate"], "loop": clip["loop"], "frames": int(clip["frames"]),
        "duration": round(float(clip["duration"]), 5), "stride": round(float(clip["stride"]), 5),
        "bones": names,
        "rot": [round(float(x), 5) for x in q.reshape(-1)],
        "root": [round(float(x), 5) for x in np.asarray(clip["root"]).reshape(-1)],
        "contact": [int(x) for x in np.asarray(clip["contact"]).reshape(-1)],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True)
    ap.add_argument("--bandai", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    bandai = lambda name: os.path.join(a.bandai, f"dataset-1_{name}.bvh")  # noqa: E731
    calib_src = Source(Bvh(bandai("walk_normal_001")), "bandai")
    cal = Calibration(calib_src, 0)
    specs = {
        "walk": "walk_giant_001",
        "run": "run_giant_001",
        "sprint": "dash_giant_001",
        "walk_back": "walk-back_giant_001",
    }
    pack = {"format": "seele-motion-pack", "version": 1, "variants": {},
            "provenance": {
                "source": "Bandai Namco Research Motiondataset-1 (CC BY-NC 4.0), giant style",
                "method": "landmark + rotation-delta retarget, two-bone leg IK, in-place loops",
                "tool": "tools/motion3/build_motion_pack.py"}}
    bvhs = {k: Bvh(bandai(v)) for k, v in specs.items()}
    idle_bvh = Bvh(bandai("walk_giant_001"))
    for variant in VARIANTS:
        rig = Rig.from_body_profile(a.body, variant)
        rt = Retargeter(rig)
        clips = {}
        for key, bvh in bvhs.items():
            probe = Source(bvh, "bandai")
            ca, cb = pick_cycle(probe)
            src = Source(bvh, "bandai", travel=(ca, cb))
            if key == "walk_back":
                # travel is backwards: face the opposite way
                src = Source(bvh, "bandai", travel=(cb, ca))
            res = rt.run(src, cal)
            clip = stylize(cycle_clip(res, src, ca, cb), lean=LEAN[key])
            clips[key] = encode(clip)
            print(variant, key, "cycle", ca, cb, "frames60", clip["frames"], "stride", round(clip["stride"], 3))
        isrc = Source(idle_bvh, "bandai", align_frame=8)
        ires = rt.run(isrc, cal)
        clips["idle"] = encode(stylize(hold_clip(ires, isrc, 8), lean=LEAN["idle"]))
        pack["variants"][str(variant)] = {"clips": clips}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(pack, f, separators=(",", ":"))
    print("wrote", a.out, os.path.getsize(a.out) // 1024, "KiB")


if __name__ == "__main__":
    main()
