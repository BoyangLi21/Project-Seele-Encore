"""view_metrics.py <view.csv> [<view.csv> ...]: how much the pilot's first-person view moves, part by part.

Reads the view.csv a cockpit review writes (-Dprojectseele.cockpitReviewR64=true, one row per drawn frame) and
prints, for the parts of the drive (walk, run, strike, jump, look), for the camera and for the head's optical
point the camera was given:

  bob up / side / fore   the eye's quick movement against its unit, in the unit's own frame (blocks): what is
                         left after the eye's own one-second average is taken away. rms and peak to peak.
  speed                  how fast that quick movement goes (blocks a second): rms and most.
  per frame              the same movement from one drawn frame to the next (blocks): mean and most.
  pitch / roll           the view's turn about its own one-second average (degrees): rms and most.
  sink                   (jump only) how far the eye goes down after touching the ground, against where it
                         comes to rest (blocks).

The camera column is the picture; the head column is the Unit's head in the same frames, which is where the
camera stood up to R63. Run the same drive with -Dprojectseele.cockpitR64=false for the turns of the view as
they were (the kicks of footfalls and blows are scaled, not filtered, so they need the other run).
"""
import sys
import numpy as np

PARTS = ['walk', 'run', 'strike', 'jump', 'look']
# Parts of a drive that are not measured: standing, leaving and boarding, looking down at the seat.
SKIP = {'idle', 'stand', 'leave', 'board', 'exit', 'down', 'rise'}


def read(path):
    rows = []
    with open(path, encoding='utf8') as f:
        f.readline()
        for line in f:
            c = line.rstrip('\n').split(',')
            if len(c) < 18: continue
            rows.append((float(c[0]) / 1e9, int(c[1]), c[3], [float(x) for x in c[4:17]], int(c[17])))
    return rows


def smooth(t, v, window=1.0):
    """The average of v over a window of seconds about each sample."""
    out = np.empty_like(v)
    j0 = j1 = 0
    c = np.concatenate([[0], np.cumsum(v)])
    for i in range(len(t)):
        while t[j0] < t[i] - window / 2: j0 += 1
        while j1 < len(t) and t[j1] <= t[i] + window / 2: j1 += 1
        out[i] = (c[j1] - c[j0]) / max(1, j1 - j0)
    return out


def local(t, point, unit, yaw):
    d = point - unit
    s, c = np.sin(np.radians(yaw)), np.cos(np.radians(yaw))
    right = -d[:, 0] * c - d[:, 2] * s
    fore = -d[:, 0] * s + d[:, 2] * c
    return np.stack([right, d[:, 1], fore], axis=1)


def quick(t, v):
    return v - np.stack([smooth(t, v[:, k]) for k in range(v.shape[1])], axis=1)


def report(name, rows):
    print(name)
    # Whatever parts the drive had (the stances script names its own), in the order they came.
    parts = []
    for r in rows:
        if r[2] not in SKIP and r[2] not in parts: parts.append(r[2])
    for part in parts:
        sel = [r for r in rows if r[2] == part and r[4] == 1]
        if len(sel) < 20:
            print('  %-7s no frames' % part); continue
        t = np.array([r[0] for r in sel]); v = np.array([r[3] for r in sel])
        cam, head, unit, yaw = v[:, 0:3], v[:, 3:6], v[:, 6:9], v[:, 9]
        fps = (len(t) - 1) / (t[-1] - t[0])
        print('  %-7s %d frames, %.1f s, %.0f fps' % (part, len(t), t[-1] - t[0], fps))
        for label, point in (('camera', cam), ('head', head)):
            q = quick(t, local(t, point, unit, yaw))
            dq = np.diff(q, axis=0); dt = np.diff(t)[:, None]; ok = dt[:, 0] > 1e-4
            speed = np.linalg.norm(dq[ok] / dt[ok], axis=1); step = np.linalg.norm(dq, axis=1)
            print('     %-6s bob up %.2f rms %.2f p-p | side %.2f rms %.2f p-p | fore %.2f rms %.2f p-p | speed %.1f rms %.1f most | per frame %.3f mean %.3f most'
                  % (label, q[:, 1].std(), np.ptp(q[:, 1]), q[:, 0].std(), np.ptp(q[:, 0]), q[:, 2].std(), np.ptp(q[:, 2]),
                     np.sqrt((speed ** 2).mean()), speed.max(), step.mean(), step.max()))
        pitch = v[:, 11] - smooth(t, v[:, 11]); roll = v[:, 12] - smooth(t, v[:, 12])
        print('     view   pitch %.3f rms %.2f most | roll %.3f rms %.2f most (degrees)'
              % (pitch.std(), np.abs(pitch).max(), roll.std(), np.abs(roll).max()))
        if part == 'jump':
            for label, point in (('camera', cam), ('head', head)):
                h = point[:, 1] - unit[:, 1]
                top = int(np.argmax(unit[:, 1]))
                # Touch-down: the unit's height back at its starting value after the top of the jump.
                ground = unit[0, 1]
                down = [i for i in range(top, len(t)) if unit[i, 1] <= ground + .05]
                if not down: print('     %-6s no touch-down in the part' % label); continue
                i0 = down[0]; after = h[i0:]; rest = np.median(h[-max(5, len(h) // 12):])
                print('     %-6s rise %.1f blocks; after touch-down the eye goes %.2f under where it rests, %.2f s after'
                      % (label, unit[top, 1] - ground, rest - after.min(), t[i0 + int(np.argmin(after))] - t[i0]))


if __name__ == '__main__':
    for path in sys.argv[1:]:
        report(path, read(path))
