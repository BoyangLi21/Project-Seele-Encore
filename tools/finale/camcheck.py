"""How close the first battle's camera comes to the two bodies, frame by frame.

python camcheck.py [clip.json] [--near 3.0] [--straight]

The game plays the clip's camera as authored, except at both ends (client/FirstBattleClient.camera):
  entry  the first 1.2 s run from where the player's camera was to the first shot; over the same 1.2 s the
         Angel is carried from where it really stood (14 to 46 blocks ahead) to where the clip has it (52 ahead)
  exit   from 21.6 s the camera runs from the last shot back to the player's camera
Both blends keep clear of the two bodies' upright axes (clearOf); a first-person view, and a camera that starts
inside the Angel, are cut from and to instead. --straight plays plain straight lines, as they were before.

Both ends are played here for a first-person camera, a third-person camera and one on the far side of the
Angel, the entry for four starting distances. For every frame the distance from the camera to the nearest
point of each body's surface is taken, and whether the camera is inside the body (rays from the camera cross
its surface an odd number of times). A camera inside a body, or nearer to it than --near blocks (default 3),
shows the inside of the model.
"""
import sys

import numpy as np

import scene as S

ENTRY, RETURN, END, ANGEL_GONE = 1.2, 21.6, 23.0, 18.65
CLIP_ANGEL_Z = 52.0
CHASE = 46.4          # vanilla's four blocks behind the eye, stretched 11.6 times for a unit this size
ANGEL_CLEAR, EVA_CLEAR, ANGEL_CORE = 24.0, 20.0, 12.0     # FirstBattleClient


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * x * (10 + x * (-15 + 6 * x))


def nearest(camera, triangles):
    """Distance from a point to a triangle soup (Ericson, Real-Time Collision Detection 5.1.5)."""
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    ab, ac, ap = b - a, c - a, camera - a
    d1, d2 = (ab * ap).sum(1), (ac * ap).sum(1)
    bp = camera - b
    d3, d4 = (ab * bp).sum(1), (ac * bp).sum(1)
    cp = camera - c
    d5, d6 = (ab * cp).sum(1), (ac * cp).sum(1)
    vc, vb, va = d1 * d4 - d3 * d2, d5 * d2 - d1 * d6, d3 * d6 - d5 * d4
    with np.errstate(divide='ignore', invalid='ignore'):
        denom = va + vb + vc
        v, w = np.where(denom != 0, vb / denom, 0), np.where(denom != 0, vc / denom, 0)
        point = a + ab * v[:, None] + ac * w[:, None]
        edge = lambda s, e, t: s + (e - s) * np.clip(np.nan_to_num(t), 0, 1)[:, None]   # 0/0: a triangle with no area
        point = np.where(((va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0))[:, None],
                         edge(b, c, (d4 - d3) / ((d4 - d3) + (d5 - d6))), point)
        point = np.where(((vb <= 0) & (d2 >= 0) & (d6 <= 0))[:, None], edge(a, c, d2 / (d2 - d6)), point)
        point = np.where(((vc <= 0) & (d1 >= 0) & (d3 <= 0))[:, None], edge(a, b, d1 / (d1 - d3)), point)
    point = np.where(((d6 >= 0) & (d5 <= d6))[:, None], c, point)
    point = np.where(((d3 >= 0) & (d4 <= d3))[:, None], b, point)
    point = np.where(((d1 <= 0) & (d2 <= 0))[:, None], a, point)
    return float(np.sqrt(((point - camera) ** 2).sum(1).min()))


RAYS = [np.array(r) / np.linalg.norm(r) for r in ((1, .13, .07), (-.09, 1, .21), (.17, -.11, 1), (-1, .31, -.23), (.23, .19, -1))]


def inside(camera, triangles):
    """Most of five rays from the point cross the surface an odd number of times (Moller-Trumbore)."""
    a = triangles[:, 0]
    e1, e2 = triangles[:, 1] - a, triangles[:, 2] - a
    s = camera - a
    odd = 0
    for ray in RAYS:
        h = np.cross(ray, e2)
        det = (e1 * h).sum(1)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
        u = (s * h).sum(1) * inv
        q = np.cross(s, e1)
        v = (q * ray).sum(1) * inv
        t = (e2 * q).sum(1) * inv
        odd += int((ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)).sum()) & 1
    return odd >= 3


def spans(times, flags):
    out, start = [], None
    for t, f in zip(times, flags):
        if f and start is None:
            start = t
        if not f and start is not None:
            out.append((start, last)); start = None
        last = t
    if start is not None:
        out.append((start, last))
    return out


def report(name, times, eva, angel, near, eva_in, angel_in):
    eva, angel = np.array(eva), np.array(angel)
    line = '%-34s nearest to the EVA %5.1f at %5.2f s' % (name, eva.min(), times[int(eva.argmin())])
    if np.isfinite(angel).any():
        line += ', to the Angel %5.1f at %5.2f s' % (np.nanmin(angel), times[int(np.nanargmin(angel))])
    print(line)
    for body, d in (('EVA', eva), ('Angel', angel)):
        for a, b in spans(times, [x < near for x in np.nan_to_num(d, nan=1e9)]):
            print('      within %.1f of the %s from %.2f to %.2f s' % (near, body, a, b))
    for body, flags in (('EVA', eva_in), ('Angel', angel_in)):
        for a, b in spans(times, flags):
            print('      INSIDE the %s from %.2f to %.2f s' % (body, a, b))


