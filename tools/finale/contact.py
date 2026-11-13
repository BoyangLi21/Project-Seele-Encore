"""How the two bodies of the first battle touch, frame by frame: python contact.py [clip.json] [--fps 15] [--out rows.tsv]

For every sampled frame of the clip, on the meshes the game draws:
  into    how deep Unit-01's surface is inside Sachiel (blocks: the deepest of its vertices that are inside the
          other body, measured to that body's surface) and which part it is; the same for Sachiel inside Unit-01
  hands   the gap from each of Unit-01's hands to Sachiel's surface and from each of Sachiel's hands to Unit-01's
          (0 or less: the hand touches or is inside)
Then the stretches where a body is more than --deep blocks (default 1.0) inside the other, and for the authored
contacts (the catch of the forearm, each blow on the core, the embrace) how far the hand is from what it holds.

The first 1.2 s are played three times, for a Sachiel that really stood 14, 20 and 27 blocks ahead when the battle
began: the game carries it from there to the clip's 52 blocks over that time (FirstBattleClip.carried).
--entry does only that part; --eased plays it with the smooth start it had before.
"""
import sys

import numpy as np

import chor
import scene as S

ENTRY, ANGEL_GONE, CLIP_ANGEL_Z = 1.2, 18.65, 52.0
AXES = ((0, 2, 1), (1, 2, 0), (0, 1, 2))      # the two coordinates a ray is seen end-on in, and the one it runs along


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * x * (10 + x * (-15 + 6 * x))


def carried(t, eased=False):
    """FirstBattleClip.carried: what is left of the way from where Sachiel really stood to the clip's place.
    eased: the smooth start it had before, for comparison."""
    if eased:
        return 1 - smooth(t / ENTRY)
    return max(0.0, 1 - t / ENTRY) ** 3


def inside(points, tris):
    """For each point, whether rays along the three axes each cross the surface an odd number of times (two of three)."""
    votes = np.zeros(len(points), int)
    for u, v, w in AXES:
        a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
        e1 = np.stack([b[:, u] - a[:, u], b[:, v] - a[:, v]], 1)
        e2 = np.stack([c[:, u] - a[:, u], c[:, v] - a[:, v]], 1)
        den = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
        ok = np.abs(den) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, den, 1.0), 0.0)
        for s in range(0, len(points), 100):
            p = points[s:s + 100]
            du = p[:, u][:, None] - a[:, u][None, :]
            dv = p[:, v][:, None] - a[:, v][None, :]
            k1 = (du * e2[:, 1] - dv * e2[:, 0]) * inv
            k2 = (dv * e1[:, 0] - du * e1[:, 1]) * inv
            hit = ok & (k1 >= 0) & (k2 >= 0) & (k1 + k2 <= 1)
            height = a[:, w] + k1 * (b[:, w] - a[:, w]) + k2 * (c[:, w] - a[:, w])
            votes[s:s + 100] += ((hit & (height > p[:, w][:, None])).sum(1) & 1)
    return votes >= 2


def distance(points, tris):
    """Distance from each point to a triangle soup (Ericson, Real-Time Collision Detection 5.1.5)."""
    out = np.empty(len(points))
    a, b, c = tris[:, 0][None], tris[:, 1][None], tris[:, 2][None]
    ab, ac = b - a, c - a
    for s in range(0, len(points), 16):
        p = points[s:s + 16][:, None, :]
        ap, bp, cp = p - a, p - b, p - c
        d1, d2 = (ab * ap).sum(2), (ac * ap).sum(2)
        d3, d4 = (ab * bp).sum(2), (ac * bp).sum(2)
        d5, d6 = (ab * cp).sum(2), (ac * cp).sum(2)
        vc, vb, va = d1 * d4 - d3 * d2, d5 * d2 - d1 * d6, d3 * d6 - d5 * d4
        with np.errstate(divide='ignore', invalid='ignore'):
            den = va + vb + vc
            v, w = np.where(den != 0, vb / den, 0), np.where(den != 0, vc / den, 0)
            q = a + ab * v[..., None] + ac * w[..., None]
            edge = lambda s0, e0, t: s0 + (e0 - s0) * np.clip(np.nan_to_num(t), 0, 1)[..., None]
            q = np.where(((va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0))[..., None], edge(b, c, (d4 - d3) / ((d4 - d3) + (d5 - d6))), q)
            q = np.where(((vb <= 0) & (d2 >= 0) & (d6 <= 0))[..., None], edge(a, c, d2 / (d2 - d6)), q)
            q = np.where(((vc <= 0) & (d1 >= 0) & (d3 <= 0))[..., None], edge(a, b, d1 / (d1 - d3)), q)
        q = np.where(((d6 >= 0) & (d5 <= d6))[..., None], c, q)
        q = np.where(((d3 >= 0) & (d4 <= d3))[..., None], b, q)
        q = np.where(((d1 <= 0) & (d2 <= 0))[..., None], a, q)
        out[s:s + 16] = np.sqrt(((q - p) ** 2).sum(2).min(1))
    return out


