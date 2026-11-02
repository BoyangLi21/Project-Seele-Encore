"""Build the review moveset (Mixamo / free captures -> EVA rig, EVA posture).

python moveset_v2.py --body eva_body_r44.json --mixamo <baked npz dir> --out review_pack.json [--variants 1]

Every slot names a baked take (blender/bake_fbx.py) and how it is cut:
loop    - a locomotion cycle (the take is one closed cycle, as Mixamo loops are)
action  - a one-shot played at source timing, with its travel split off
The EVA posture layer (retune_trunk / stylize, shared with build_motion_pack)
is applied per slot.  Output uses the seele-motion-pack format, so the pack
renderers and the runtime sampler read it unchanged.
"""

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from baked import Baked  # noqa: E402
from build_motion_pack import action_clip, cycle_clip, encode, retune_trunk, stylize  # noqa: E402
from evarig import Rig  # noqa: E402
from retarget import Retargeter, Source  # noqa: E402

# slot -> (take, kind, chest lean in degrees, time scale (>1 slower))
SLOTS = {
    # unarmed locomotion: A = standard capture, B = heavy "mutant" capture
    "idle_a": ("Breathing_Idle", "loop", 6.0, 1.0),
    "idle_b": ("Mutant_Breathing_Idle", "loop", 0.0, 1.0),
    "walk_a": ("Walking_21", "loop", 7.0, 1.15),
    "walk_b": ("Mutant_Walking", "loop", 0.0, 1.15),
    "run_a": ("Running_6", "loop", 10.0, 1.1),
    "run_b": ("Mutant_Run", "loop", 0.0, 1.1),
    "sprint": ("Fast_Run", "loop", 14.0, 1.05),
    # unarmed attacks
    "fight_idle": ("Fighting_Idle", "loop", 5.0, 1.0),
    "jab": ("Lead_Jab", "action", 4.0, 1.2),
    "cross": ("Cross_Punch", "action", 4.0, 1.2),
    "hook": ("Hook_Punch", "action", 4.0, 1.2),
    "heavy": ("Hook_2", "action", 3.0, 1.3),
    "kick": ("Mma_Kick", "action", 3.0, 1.25),
    "swipe": ("Mutant_Swiping", "action", 0.0, 1.15),
    # knife
    "knife_idle": ("Knife_Idle", "loop", 5.0, 1.0),
    "knife_stab": ("Stabbing_2", "action", 4.0, 1.2),
    "knife_reverse": ("Stabbing_3", "action", 4.0, 1.2),
    "knife_thrust": ("Thrust_Slash", "action", 4.0, 1.2),
    # rifle
    "rifle_aim": ("Rifle_Aiming_Idle", "loop", 4.0, 1.0),
    "rifle_fire": ("Firing_Rifle_2", "action", 4.0, 1.0),
    "rifle_walk_fire": ("Firing_Rifle_8", "loop", 4.0, 1.15),
    "rifle_run": ("Rifle_Run_2", "loop", 8.0, 1.1),
    "rifle_stand_to_kneel": ("Rifle_Stand_To_Kneel", "action", 0.0, 1.2),
    "rifle_kneel": ("Rifle_Kneel_Idle", "loop", 0.0, 1.0),
    "rifle_kneel_to_prone": ("Rifle_Kneel_To_Prone", "action", 0.0, 1.15),
    "prone_idle": ("Prone_Idle", "loop", 0.0, 1.0),
    "prone_fire": ("Prone_Firing_Rifle_2", "action", 0.0, 1.0),
    "prone_crawl": ("Prone_Forward", "loop", 0.0, 1.2),
    "rifle_prone_to_kneel": ("Rifle_Prone_To_Kneel", "action", 0.0, 1.15),
    "rifle_kneel_to_stand": ("Rifle_Kneel_To_Stand", "action", 0.0, 1.15),
    "rifle_crouch_walk": ("Rifle_Crouch_Walk_2", "loop", 0.0, 1.15),
    "rifle_crouch_fire": ("Firing_Rifle_5", "loop", 0.0, 1.15),
    # unarmed crouch / prone
    "stand_to_crouch": ("Standing_Idle_To_Crouch", "action", 0.0, 1.2),
    "crouch_idle": ("Crouch_Idle_2", "loop", 0.0, 1.0),
    "crouch_walk": ("Crouched_Walking", "loop", 0.0, 1.15),
    "crouch_to_prone": ("Crouch_To_Prone", "action", 0.0, 1.15),
    "crawl": ("Crawl_Forward", "loop", 0.0, 1.2),
    "prone_to_crouch": ("Prone_To_Crouch_Transition", "action", 0.0, 1.15),
    "crouch_to_stand": ("Crouch_To_Standing_Idle", "action", 0.0, 1.2),
    # reactions
    "hit_light": ("Hit_To_Body_3", "action", 3.0, 1.15),
    "hit_heavy": ("Big_Hit_To_Head", "action", 3.0, 1.15),
    "knocked_down": ("Knocked_Down", "action", 0.0, 1.15),
    "get_up": ("Getting_Up", "action", 0.0, 1.15),
}


