"""Private visual study of the TV cage's shallow front beam.

The reference supports the silhouette, not the existing five-stage telescope.
Keep that distinction explicit. This draft is not installable: its receiver
bearing arrangement must be reauthored and checked before production use.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--depth-factor', type=float, default=.55)
    args = parser.parse_args()
    assert .4 <= args.depth_factor <= .8
    assert not args.out.exists()
    data = json.loads(args.base.read_text('utf8'))
    source_hash = hashlib.sha256(args.base.read_bytes()).hexdigest()
    changed = {}
    for side in ('l', 'r'):
        for stage in range(5):
            name = f'front_stage_{stage}_{side}'
            vertices = np.array(data['parts'][name]).reshape(-1, 6)
            original = vertices.copy()
            boxes = np.array(data['collision_parts'][name])
            # Keep the physical top, not the slightly raised decorative cover.
            # All X/Z motion coordinates stay unchanged.
            top = float(boxes[:, 1, 1].max())
            vertices[:, 1] = top + (vertices[:, 1] - top) * args.depth_factor
            old_boxes = boxes.copy()
            boxes[:, :, 1] = top + (boxes[:, :, 1] - top) * args.depth_factor
            assert np.all(boxes[:, 0].min(0) >= old_boxes[:, 0].min(0) - 1e-8)
            assert np.all(boxes[:, 1].max(0) <= old_boxes[:, 1].max(0) + 1e-8)
            data['parts'][name] = vertices.reshape(-1).tolist()
            data['collision_parts'][name] = boxes.tolist()
            low, high = vertices[:, :3].min(0), vertices[:, :3].max(0)
            for component in data['components']:
                if component['part'] != name:
                    continue
                delta = np.array(component['translation_open_local'])
                component['closed_bounds_local'] = [low.tolist(), high.tolist()]
                component['sampled_sweep_bounds_local'] = [
                    np.minimum(low, low + delta).tolist(),
                    np.maximum(high, high + delta).tolist()]
            changed[name] = dict(old_height_m=float(np.ptp(original[:, 1])),
                                 new_height_m=float(np.ptp(vertices[:, 1])),
                                 top_preserved_m=top,
                                 outer_collision_envelope_subset=True,
                                 individual_solids_subset=False)
    data['forebeam_proportion_study_r45'] = dict(
        source_sha256=source_hash, depth_factor=args.depth_factor,
        scope='Visual silhouette study; telescope is an original engineering adaptation',
        install_allowed=False, bearing_support_passed=False,
        native_passed=False, visual_accepted=False)
    args.out.mkdir(parents=True)
    target = args.out / 'tv_shoulder_shells_r44.json'
    target.write_text(json.dumps(data, separators=(',', ':')), encoding='utf8')
    receipt = dict(base_sha256=source_hash,
                   candidate_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                   changed_parts=changed, unchanged='All side personnel decks, guards, doors, shoulder shells, static supports, lower frame, movement clocks and X/Z translations',
                   reference='Privately viewed tv_cage.png; thickness is a proportion study, not a verified TV dimension',
                   remaining=['Receiver roller/bearing load path after shallow-beam revision',
                              'Exact nested-shell collisions; envelope inclusion does not prove solid inclusion',
                              'Matched native front/side views and full motion lifecycle',
                              'Whole platform TV silhouette and immersion relationship'],
                   install_allowed=False, world_write=False, visual_accepted=False)
    (args.out / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'changed_parts'}))


if __name__ == '__main__':
    main()