def around(points, tris, reach):
    """The triangles that come within `reach` of the points' box: the only ones a point can be that near to."""
    lo, hi = points.min(0) - reach, points.max(0) + reach
    return tris[np.all((tris.max(1) > lo) & (tris.min(1) < hi), axis=1)]


def deepest(points, labels, tris, lo, hi):
    """(depth, label) of the point of one body deepest inside the other, (0, '') when none is inside."""
    near = np.all((points > lo) & (points < hi), axis=1)
    if not near.any():
        return 0.0, ''
    idx = np.nonzero(near)[0]
    idx = idx[inside(points[idx], tris)]
    if not len(idx):
        return 0.0, ''
    d = distance(points[idx], around(points[idx], tris, 8.0))
    k = int(d.argmax())
    return float(d[k]), labels[idx[k]]


def gap(points, tris):
    """Smallest distance from the points to a surface: 0 when one is inside it, 99 when it is over 12 blocks away."""
    local = around(points, tris, 12.0)
    if not len(local):
        return 99.0
    return 0.0 if inside(points[::4], tris).any() else float(distance(points, local).min())


def spans(rows, key, limit):
    out, cur = [], None
    for r in rows:
        if r[key] > limit:
            cur = [r['t'], r['t'], r[key], r[key + '_part']] if cur is None else [cur[0], r['t'], max(cur[2], r[key]), cur[3] if cur[2] >= r[key] else r[key + '_part']]
        elif cur is not None:
            out.append(cur); cur = None
    if cur is not None:
        out.append(cur)
    return out