def carried(t, eased=False):
    """FirstBattleClip.carried: what is left of the way from where Sachiel really stood to the clip's place.
    eased: the smooth start it had before, for comparison."""
    if eased:
        return 1 - smooth(t / ENTRY)
    return max(0.0, 1 - t / ENTRY) ** 3


def on_axis(root, camera):
    return np.array([root[0], min(max(camera[1], root[1] + 10), root[1] + 50), root[2]])


def clear_of(root, camera, radius, toward):
    """FirstBattleClient.clearOf: the camera moved straight away from a body's axis until it is `radius` from it."""
    axis = on_axis(root, camera)
    out = camera - axis
    d = np.linalg.norm(out)
    if d >= radius:
        return camera
    if d < 1e-3:
        out = (toward - axis) * np.array([1, 0, 1])
        d = np.linalg.norm(out)
        if d < 1e-3:
            out, d = np.array([1.0, 0, 0]), 1.0
    return axis + out * (radius / d)


def main():
    args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith('--') and not sys.argv[i - 1].startswith('--')]
    near = float(sys.argv[sys.argv.index('--near') + 1]) if '--near' in sys.argv else 3.0
    straight = '--straight' in sys.argv
    path = args[0] if args else '../../src/main/resources/assets/projectseele/motion/first_battle_r59.json'
    actors, clip = S.Actors(), S.Clip(path)
    step = 1.0 / 30
    print('blends at both ends: %s' % ('straight lines, as before the camera kept clear of the bodies' if straight else 'as the game plays them'))

    def bodies(t, shift=0.0):
        tris, _, _ = S.clip_scene(actors, clip, t)
        angel = tris[1][0] + np.array([0, 0, shift]) if t < ANGEL_GONE else None
        return tris[0][0], angel

    def measure(name, times, camera_at, shift_at=lambda t: 0.0):
        eva, angel, eva_in, angel_in, cams = [], [], [], [], []
        for t in times:
            e, a = bodies(t, shift_at(t))
            c = camera_at(t)
            cams.append(c)
            eva.append(nearest(c, e))
            angel.append(nearest(c, a) if a is not None else float('nan'))
            eva_in.append(inside(c, e))
            angel_in.append(a is not None and inside(c, a))
        report(name, times, eva, angel, near, eva_in, angel_in)
        steps = [float(np.linalg.norm(b - a)) for a, b in zip(cams, cams[1:])]
        if steps:
            print('      largest move in one frame %.1f blocks' % max(steps))

    # the authored shots
    measure('authored shots, 1.2 to 21.6 s', list(np.arange(ENTRY, RETURN, step)), lambda t: clip.camera(t)[0])

    eye0 = clip.curve('eva', 'eye_blocks', 0.0)
    look0 = clip.curve('eva', 'look_blocks', 0.0) - eye0
    look0 = look0 / np.linalg.norm(look0)
    eva_root = lambda t: clip.curve('eva', 'root_blocks', t)
    first = list(np.arange(0.0, ENTRY + 1e-6, step))

    def entry(name, start, distance):
        shift = lambda t: (distance - CLIP_ANGEL_Z) * carried(t, straight)
        angel_root = lambda t: clip.curve('angel', 'root_blocks', t) + np.array([0, 0, shift(t)])
        from_angel = min(ANGEL_CLEAR, np.linalg.norm(start - on_axis(angel_root(0.0), start)))
        from_eva = min(EVA_CLEAR, np.linalg.norm(start - on_axis(eva_root(0.0), start)))
        cut = not straight and (name == 'first person' or from_angel < ANGEL_CORE)

        def camera(t):
            shot = clip.camera(t)[0]
            if cut:
                return shot
            mix = smooth(t / ENTRY)
            p = start + (shot - start) * mix
            if straight:
                return p
            opened = smooth(mix / .5)
            for _ in range(3):
                p = clear_of(angel_root(t), p, from_angel + (ANGEL_CLEAR - from_angel) * opened, start)
                p = clear_of(eva_root(t), p, from_eva + (EVA_CLEAR - from_eva) * opened, start)
            return p
        measure('entry, %s, Angel %2.0f ahead%s' % (name, distance, ' (cut)' if cut else ''), first, camera, shift)

    for distance in (14.0, 22.0, 30.0, 46.0):
        entry('first person', eye0, distance)
        entry('third person', eye0 - look0 * CHASE, distance)
        # a camera that looks back at Unit-01 from beyond Sachiel: the first shot is on the other side of it
        entry('from beyond the Angel', np.array([30.0, 34.0, distance + 34.0]), distance)

    last = clip.camera(RETURN - step)[0]
    back = list(np.arange(RETURN, END, step))
    for view in ('first person', 'third person', 'third person from the front'):
        if view == 'first person' and not straight:
            print("exit, first person                 cut to the pilot's eye (Unit-01's head is not drawn from there)")
            continue
        def ending(t):
            eye = clip.curve('eva', 'eye_blocks', t)
            look = clip.curve('eva', 'look_blocks', t) - eye
            look = look / np.linalg.norm(look)
            home = eye if view == 'first person' else eye - look * CHASE if view == 'third person' else eye + look * CHASE
            mix = smooth((t - RETURN) / 1.4)
            p = last + (home - last) * mix
            if straight:
                return p
            end = min(EVA_CLEAR, np.linalg.norm(home - on_axis(eva_root(t), home)))
            return clear_of(eva_root(t), p, EVA_CLEAR + (end - EVA_CLEAR) * smooth((mix - .5) / .5), last)
        measure('exit, %s' % view, back, ending)


if __name__ == '__main__':
    main()
