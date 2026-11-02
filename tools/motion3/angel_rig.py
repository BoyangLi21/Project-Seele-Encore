"""Retarget human captures onto an Angel geo rig (Sachiel's 17-bone humanoid).

The EVA retargeter expects clavicle, wrist and ankle joints.  The Angel rig
lacks them, so it is extended with virtual joints placed on the real bone
lines (clavicle just inboard of the shoulder, wrist at the hand pivot, ankle
at the foot pivot), retargeted, and folded back: each real bone's local
rotation is recomputed against its real parent from the world rotations.
"""

import json

import numpy as np

from evarig import Rig, px_to_model
from retarget import Retargeter

ANGEL_BONES = ("root", "torso_lower", "torso_upper", "neck", "head",
               "arm_l", "forearm_l", "hand_l", "leg_l", "shin_l", "foot_l",
               "arm_r", "forearm_r", "hand_r", "leg_r", "shin_r", "foot_r")


def load_geo(path):
    with open(path, encoding="utf-8") as f:
        geo = json.load(f)["minecraft:geometry"][0]
    return [{"name": b["name"], "parent": b.get("parent"), "pivot": b["pivot"],
             "rotation": b.get("rotation")} for b in geo["bones"]]


def extended(bones):
    by = {b["name"]: dict(b) for b in bones}
    out = [dict(b) for b in bones]
    for s in ("l", "r"):
        arm = by["arm_" + s]["pivot"]
        out.append({"name": "clavicle_" + s, "parent": "torso_upper",
                    "pivot": [arm[0] * 0.55, arm[1] - 2.0, arm[2]]})
        out.append({"name": "wrist_" + s, "parent": "forearm_" + s, "pivot": list(by["hand_" + s]["pivot"])})
        out.append({"name": "ankle_" + s, "parent": "shin_" + s, "pivot": list(by["foot_" + s]["pivot"])})
    for b in out:
        if b["name"].startswith("arm_"):
            b["parent"] = "clavicle_" + b["name"][-1]
        elif b["name"].startswith("hand_"):
            b["parent"] = "wrist_" + b["name"][-1]
        elif b["name"].startswith("foot_"):
            b["parent"] = "ankle_" + b["name"][-1]
    return out


class AngelRetargeter:
    def __init__(self, geo_path):
        self.bones = load_geo(geo_path)
        self.rig = Rig(self.bones)
        self.ext = Rig(extended(self.bones))
        self.rt = Retargeter(self.ext)

    def run(self, src):
        res = self.rt.run(src, None)
        wr, _ = self.ext.fk(res["local"])
        local = {}
        for name in self.rig.names:
            p = self.rig.parent[name]
            local[name] = wr[name] if p is None else np.einsum("nji,njk->nik", wr[p], wr[name])
        res["local"] = local
        return res

    def height(self):
        return float(self.rig.pivot["head"][1])


def pivot_model(px):
    return px_to_model(px)