def slow(clip, factor):
    """Giant timing: the same poses over a longer duration (stride unchanged)."""
    if abs(factor - 1.0) > 1e-6:
        clip["duration"] *= factor
    return clip


class LoopPadded:
    """A closed-cycle take with its last frames (moved back by one cycle of
    hip travel) prepended, so cycle_clip finds the frames before the cycle
    start that it blends the seam with."""

    def __init__(self, take, pad):
        self.pad = pad
        n = take.frames
        hips = take.pos("Hips")
        shift = hips[n - 1] - hips[0]
        shift[1] = 0.0
        self.frames = n + pad
        self.rate = take.rate
        self._pos = {k: np.concatenate([take.pos(k)[n - 1 - pad:n - 1] - shift, take.pos(k)]) for k in take.names}
        self._rot = {k: np.concatenate([take.rot(k)[n - 1 - pad:n - 1], take.rot(k)]) for k in take.names}

    def pos(self, name):
        return self._pos[name]

    def rot(self, name):
        return self._rot[name]


def build(rt, take, kind, lean, scale, pad=6):
    n = take.frames
    if kind == "loop":
        take = LoopPadded(take, pad)
        src = Source(take, "mixamo", travel=(pad, pad + n - 1))
    else:
        src = Source(take, "mixamo", align_frame=0)
    res = rt.run(src, None)
    if kind == "loop":
        clip = cycle_clip(res, src, pad, pad + n - 1)
        moving = clip["stride"] > 0.15
        clip = retune_trunk(clip, lean=lean, damping=0.6 if moving else 0.0) if lean else clip
        if not moving:
            clip["stride"] = 0.0
    else:
        clip = action_clip(res, src, 0, n - 1, lean=lean)
    return slow(clip, scale)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True)
    ap.add_argument("--mixamo", required=True)
    ap.add_argument("--variants", default="1")
    ap.add_argument("--only", default="", help="comma-separated slot names")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    slots = {k: v for k, v in SLOTS.items() if not a.only or k in a.only.split(",")}
    pack = {"format": "seele-motion-pack", "version": 1, "variants": {},
            "provenance": {"source": "Mixamo (Adobe Mixamo terms; private, not redistributed)",
                           "method": "landmark + rotation-delta retarget, two-bone leg IK, EVA posture/timing",
                           "tool": "tools/motion3/moveset_v2.py"}}
    takes = {}
    for variant in (int(v) for v in a.variants.split(",")):
        rig = Rig.from_body_profile(a.body, variant)
        rt = Retargeter(rig)
        clips = {}
        for slot, (name, kind, lean, scale) in slots.items():
            if name not in takes:
                takes[name] = Baked(os.path.join(a.mixamo, name + ".npz"))
            try:
                clip = build(rt, takes[name], kind, lean, scale)
            except Exception as exc:  # report and keep building the other slots
                print("FAIL", slot, name, exc)
                continue
            clips[slot] = encode(clip)
            print(variant, slot, name, kind, "frames", clip["frames"], "dur", round(clip["duration"], 2),
                  "stride", round(clip["stride"], 2))
        pack["variants"][str(variant)] = {"clips": clips}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(pack, f, separators=(",", ":"))
    print("wrote", a.out, os.path.getsize(a.out) // 1024, "KiB")


if __name__ == "__main__":
    main()
