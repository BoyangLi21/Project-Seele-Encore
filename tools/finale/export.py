"""Write the authored execution as a first_battle clip.

python export.py out.json
"""
import json
import math
import sys

import numpy as np

import body as B
import chor
import film as F
import rig as R
import scene as S

FPS = 30
DURATION_TICKS = 460
COUNT = round(DURATION_TICKS / 20 * FPS) + 1

EVA_EXTRA = ['pylon_l', 'pylon_r', 'knife', 'cannon', 'lance', 'n2', 'entry_plug', 'plug_hatch_l',
             'plug_hatch_r', 'horn']
EVA_BONES = ['root', 'torso_lower', 'torso_upper', 'aim_pitch', 'clavicle_l', 'arm_l', 'forearm_l', 'wrist_l',
             'hand_l', 'clavicle_r', 'arm_r', 'forearm_r', 'wrist_r', 'hand_r', 'neck', 'head', 'r37_jaw',
             'leg_l', 'shin_l', 'ankle_l', 'foot_l', 'leg_r', 'shin_r', 'ankle_r', 'foot_r'] + EVA_EXTRA
ANGEL_BONES = ['root', 'torso_lower', 'torso_upper', 'neck', 'head', 'arm_l', 'forearm_l', 'hand_l', 'leg_l',
               'shin_l', 'foot_l', 'arm_r', 'forearm_r', 'hand_r', 'leg_r', 'shin_r', 'foot_r']

DORSAL_CENTRE = np.array([0.0, 170.616127, 15.217754]) / 16
DORSAL_OUT = np.array([0.0, 0.90587519, 0.42354474])
DORSAL_UP = np.array([0.0, 0.42354474, -0.90587519])
EVA_EYE = np.array([0.0, 171.0, -15.0]) / 16
ANGEL_EYE = np.array([0.0, 166.0, -22.0]) / 16

# original tick -> authored tick (FirstBattleClip.eventTick)
EVENT_REMAP = {19: 40, 28: 40, 122: 115}
LANDING_TICK = 234

# finger preset timeline per hand (EvaAnatomicalHandsR45 preset names)
HAND_PRESETS = {
    'l': [(0.0, 'relaxed'), (0.55, 'fist'), (1.62, 'spread'), (2.0, 'grab'), (4.9, 'spread'), (5.3, 'fist'),
          (6.6, 'spread'), (7.95, 'grab'), (9.15, 'spread'), (10.5, 'fist'), (16.35, 'spread'),
          (18.6, 'grab'), (19.4, 'spread'), (20.6, 'relaxed')],
    'r': [(0.0, 'relaxed'), (0.55, 'fist'), (1.62, 'spread'), (2.0, 'grab'), (4.9, 'spread'), (5.3, 'fist'),
          (6.6, 'spread'), (7.95, 'grab'), (9.15, 'spread'), (10.5, 'fist'), (16.35, 'spread'),
          (18.6, 'grab'), (19.4, 'spread'), (20.6, 'relaxed')],
}


def gecko_pos(t):
    """Baked translation (model blocks) -> GeckoLib position fields (px)."""
    return [-t[0] * 16, t[1] * 16, t[2] * 16]


def rounded(v, n=5):
    return [round(float(x), n) for x in v]


def entity_root(hip):
    return np.array([hip[0], 0.0, hip[2]])


