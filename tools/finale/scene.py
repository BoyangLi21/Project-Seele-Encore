"""Load the private actor assets and pose them from a first_battle clip.

Paths come from SEELE_PRIVATE (default: the motion-work private runtime pack).
"""
import json
import math
import os

import numpy as np

import rig as R

PRIVATE = os.environ.get('SEELE_PRIVATE',
                         'F:/eva/.claude/motion-work/runtime_private/assets/projectseele')
SCALE = 5.0
KNEE_LIFT = 11.4 / 16


def elbow_centre(side):
    return np.array([-23.489652 if side == 'l' else 23.489652, 123.435069, 7.737214]) / 16


class Actors:
    def __init__(self):
        self.eva_rig = R.Rig(PRIVATE + '/geo/eva_unit01.geo.json')
        self.eva_mesh = R.RigidMesh(PRIVATE + '/mesh/eva_unit01.mesh.json',
                                    PRIVATE + '/textures/entity/eva_unit01.png', self.eva_rig)
        self.angel_rig = R.Rig(PRIVATE + '/geo/sachiel.geo.json')
        self.angel_mesh = R.SkinnedMesh(PRIVATE + '/mesh/sachiel.mesh.json',
                                        PRIVATE + '/textures/entity/sachiel.png', self.angel_rig)

    def eva_mats(self, rot, pos, world):
        """Apply the game's knee/elbow hinge (FirstBattlePoseRenderer) then FK."""
        pos = dict(pos)
        rig = self.eva_rig
        for s in 'lr':
            q = rot.get('shin_' + s, rig.rest['shin_' + s])
            pos['shin_' + s] = R.Rig.hinge_offset(q, rig.pivot['shin_' + s],
                                                  rig.pivot['shin_' + s] + np.array([0, KNEE_LIFT, 0]))
            q = rot.get('forearm_' + s, rig.rest['forearm_' + s])
            pos['forearm_' + s] = R.Rig.hinge_offset(q, rig.pivot['forearm_' + s], elbow_centre(s))
        return rig.fk(rot, pos, world)


class Clip:
    """Reader for first_battle_*.json (fps 30/60, 460 ticks)."""

    def __init__(self, path):
        self.data = json.load(open(path, encoding='utf8'))
        self.fps = self.data['fps']
        self.count = len(self.data['camera']['fov'])

    def frame(self, seconds):
        f = min(max(seconds * self.fps, 0), self.count - 1)
        a = int(f)
        return a, min(a + 1, self.count - 1), f - a

    def pose(self, role, seconds):
        r = self.data[role]
        a, b, t = self.frame(seconds)
        rot, pos = {}, {}
        for i, name in enumerate(r['bones']):
            qa = R.clip_to_baked(r['frames'][a]['rotation_wxyz'][i])
            qb = R.clip_to_baked(r['frames'][b]['rotation_wxyz'][i])
            rot[name] = R.qslerp(qa, qb, t)
            if name == 'root':
                pa = np.array(r['frames'][a]['root_m']) * 112
                pb = np.array(r['frames'][b]['root_m']) * 112
            else:
                off = r['frames'][a].get('bone_position_xyz') or {}
                offb = r['frames'][b].get('bone_position_xyz') or {}
                pa = np.array(off.get(name, [0, 0, 0]), float)
                pb = np.array(offb.get(name, [0, 0, 0]), float)
            p = pa + (pb - pa) * t
            pos[name] = np.array([-p[0], p[1], p[2]]) / 16
        return rot, pos

    def curve(self, role, name, seconds):
        rows = self.data[role][name]
        a, b, t = self.frame(seconds)
        return np.array(rows[a]) + (np.array(rows[b]) - np.array(rows[a])) * t

    def camera(self, seconds):
        c = self.data['camera']
        a, b, t = self.frame(seconds)
        lerp = lambda k: np.array(c[k][a]) + (np.array(c[k][b]) - np.array(c[k][a])) * t
        return lerp('position'), lerp('target'), c['fov'][a] + (c['fov'][b] - c['fov'][a]) * t


def clip_scene(actors, clip, seconds):
    """World triangles of both actors at a clip time (stage frame, spec yaw 0)."""
    rot, pos = clip.pose('eva', seconds)
    world_e = R.entity_matrix(clip.curve('eva', 'root_blocks', seconds), 0, SCALE)
    mats_e = actors.eva_mats(rot, pos, world_e)
    rot, pos = clip.pose('angel', seconds)
    world_a = R.entity_matrix(clip.curve('angel', 'root_blocks', seconds), 180, SCALE)
    mats_a = actors.angel_rig.fk(rot, pos, world_a)
    return [actors.eva_mesh.triangles(mats_e, np.eye(4)),
            actors.angel_mesh.triangles(mats_a, np.eye(4))], mats_e, mats_a
