"""Side-by-side joint bends for several Unit-01 meshes: python skin_compare.py out.png mesh1 mesh2 ..."""
import math
import sys

import numpy as np

import rig as R
import scene as S

D = math.radians
POSES = [
    ('elbow 120', {'forearm_l': R.qx(D(120)), 'forearm_r': R.qx(D(120))}, 39, (30, 6, -24)),
    ('knee 120', {'shin_l': R.qx(D(-120)), 'shin_r': R.qx(D(-120))}, 23, (30, 6, -22)),
    ('hip 100 knee 110', {'leg_l': R.qx(D(100)), 'shin_l': R.qx(D(-110))}, 30, (34, 8, 26)),
    ('arm raised 150', {'arm_l': R.qx(D(150)), 'arm_r': R.qx(D(150))}, 50, (26, 8, 30)),
    ('arm side 90', {'arm_l': R.qz(D(-90))}, 47, (0, 8, 40)),
    ('waist bend 40', {'torso_upper': R.qx(D(-40))}, 40, (34, 6, 16)),
]


def main():
    out, paths = sys.argv[1], sys.argv[2:]
    a = S.Actors()
    tex = S.PRIVATE + '/textures/entity/eva_unit01.png'
    meshes = [R.RigidMesh(p, tex, a.eva_rig) for p in paths]
    imgs = []
    for name, rot, y, eye in POSES:
        for k, mesh in enumerate(meshes):
            mats = a.eva_mats(rot, {}, R.entity_matrix([0, 0, 0], 0, S.SCALE))
            g = [mesh.triangles(mats, np.eye(4))]
            cam = R.Camera(np.array([eye[0], y + eye[1], eye[2]], float), np.array([0, y, 2.0]), 46, (340, 300))
            imgs.append(R.render(cam, g, label='%s  [%d]' % (name, k), ground=(-30, 30, -30, 30)))
    R.sheet(imgs, len(meshes) * 2).save(out)


if __name__ == '__main__':
    main()
