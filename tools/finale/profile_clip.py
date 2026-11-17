"""Contact sheet of a clip of the private gameplay profile: python profile_clip.py <clip> out.png f1 f2 ...

The clip by its name in the profile without the r32_ (knife_forward, cross, ...). Each frame gets a side view, a
front view and a view from above, the knife drawn as a line from its grip to its tip where the clip strikes with
one. The profile is the review client's, Unit-01's: rig 1 (rig 0 is Unit-00). SEELE_PROFILE to read another.
"""
import json
import os
import sys

import numpy as np

import rig as R
import scene as S

PROFILE = os.environ.get('SEELE_PROFILE',
                         'F:/eva/.claude/motion-work/review_client/projectseele-local-maps/eva_gameplay_r44_1.json')
# The blade's tip in the knife bone's own space (the profile's contact_point_model of both knife clips).
TIP = np.array([24.469608571428555, 57.01651785714286, -0.12080374999999999]) / 16


def load():
    return json.load(open(PROFILE, encoding='utf8'))


def frame_pose(bones, clip, f):
    """A frame of a profile clip as the rig's rotations and offsets."""
    rot, pos = {}, {}
    fr = clip['frames'][f]
    for i, n in enumerate(bones):
        rot[n] = R.clip_to_baked(fr['rotation_wxyz'][i])
    p = np.array(fr['root_m']) * 112
    pos['root'] = np.array([-p[0], p[1], p[2]]) / 16
    for n, v in (fr.get('bone_position_xyz') or {}).items():
        pos[n] = np.array([-v[0], v[1], v[2]]) / 16
    return rot, pos


def blade(rig, mats):
    """Grip and tip of the knife in the world."""
    m = mats['knife']
    return m[:3, :3] @ rig.pivot['knife'] + m[:3, 3], m[:3, :3] @ TIP + m[:3, 3]


def views(actors, mats, label, size=(300, 300), knife=True):
    groups = [actors.eva_mesh.triangles(mats, np.eye(4))]
    lines = []
    if knife:
        a, b = blade(actors.eva_rig, mats)
        lines = [(a, b, (255, 80, 40))]
    rig = actors.eva_rig
    mid = mats['torso_lower'][:3, :3] @ rig.pivot['torso_lower'] + mats['torso_lower'][:3, 3]
    tall = float((mats['head'][:3, :3] @ rig.pivot['head'] + mats['head'][:3, 3])[1])
    mid[1] = 0
    ground = (-80, 80, -80, 80)
    side = R.Camera(mid + np.array([-2.9 * tall, .7 * tall, 0]), mid + np.array([0, .5 * tall, 0]), 36, size)
    front = R.Camera(mid + np.array([0, .7 * tall, 2.9 * tall]), mid + np.array([0, .5 * tall, 0]), 36, size)
    top = R.Camera(mid + np.array([0, 4.2 * tall, 1]), mid + np.array([0, .5 * tall, 0]), 30, size, up=(0, 0, 1))
    return [R.render(side, groups, label=label + ' side', ground=ground, lines=lines),
            R.render(front, groups, label=label + ' front', ground=ground, lines=lines),
            R.render(top, groups, label=label + ' top', ground=ground, lines=lines)]


def main():
    name, out = sys.argv[1], sys.argv[2]
    data = load()
    clip = data['clips']['r32_' + name]
    frames = [int(x) for x in sys.argv[3:]] or list(range(0, len(clip['frames']), max(1, len(clip['frames']) // 8)))
    actors = S.Actors()
    world = R.entity_matrix([0, 0, 0], 0, S.SCALE)
    images = []
    for f in frames:
        rot, pos = frame_pose(data['bones'], clip, f)
        mats = actors.eva_rig.fk(rot, pos, world)
        images.append(views(actors, mats, '%s %d' % (name, f), knife='knife' in name))
    R.sheet([row[v] for v in range(3) for row in images], len(frames)).save(out)
    print('wrote', out, len(clip['frames']), 'frames, contact', clip.get('contact_phase'), 'duration', clip.get('duration_seconds'))


if __name__ == '__main__':
    main()
