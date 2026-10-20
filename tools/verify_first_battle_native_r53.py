"""Compare the installed native pose submissions with their authored clip.

This checks the runtime writer and final hand ownership, not just an offline
authoring loop. Image review remains separate.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp


def verify(clip_path, witness_path):
    content = clip_path.read_bytes()
    clip = json.loads(content)
    digest = hashlib.sha256(content).hexdigest()
    rows = [json.loads(line) for line in witness_path.read_text(encoding="utf-8").splitlines()]
    if not rows or any(row["clip_sha256"] != digest for row in rows):
        raise ValueError("Native observations do not belong to this exact candidate")
    roles = {}
    errors, hand_changes, sole_gaps = [], [], []
    for row in rows:
        key = "eva" if row["actor"] == "eva" else "angel"
        role = clip[key]
        roles.setdefault(key, []).append(row["scene_seconds"])
        at = min(len(role["frames"])-1, row["scene_seconds"]*clip["fps"])
        a = int(at)
        b = min(a+1, len(role["frames"])-1)
        for name, actual in row["writer_bones"].items():
            if name not in role["bones"]:
                continue
            index = role["bones"].index(name)
            source = []
            for i in (a, b):
                qw, qx, qy, qz = role["frames"][i]["rotation_wxyz"][index]
                source.append([-qx, -qy, qz, qw])
            expected = Slerp([0, 1], R.from_quat(source))([at-a])[0]
            native = R.from_euler("xyz", actual["rot_xyz_radians"])
            errors.append(float((expected.inv()*native).magnitude()*180/np.pi))
            final = row.get("final_at_root_return", {}).get(name)
            if final and name.startswith("r45_hand_"):
                q = R.from_euler("xyz", final["rot_xyz_radians"])
                hand_changes.append(float((native.inv()*q).magnitude()*180/np.pi))
        if key == "eva":
            for name, part in row["submitted_parts"].items():
                if name.startswith("foot_") and part.get("ground_probe_block_hit"):
                    sole_gaps.append(part["actual_sole_gap"])
    if set(roles) != {"eva", "angel"} or max(roles["eva"]) < 22.9 or max(roles["angel"]) < 18:
        raise ValueError("Incomplete paired performance observation")
    if not errors or max(errors) > .05:
        raise ValueError("Native bone rotation differs from authored interpolation")
    if not hand_changes or max(hand_changes) > .001:
        raise ValueError("A later owner overwrote an authored anatomical hand")
    if not sole_gaps or min(sole_gaps) < -.03:
        raise ValueError("Submitted foot geometry penetrates the measured ground")
    return {
        "clip_sha256": digest, "native_rows": len(rows),
        "native_seconds": {k: [min(v), max(v)] for k, v in roles.items()},
        "source_rotation_comparisons": len(errors),
        "max_rotation_error_degrees": max(errors),
        "final_hand_comparisons": len(hand_changes),
        "max_final_hand_overwrite_degrees": max(hand_changes),
        "actual_ground_probes": len(sole_gaps),
        "minimum_submitted_sole_gap_blocks": min(sole_gaps),
        "scope": "Native pose/mesh/ownership verification; appearance needs the accompanying continuous frames",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clip", type=Path, required=True)
    ap.add_argument("--witness", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = verify(args.clip, args.witness)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
