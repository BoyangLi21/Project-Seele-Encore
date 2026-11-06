"""Print hip height and sole clearance tick by tick: python hipcurve.py capture t0 t1"""
import sys

import numpy as np

import body as B
import replay as RP
import scene as S


def main():
    A = S.Actors()
    rows = RP.load(sys.argv[1] + '/poses.jsonl')
    rows.sort(key=lambda r: r['tick'])
    t0, t1 = int(sys.argv[2]), int(sys.argv[3])
    g = min(r['drawnPosition'][1] for r in rows)
    pv = A.eva_rig.pivot
    hips = []
    for r in rows:
        if not t0 <= r['tick'] <= t1:
            continue
        m = RP.pose(A, r)
        hip = (B.point(m['leg_l'], pv['leg_l']) + B.point(m['leg_r'], pv['leg_r'])) / 2
        sole = []
        for s in 'lr':
            v = np.concatenate([t.reshape(-1, 3) @ m[b][:3, :3].T + m[b][:3, 3] for b, t, _ in A.eva_mesh.parts if b == 'foot_' + s])
            sole.append(v[:, 1].min() - g)
        hips.append(hip[1] - r['drawnPosition'][1])
        print('%4d hip %6.2f  soles %6.2f %6.2f  %s' % (r['tick'], hips[-1], sole[0], sole[1], '*' * int(max(0, (hips[-1] - 30) * 4))))
    print('max tick-to-tick hip change %.2f' % np.abs(np.diff(hips)).max())


if __name__ == '__main__':
    main()
