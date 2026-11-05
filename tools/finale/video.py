"""Render the authored scene to MP4: python video.py out.mp4 view [fps] [t0] [t1]

view: film (the clip camera) or side (fixed wide profile following the action).
"""
import os
import subprocess
import sys
import tempfile

import numpy as np

import chor
import film as F
import review as V
import rig as R
import scene as S


def main():
    out, view = sys.argv[1], sys.argv[2]
    fps = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    t0 = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
    t1 = float(sys.argv[5]) if len(sys.argv) > 5 else 23.0
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    sc = chor.Scene(S.Actors())
    cam = F.Film()
    size = (960, 540)
    tmp = tempfile.mkdtemp(prefix='seele_film_')
    n = int(round((t1 - t0) * fps)) + 1
    for i in range(n):
        t = t0 + i / fps
        groups, s = V.scene_groups(sc, t)
        if view == 'film':
            p, g, f = cam.sample(t)
            c = R.Camera(p, g, f, size)
        else:
            hip = np.asarray(s['eva'][4]['hip'], float)
            mid = np.array([0, 0, min(max(hip[2] + 16, 22), 62)])
            c = R.Camera(mid + np.array([-150, 36, 0]), mid + np.array([0, 26, 0]), 40, size)
        img = R.render(c, groups, label='%s  t=%.2f s' % (view, t), lines=V.field_lines(t),
                       ground=(-100, 100, -50, 130))
        img.save(os.path.join(tmp, 'f%04d.png' % i))
    subprocess.run([ff, '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', os.path.join(tmp, 'f%04d.png'),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', out], check=True)
    print('wrote', out, n, 'frames')


if __name__ == '__main__':
    main()
