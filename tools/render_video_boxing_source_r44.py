"""CPU source-armature preview of the actual published video FK, at 30 fps."""
from pathlib import Path
import subprocess,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/video_source/boxing';data=np.load(OUT/'data6_fk.npz',allow_pickle=False);points=data['positions'];parents=data['parents'];names=data['names'];fps=int(data['fps']);frames=OUT/'source_frames';frames.mkdir(exist_ok=True)
fig=plt.figure(figsize=(8.64,4.86));ax=fig.add_subplot(111,projection='3d');fig.patch.set_facecolor('#eef1f5')
for frame,p in enumerate(points):
    ax.clear();ax.set_xlim(-.75,.75);ax.set_ylim(-.75,.85);ax.set_zlim(0,1.8);ax.set_box_aspect((1.05,1.15,1.5));ax.view_init(elev=12,azim=-27)
    for i,parent in enumerate(parents):
        if parent>=0:ax.plot(*np.stack([p[i],p[parent]]).T,color='#d35f34'if str(names[i]).startswith('R_')else'#246c9c',lw=4)
    ax.scatter(*p.T,color='#29374b',s=13);ax.set_title(f'A: published VIDEO boxing source / data6 / {frame/fps:.3f}s\n24 body joints; no captured fingers or measured COM',fontsize=10)
    ax.set_xlabel('X (m)');ax.set_ylabel('Y (m)');ax.set_zticks([0,.5,1,1.5]);fig.tight_layout();fig.savefig(frames/f'{frame+1:04d}.png',dpi=100)
plt.close(fig)
cmd=['ffmpeg','-y','-hide_banner','-loglevel','warning','-framerate',str(fps),'-i',str(frames/'%04d.png'),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'A_video_boxing_data6_original.mp4')]
subprocess.run(cmd,check=True);print('Actual source FK 30fps MP4:',OUT/'A_video_boxing_data6_original.mp4')
