"""Plot real source BVH joint positions to select usable capture phases.

Not an EVA render, not a retarget, and never a substitute for native review.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from bvh_motion_r12 import load_bvh

p=argparse.ArgumentParser();p.add_argument('--sources',nargs='+',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--frame-ranges',nargs='*',help='One inclusive start:end per source, using official frame cuts where supplied')
a=p.parse_args()
if a.frame_ranges:assert len(a.frame_ranges)==len(a.sources)
assert not a.out.exists();a.out.mkdir(parents=True)
fig=plt.figure(figsize=(20,len(a.sources)*3.7));records=[]
for ri,path in enumerate(a.sources):
    capture=load_bvh(path);pos=capture['positions'];parents=capture['parents'];names=capture['names']
    first,last=0,len(pos)-1
    if a.frame_ranges:
        first,last=map(int,a.frame_ranges[ri].split(':'));last=len(pos)-1 if last<0 else last
        assert 0<=first<last<len(pos)
    ids=np.linspace(first,last,8).astype(int)
    # Original source units, fixed bounding box per clip, no visual scaling of limbs.
    centred=pos-pos[:,:1,:]*[1,0,1];low=centred[first:last+1].min((0,1));high=centred[first:last+1].max((0,1));centre=(low+high)/2
    radius=max(high-low)*.55
    for ci,frame in enumerate(ids):
        ax=fig.add_subplot(len(a.sources),8,ri*8+ci+1,projection='3d')
        points=centred[frame]
        for j,parent in enumerate(parents):
            if parent<0:continue
            q=points[[parent,j]];colour='#bc5a37'if names[j].startswith('Right')else'#256c8e'
            ax.plot(q[:,0],q[:,2],q[:,1],color=colour,linewidth=1.6)
        ax.set(xlim=(centre[0]-radius,centre[0]+radius),ylim=(centre[2]-radius,centre[2]+radius),
               zlim=(centre[1]-radius,centre[1]+radius),title=f'{path.stem}\nf{frame} / {frame/capture["fps"]:.2f}s')
        ax.set_box_aspect((1,1,1));ax.view_init(elev=10,azim=-58);ax.set_axis_off()
    records.append(dict(source=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        frames=len(pos),fps=capture['fps'],sampled_frames=ids.tolist(),selected_inclusive_range=[first,last],native_EVA_review=False))
fig.suptitle('RAW HUMAN CAPTURE — joint FK only; no EVA retarget / no animation quality approval',fontsize=15)
fig.tight_layout();fig.savefig(a.out/'source_sequence.png',dpi=140);plt.close(fig)
(a.out/'sources.json').write_text(json.dumps(records,indent=2),'utf8')
print('Source sequences:',[(r['frames'],r['fps'])for r in records])
