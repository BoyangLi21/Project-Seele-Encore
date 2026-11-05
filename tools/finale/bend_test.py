"""Rig audit: bend each joint through its range and look for breaks at the seams.

python bend_test.py out.png
Baked-space signs (model faces -Z): hip/shoulder/elbow flexion +X,
knee flexion -X, ankle dorsiflexion +X.
"""
import math
import sys

import numpy as np

import rig as R
import scene as S

D = math.radians


def pose_set():
    cases = []
    cases.append(('rest', {}))
    cases.append(('knee 60', {'shin_l': R.qx(D(-60)), 'shin_r': R.qx(D(-60))}))
    cases.append(('knee 110', {'shin_l': R.qx(D(-110)), 'shin_r': R.qx(D(-110))}))
    cases.append(('hip 90 knee 90', {'leg_l': R.qx(D(90)), 'shin_l': R.qx(D(-90)),
                                     'leg_r': R.qx(D(-20)), 'shin_r': R.qx(D(-30))}))
    cases.append(('elbow 90', {'forearm_l': R.qx(D(90)), 'forearm_r': R.qx(D(90))}))
    cases.append(('elbow 135', {'forearm_l': R.qx(D(135)), 'forearm_r': R.qx(D(135))}))
    cases.append(('arms overhead', {'arm_l': R.qx(D(170)), 'arm_r': R.qx(D(170)),
                                    'forearm_l': R.qx(D(30)), 'forearm_r': R.qx(D(30))}))
    cases.append(('ankle +25/-35', {'ankle_l': R.qx(D(25)), 'ankle_r': R.qx(D(-35))}))
    cases.append(('arm abduct 80', {'arm_l': R.qz(D(-80)), 'arm_r': R.qz(D(80))}))
    return cases


def main():
    out = sys.argv[1]
    a = S.Actors()
    images = []
    for name, rot in pose_set():
        world = R.entity_matrix([0, 0, 0], 0, S.SCALE)
        mats = a.eva_mats(rot, {}, world)
        groups = [a.eva_mesh.triangles(mats, np.eye(4))]
        side = R.Camera([-70, 35, 0], [0, 30, 0], 45, (300, 380))
        front = R.Camera([0, 35, 70], [0, 30, 0], 45, (300, 380))
        images.append(R.render(side, groups, label=name + ' side', ground=(-40, 40, -40, 40)))
        images.append(R.render(front, groups, label=name + ' front', ground=(-40, 40, -40, 40)))
    R.sheet(images, 6).save(out)
    print('wrote', out)


if __name__ == '__main__':
    main()
