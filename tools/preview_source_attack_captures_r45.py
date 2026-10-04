"""Inspect original Z-up Tuffles BVH performances before retargeting.

Root-relative silhouettes retain vertical travel. They are source reference
only, never evidence that an EVA rig or its game controls are acceptable.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from bvh_motion_r12 import load_bvh


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--provider', choices=('tuffles', 'eyes-japan'), default='tuffles')
    p.add_argument('--clips', nargs='+', help='Exact existing source stems to inspect')
    a = p.parse_args()
    assert not a.out.exists()
    clips = ['ArmsSinglePunch', 'ArmsPunch1', 'ArmsLariat',
             'ArmsGrappleKnockdown', 'ArmsSlapUpwards', 'ArmsCloseRangePunch']
    if a.provider == 'eyes-japan':
        clips = ['karate-09-punch strong-yokoyama', 'karate-10-punch-yokoyama',
                 'karate-12-double punch-yokoyama', 'fighting-33-parm punch-yokoyama']
    if a.clips:
        clips = a.clips
    names = {'Hip', 'LowerSpine', 'MiddleSpine', 'Chest', 'Neck', 'Head', 'Head_End'}
    names |= {side+part for side in ('L', 'R')
              for part in ('Clavicle', 'Shoulder', 'Forearm', 'Hand', 'Thigh', 'Shin', 'Foot', 'Toe', 'Toe_End')}
    fig = plt.figure(figsize=(24, 15))
    reports = []
    for row, name in enumerate(clips):
        source = a.source / (name+'.bvh')
        d = load_bvh(source)
        positions = d['positions'].copy()
        start, end = 0, len(positions)
        if a.provider == 'eyes-japan':
            hip, head, left, right = (d['names'].index(n) for n in ('Hips', 'Head_End', 'LeftFoot', 'RightFoot'))
            hands = [d['names'].index(n) for n in ('LeftHand', 'RightHand')]
            relative = positions[:, hands] - positions[:, hip:hip+1]
            speed = np.linalg.norm(np.diff(relative, axis=0), axis=2).max(axis=1)
            speed[:30] = 0
            speed[-30:] = 0
            peak = int(np.argmax(speed))+1
            start, end = max(0, peak-14), min(len(positions), peak+23)
            positions = positions[start:end, :, [0, 2, 1]]
            positions[:, :, 1] *= -1
        else:
            hip, head, left, right = (d['names'].index(n) for n in ('Hip', 'Head_End', 'LFoot', 'RFoot'))
        height = positions[0, head, 2] - min(positions[0, left, 2], positions[0, right, 2])
        assert height > 80, 'Unexpected source units or up axis'
        travel = positions[:, hip, :2].copy()
        positions[:, :, :2] -= positions[:, hip:hip+1, :2]
        positions[:, :, 2] -= positions[:, :, 2].min()
        positions /= height
        indices = np.linspace(0, len(positions)-1, 8).astype(int)
        reports.append(dict(source=str(source.resolve()), sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                            frames=len(positions), fps=d['fps'], sampled=(indices+start).tolist(),
                            source_window=[start, end], window_selection='peak hand speed, not asserted impact time' if a.provider == 'eyes-japan' else 'full source',
                            source_up='Y' if a.provider == 'eyes-japan' else 'Z', root_horizontal_travel_source_units=(travel-travel[0]).tolist()))
        for col, index in enumerate(indices):
            ax = fig.add_subplot(len(clips), 8, row*8+col+1, projection='3d')
            ax.view_init(elev=12, azim=-56)
            ax.set_proj_type('ortho')
            for j, bone in enumerate(d['names']):
                parent = d['parents'][j]
                if (a.provider == 'tuffles' and bone not in names) or parent < 0:
                    continue
                first, last = positions[index, parent], positions[index, j]
                color = '#2376b8' if bone.startswith('L') else '#cf6a24' if bone.startswith('R') else '#41494f'
                ax.plot(*zip(first, last), color=color, lw=3)
            ax.set_xlim(-.7, .7)
            ax.set_ylim(-.8, .8)
            ax.set_zlim(0, 1.25)
            ax.set_box_aspect((1, 1, 1))
            ax.set_axis_off()
            ax.set_title(f'{name if col == 0 else ""}\n{(index+start)/d["fps"]:.2f}s', fontsize=10)
    fig.suptitle('SOURCE MOTION ONLY — Z-up / root-relative / no EVA retarget or acceptance', fontsize=18)
    fig.subplots_adjust(wspace=0, hspace=.15)
    a.out.mkdir(parents=True)
    fig.savefig(a.out/'comparison.png', dpi=110, bbox_inches='tight')
    plt.close(fig)
    (a.out/'sources.json').write_text(json.dumps(dict(sources=reports, source_only=True, accepted=False), indent=2), 'utf8')


if __name__ == '__main__':
    main()
