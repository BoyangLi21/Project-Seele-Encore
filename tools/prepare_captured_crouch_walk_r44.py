"""Preserve a real crouched walking capture and its own standing calibration.

Only exact source names are aliased. Hierarchy, offsets, world FK and timing
remain those of 100STYLE; no ACCAD skeleton or synthetic crouch is substituted.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from scipy.spatial.transform import Rotation
from bvh_motion_r12 import load_bvh

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'external-assets/incoming/mocap/100style-eva-allowlist-r01/third_party_raw'


def canonical(data):
    mapping = {'Chest4': 'Spine1'}
    for side in ('Left', 'Right'):
        mapping.update({side+a: side+b for a, b in (
            ('Shoulder', 'Arm'), ('Elbow', 'ForeArm'), ('Wrist', 'Hand'),
            ('Wrist_End', 'Hand_End'), ('Hip', 'UpLeg'), ('Knee', 'Leg'),
            ('Ankle', 'Foot'), ('Toe', 'ToeBase'), ('Toe_End', 'ToeBase_End'))})
    result = dict(data)
    result['names'] = [mapping.get(n, n) for n in data['names']]
    if len(set(result['names'])) != len(result['names']):
        raise ValueError('Source alias collision')
    return result, mapping


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    out = args.out.resolve(); (out / 'source').mkdir(parents=True, exist_ok=True)
    path = SOURCE / 'Crouched_FW.bvh'
    capture, mapping = canonical(load_bvh(path))
    stand, _ = canonical(load_bvh(SOURCE / 'Neutral_ID.bvh'))
    if capture['names'] != stand['names'] or not np.array_equal(capture['parents'], stand['parents']):
        raise ValueError('Crouch and its own standing capture do not share hierarchy')
    offset_error = float(np.max(np.abs(capture['offsets'] - stand['offsets'])))
    if offset_error > 1e-6:
        raise ValueError('Source skeleton offsets differ')
    names = capture['names']; hip = names.index('Hips')
    points = capture['positions']; q = capture['rotations']
    hips = Rotation.from_quat(q[:, hip])
    # Local FK is measured without Blender import or independently interpolated
    # joint positions. Root heading/travel is excluded only for cycle search.
    local_q = np.empty_like(q)
    for i, parent in enumerate(capture['parents']):
        local_q[:, i] = q[:, i] if parent < 0 else (Rotation.from_quat(q[:, parent]).inv() * Rotation.from_quat(q[:, i])).as_quat()
    relative_points = np.stack([hips.inv().apply(points[:, i] - points[:, hip]) for i in range(len(names))], axis=1)
    candidates = []
    # Official Frame_Cuts.csv Crouched FW valid frames 430..6762. Search the
    # first substantial captured stretch, with an even 60Hz sample interval.
    for interval in range(72, 181, 2):
        for first in range(430, 1600, 2):
            last = first + interval
            angles = 2*np.arccos(np.clip(np.abs((local_q[first]*local_q[last]).sum(axis=1)), 0, 1))
            angles[hip] = 0
            position_error = np.linalg.norm(relative_points[first] - relative_points[last], axis=1)
            contact = []
            for endpoint in (first, last):
                contact.append([bool(points[endpoint, names.index(side+'ToeBase_End'), 1] < 5) for side in ('Left', 'Right')])
            if contact[0] != contact[1]:
                continue
            travel = float(np.linalg.norm((points[last, hip] - points[first, hip])[[0, 2]])*.01)
            if travel < .35:
                continue
            score = float(np.mean(angles**2) + np.mean((position_error*.02)**2))
            candidates.append(dict(first=first, last=last, score=score,
                                   maximum_local_joint_seam_degrees=float(np.rad2deg(angles).max()),
                                   maximum_hip_relative_joint_seam_metres=float(position_error.max()*.01),
                                   captured_travel_metres=travel, endpoint_toe_height_contact_estimate=contact))
    if not candidates:
        raise ValueError('No source cycle candidates')
    candidates.sort(key=lambda row: row['score']); selected = candidates[0]
    first, last = selected['first'], selected['last']; count = (last-first)//2 + 1
    for filename, data in (('crouch_walk', capture), ('calibration_stand', stand)):
        if filename == 'calibration_stand':
            data = dict(data, positions=data['positions'][568:569], rotations=data['rotations'][568:569])
        np.savez_compressed(out / 'source' / (filename+'.npz'), **{k:data[k] for k in ('names','parents','positions','rotations','fps','offsets')})
    segment = dict(label='crouch_walk', source_file=str(path), source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   source_frame_range=[first,last], source_fps=capture['fps'], original_window_seconds=(last-first)/capture['fps'],
                   candidate_frames=[1,count], candidate_seconds=(count-1)/30, candidate_pose_interval_seconds=(count-1)/30,
                   source_time_preserved=True, source_semantics='Actual 100STYLE Crouched forward walking capture; no lowered standing gait',
                   source_license='CC BY 4.0', source_url='https://www.ianxmason.com/100style/',
                   timing_quantization='60Hz nominal capture sampled at exact 2-frame increments; stored source 59.9988Hz differs from nominal30Hz by 0.002%')
    card = dict(schema='projectseele.continuous-leg-source.r44', fps=30, frames=count, segments=[segment],
                source_kind='Actual 100STYLE BVH full-body crouched walking capture',
                source_license='100STYLE, Ian Mason, Sebastian Starke and Taku Komura, CC BY 4.0',
                source_url='https://www.ianxmason.com/100style/',
                calibration='Own 100STYLE Neutral_ID source frame568, official valid idle interval; different capture skeleton from ACCAD',
                source_aliases=mapping, source_offset_error_cm=offset_error, source_timing_preserved=True,
                quality='UNREVIEWED source cycle study; source role, fullbody retarget/contact/native art still required')
    fixture = json.loads((ROOT/'artifacts/rebuild_r44/combat/locomotion_sequence_v5_run_seam_study/fixture.json').read_text('utf8'))
    fixture['source_motion_card'] = card; fixture['duration'] = count/30; fixture['quality'] = card['quality']
    (out/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')),'utf8')
    (out/'source_card.json').write_text(json.dumps(card,indent=2),'utf8')
    (out/'source_cycle_selection.json').write_text(json.dumps(dict(selected=selected,first_20=candidates[:20],
        standing_source_sha256=hashlib.sha256((SOURCE/'Neutral_ID.bvh').read_bytes()).hexdigest(),
        actual_calibration_source_frame=568,artistic_acceptance=False),indent=2),'utf8')
    print(json.dumps(dict(selected=selected,frames=count,source_seconds=segment['original_window_seconds'])))


if __name__ == '__main__':
    main()
