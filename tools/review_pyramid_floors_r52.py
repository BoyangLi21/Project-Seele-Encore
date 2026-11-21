"""Root current-world floor plans, exact saved states, no world editing."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json,argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.ndimage import label
from survey_r52_original_complex import measure
from r52_spatial_plan import BASE


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',default='');args=ap.parse_args()
    out=BASE/'pyramid_floor_review'
    if args.stage:
        assert args.stage.replace('_','').isalnum(),'Simple review stage name required'
        out=out/args.stage
    out.mkdir(parents=True,exist_ok=True)
    lo=(-95,-565,205);hi=(148,-430,448)
    target=out/'CURRENT.npz'
    if target.exists():
        d=np.load(target);a=d['states'];pal=list(map(str,d['palette']))
    else:
        a,pal=measure(lo,hi);np.savez_compressed(target,states=a,palette=pal,origin=lo)
    levels=(-554,-541,-527,-513,-499,-485,-471,-457,-433)
    fig,axs=plt.subplots(3,3,figsize=(18,18),layout='constrained')
    empty=np.array([s in ('minecraft:air','minecraft:cave_air','minecraft:void_air') or s.startswith(('minecraft:light[','minecraft:wall_torch','projectseele:nerv_direction_panel'))for s in pal])
    rows=[]
    for ax,y in zip(axs.flat,levels):
        i=y-lo[1];foot=a[i];head=a[i+1];floor=a[i-1]
        walk=empty[foot]&empty[head]&~empty[floor]
        image=np.ones((*foot.shape,3))*.84
        image[~empty[foot]]=[.17,.24,.27];image[walk]=[.69,.82,.64]
        image[np.array([('glass'in s)for s in pal])[foot]]=[.17,.69,.78]
        image[np.array([('door'in s or s=='minecraft:barrier')for s in pal])[foot]]=[.91,.48,.32]
        ax.imshow(image,origin='lower',extent=(lo[0]-.5,hi[0]+.5,lo[2]-.5,hi[2]+.5))
        ax.set_title(f'Actual foot Y={y} (green: two-cell air + support)');ax.set_xlabel('X');ax.set_ylabel('Z');ax.grid(alpha=.15)
        for x,z,name in ((66,305,'east'),(12,258,'command'),(28,318,'office'),(108,402,'deep')):
            ax.plot(x,z,'ro',markersize=3);ax.text(x+2,z,name,fontsize=7)
        labels,n=label(walk);sizes=np.bincount(labels.ravel())[1:]
        rows.append(dict(y=y,walk_cells=int(walk.sum()),static_air_components=sorted(map(int,sizes),reverse=True)[:20]))
    fig.savefig(out/'CURRENT_NINE_FLOORS.png',dpi=120);plt.close(fig)
    (out/'AIR_ONLY_REVIEW.json').write_text(json.dumps(dict(world_written=False,not_native_navigation_proof=True,floors=rows),indent=2),'utf8')
    print(json.dumps(rows),flush=True)


if __name__=='__main__':main()