def main():
    args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith('--') and not sys.argv[i - 1].startswith('--')]
    opt = lambda name, default: sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default
    fps, deep = float(opt('--fps', 15)), float(opt('--deep', 1.0))
    eased = '--eased' in sys.argv
    path = args[0] if args else '../../src/main/resources/assets/projectseele/motion/first_battle_r59.json'
    actors, clip = S.Actors(), S.Clip(path)
    eva_label = np.concatenate([[bone] * (len(tris) * 3) for bone, tris, _ in actors.eva_mesh.parts])
    mesh = actors.angel_mesh
    angel_label = np.array(mesh.bones)[mesh.idx[np.arange(len(mesh.idx)), mesh.w.argmax(1)]]

    # every triangle carries its own three corners: one of each shared corner is enough to test
    first = S.clip_scene(actors, clip, 0.0)[0]
    eva_one = np.unique(np.round(first[0][0].reshape(-1, 3), 4), axis=0, return_index=True)[1]
    angel_one = np.unique(np.round(first[1][0].reshape(-1, 3), 4), axis=0, return_index=True)[1]
    eva_names, angel_names = eva_label[eva_one], angel_label[angel_one].astype(str)
    eva_hand = {side: eva_names == 'hand_' + side for side in 'lr'}
    angel_arm = {side: np.char.startswith(angel_names, 'hand_' + side) | (angel_names == 'forearm_' + side) for side in 'lr'}

    def frame(t, shift=0.0):
        tris, _, _ = S.clip_scene(actors, clip, t)
        e, a = tris[0][0], tris[1][0] + np.array([0, 0, shift])
        ep, ap = e.reshape(-1, 3)[eva_one], a.reshape(-1, 3)[angel_one]
        row = {'t': t}
        row['eva_in'], row['eva_in_part'] = deepest(ep, eva_names, a, ap.min(0), ap.max(0))
        row['angel_in'], row['angel_in_part'] = deepest(ap, angel_names, e, ep.min(0), ep.max(0))
        for side in 'lr':
            row['eva_hand_' + side] = gap(ep[eva_hand[side]], a)
            row['angel_arm_' + side] = gap(ap[angel_arm[side]], e) if angel_arm[side].any() else float('nan')
        return row

    if '--entry' in sys.argv:
        entry(frame, eased)
        return
    out = open(opt('--out', 'contact_rows.tsv'), 'w', encoding='utf8')
    out.write('t\teva_in\teva_part\tangel_in\tangel_part\teva_hand_l\teva_hand_r\tangel_arm_l\tangel_arm_r\n')
    rows = []
    for t in np.arange(0.0, ANGEL_GONE, 1.0 / fps):
        r = frame(float(t))
        rows.append(r)
        out.write('%.2f\t%.2f\t%s\t%.2f\t%s\t%.2f\t%.2f\t%.2f\t%.2f\n' % (r['t'], r['eva_in'], r['eva_in_part'], r['angel_in'], r['angel_in_part'],
                                                                  r['eva_hand_l'], r['eva_hand_r'], r['angel_arm_l'], r['angel_arm_r']))
        out.flush()
    print('whole clip, Sachiel where the clip has it (%d frames at %.0f a second)' % (len(rows), fps))
    for key, who in (('eva_in', 'Unit-01 inside Sachiel'), ('angel_in', 'Sachiel inside Unit-01')):
        found = spans(rows, key, deep)
        print('  %s by more than %.1f: %s' % (who, deep, 'never' if not found else ''))
        for a, b, d, part in found:
            print('      %5.2f to %5.2f s, deepest %.1f (%s)' % (a, b, d, part))
    print('authored contacts (gap from the hand to the other body, 0 = touching)')
    grab = [r for r in rows if 8.2 <= r['t'] <= 9.6]
    if grab:
        print('  the catch, 8.2 to 9.6 s: left hand %.2f to %.2f, right hand %.2f to %.2f' % (
            min(r['eva_hand_l'] for r in grab), max(r['eva_hand_l'] for r in grab), min(r['eva_hand_r'] for r in grab), max(r['eva_hand_r'] for r in grab)))
    for blow in chor.BLOWS:
        r = frame(blow)
        print('  blow at %5.2f s: left fist %.2f, right fist %.2f, deepest Unit-01 inside Sachiel %.1f (%s)' % (
            blow, r['eva_hand_l'], r['eva_hand_r'], r['eva_in'], r['eva_in_part']))
    hug = [r for r in rows if 16.9 <= r['t'] <= 18.5]
    if hug:
        print('  the embrace, 16.9 to 18.5 s: Sachiel\'s arms from Unit-01 %.2f to %.2f (left), %.2f to %.2f (right); Sachiel inside Unit-01 up to %.1f, Unit-01 inside Sachiel up to %.1f' % (
            min(r['angel_arm_l'] for r in hug), max(r['angel_arm_l'] for r in hug), min(r['angel_arm_r'] for r in hug), max(r['angel_arm_r'] for r in hug),
            max(r['angel_in'] for r in hug), max(r['eva_in'] for r in hug)))
    print('the first 1.2 s for a Sachiel that stood nearer than the clip\'s 52 blocks')
    entry(frame, eased)


def entry(frame, eased):
    print('  carried %s' % ('with the eased start it had before' if eased else 'as the game does it'))
    for start in (14.0, 20.0, 27.0):
        worst, until = 0.0, None
        for t in np.arange(0.0, 0.7, 1.0 / 30):
            r = frame(float(t), (start - CLIP_ANGEL_Z) * carried(t, eased))
            d = max(r['eva_in'], r['angel_in'])
            worst = max(worst, d)
            if d > 0.3:
                until = float(t)
        print('  %2.0f blocks: bodies inside each other by up to %.1f, %s' % (start, worst, 'never over 0.3' if until is None else 'over 0.3 until %.2f s' % until))


if __name__ == '__main__':
    main()