def main():
    out = sys.argv[1]
    actors = S.Actors()
    sc = chor.Scene(actors)
    film = F.Film()
    eva_rest = {n: actors.eva_rig.rest[n] for n in EVA_BONES}
    roles = {'eva': {'bones': EVA_BONES, 'frames': [], 'curves': {}},
             'angel': {'bones': ANGEL_BONES, 'frames': [], 'curves': {}}}
    for k in ('root_blocks', 'eye_blocks', 'look_blocks', 'socket_blocks', 'socket_outward_blocks', 'socket_up_blocks',
              'hand_l_blocks', 'hand_r_blocks', 'foot_l_blocks', 'foot_r_blocks'):
        roles['eva']['curves'][k] = []
    for k in ('root_blocks', 'eye_blocks', 'hand_l_blocks', 'hand_r_blocks', 'core_blocks', 'waist_blocks'):
        roles['angel']['curves'][k] = []
    cam = {'position': [], 'target': [], 'fov': []}
    worst = {}
    for i in range(COUNT):
        t = i / FPS
        s = sc.solve(t)
        for role, yaw, bones in (('eva', 0.0, EVA_BONES), ('angel', 180.0, ANGEL_BONES)):
            rot, pos, mats, info, ctl = s[role]
            for k, v in info.items():
                if 'err' in k:
                    key = role + '.' + k
                    if v > worst.get(key, (0.0, 0.0))[0]:
                        worst[key] = (v, t)
            hip = np.asarray(ctl['hip'], float)
            ent = entity_root(hip)
            ra = R.qy(math.radians(180 - yaw))
            shift = R.qmat(R.qconj(ra)) @ ent / B.SCALE
            frame = {'root_m': None, 'rotation_wxyz': [], 'bone_position_xyz': {}}
            for n in bones:
                q = rot.get(n)
                if q is None:
                    q = eva_rest[n] if role == 'eva' else np.array([1.0, 0, 0, 0])
                frame['rotation_wxyz'].append(rounded(R.baked_to_clip(R.qnorm(q)), 6))
                if n == 'root':
                    frame['root_m'] = rounded(np.array(gecko_pos(pos['root'] - shift)) / 112, 6)
                elif n in pos:
                    frame['bone_position_xyz'][n] = rounded(gecko_pos(pos[n]), 4)
            roles[role]['frames'].append(frame)
            c = roles[role]['curves']
            c['root_blocks'].append(rounded(ent, 4))
            if role == 'eva':
                eye = B.point(mats['head'], EVA_EYE)
                fwd = mats['head'][:3, :3] @ np.array([0, 0, -1.0])
                c['eye_blocks'].append(rounded(eye, 4))
                c['look_blocks'].append(rounded(eye + 40 * fwd / np.linalg.norm(fwd), 4))
                sock = B.point(mats['torso_upper'], DORSAL_CENTRE)
                rr = mats['torso_upper'][:3, :3] / np.linalg.norm(mats['torso_upper'][:3, 0])
                c['socket_blocks'].append(rounded(sock, 4))
                c['socket_outward_blocks'].append(rounded(sock + 2 * rr @ DORSAL_OUT, 4))
                c['socket_up_blocks'].append(rounded(sock + 2 * rr @ DORSAL_UP, 4))
                for side in 'lr':
                    c['hand_%s_blocks' % side].append(rounded(B.point(mats['hand_' + side], actors.eva_rig.pivot['hand_' + side] + np.array([0, -4.5, 0]) / 16), 4))
                    c['foot_%s_blocks' % side].append(rounded(B.point(mats['foot_' + side], sc.eva_body.sole[side]['mid']), 4))
            else:
                c['eye_blocks'].append(rounded(B.point(mats['head'], ANGEL_EYE), 4))
                for side in 'lr':
                    c['hand_%s_blocks' % side].append(rounded(B.point(mats['hand_' + side], actors.angel_rig.pivot['hand_' + side]), 4))
                c['core_blocks'].append(rounded(s['core'], 4))
                c['waist_blocks'].append(rounded(B.point(mats['torso_lower'], actors.angel_rig.pivot['torso_lower']), 4))
        p, g, f = film.sample(t)
        cam['position'].append(rounded(p, 3))
        cam['target'].append(rounded(g, 3))
        cam['fov'].append(round(f, 3))
    data = {'schema': 1, 'fps': FPS, 'duration_ticks': DURATION_TICKS,
            'reference': 'Project SEELE original hand-keyed choreography (tools/finale), MIT. No capture data.',
            'dorsal_profile_version': 13, 'landing_tick': LANDING_TICK,
            'event_tick_remap_r42': {str(k): v for k, v in EVENT_REMAP.items()},
            'hand_presets_r59': {k: [[a, b] for a, b in v] for k, v in HAND_PRESETS.items()},
            'camera': dict(cam, cuts=film.cut_frames(FPS))}
    for role in ('eva', 'angel'):
        r = roles[role]
        data[role] = dict({'bones': r['bones'], 'frames': r['frames']}, **r['curves'])
    with open(out, 'w', encoding='utf8') as fh:
        json.dump(data, fh, separators=(',', ':'))
    print('wrote', out, COUNT, 'frames')
    for k, (v, t) in sorted(worst.items()):
        if v > 0.05:
            print('  reach miss %-18s %.2f blocks at %.2f s' % (k, v, t))


if __name__ == '__main__':
    main()
