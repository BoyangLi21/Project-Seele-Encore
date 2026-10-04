"""Measure arm/hand alignment from final native rendered bone matrices.

This is a longitudinal wrist diagnostic, not an anatomical or art pass.
It does not move geometry or synthesize poses.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--witness', type=Path, required=True)
    p.add_argument('--contract', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    contract = json.loads(args.contract.read_text(encoding='utf8'))
    frames = []
    with args.witness.open(encoding='utf8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['kind'] != 'final_named_palette' or row['actual_owner_inputs'].get('weapon') != 4:
                continue
            bones = {b['name']: b for b in row['bones']}
            model_world = np.array(row['model_to_world_column_major']).reshape(4, 4).T
            def matrix(name):
                return model_world @ np.array(bones[name]['final_model_column_major']).reshape(4, 4).T
            def point(name, pivot=None):
                return (matrix(name) @ np.r_[bones[name]['pivot_model'] if pivot is None else pivot, 1])[:3]
            hands = {}
            for side in ('l', 'r'):
                wrist = point('hand_' + side)
                socket = 'r30_elbow_socket_' + side
                # Actual socket pivot belongs to the forearm's rigid segment.
                pivot = bones[socket]['pivot_model'] if socket in bones else np.array([
                    -23.489652 if side == 'l' else 23.489652, 123.435069, 7.737214]) / 16
                elbow = point('forearm_' + side, pivot)
                shoulder = point('arm_' + side)
                forearm = wrist - elbow
                long = matrix('hand_' + side)[:3, :3] @ contract['hands'][side]['longitudinal_bind']
                cosine = float(np.clip(forearm @ long / (np.linalg.norm(forearm) * np.linalg.norm(long)), -1, 1))
                hands[side] = dict(wrist_bend_deg=float(np.degrees(np.arccos(cosine))),
                    wrist_above_shoulder_blocks=float(wrist[1] - shoulder[1]),
                    elbow_above_shoulder_blocks=float(elbow[1] - shoulder[1]),
                    forearm_length_blocks=float(np.linalg.norm(forearm)))
            frames.append(dict(tick=row['tick'], stance=row['stance'], inputs=row['actual_owner_inputs'], hands=hands))
    assert frames, 'No actual armed final palette'
    selected = {label: min(frames, key=lambda r: (abs(r['stance'] - value), -r['tick']))
                for label, value in [('standing', 0), ('crouch', 1), ('prone', 3)]}
    result = dict(witness_sha256=hashlib.sha256(args.witness.read_bytes()).hexdigest(),
                  contract_sha256=hashlib.sha256(args.contract.read_bytes()).hexdigest(),
                  frames=frames, selected=selected, visual_accepted=False,
                  limitation='Longitudinal wrist bend only; no thumb, twist, skin or sight-line acceptance')
    args.out.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(selected, ensure_ascii=False))


if __name__ == '__main__':
    main()
