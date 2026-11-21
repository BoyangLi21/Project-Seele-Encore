"""Root geometric sections of the exact pending bank3 voxel delta; no writes."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from r52_spatial_plan import BASE
from build_continuous_upright_directory_r52 import sample

OUT=BASE/'continuous_upright/final_0262_66f_civil'

def main():
    src=np.load(OUT/'CANDIDATE.npz');before=src['before'];after=src['after'];names=list(map(str,src['palette']))
    keys={tuple(map(int,k)):i for i,k in enumerate(src['section_keys'])}
    def lookup(points,data):
        p=np.floor(points).astype(int);out=np.full(len(p),len(names),np.int32)
        for n,(x,y,z) in enumerate(p):
            k=keys.get((x//16,z//16,y//16))
            if k is not None:out[n]=data[k,(y%16)*256+(z%16)*16+x%16]
        return out
    colours=[]
    for s in names:
        if s in ('minecraft:air','minecraft:cave_air','minecraft:void_air'):c=(20,27,32)
        elif s=='projectseele:nerv_machine_panel':c=(100,113,94)
        elif s=='projectseele:nerv_shaft_panel':c=(59,70,91)
        elif s=='projectseele:nerv_machine_edge':c=(150,159,149)
        elif 'light' in s and 'glass' not in s:c=(210,225,215)
        elif 'glass' in s:c=(65,155,175)
        elif s=='minecraft:barrier':c=(205,70,70)
        elif 'grass_block' in s:c=(72,130,61)
        elif 'dirt' in s:c=(110,79,49)
        else:c=(89,86,81)
        colours.append(c)
    colours=np.asarray(colours+[(210,100,200)],np.float32)/255
    fig,axes=plt.subplots(2,2,figsize=(17,10),layout='constrained')
    z,x=np.mgrid[-825:-475,-40:125];points=np.stack((x,np.full_like(x,-529),z),axis=-1)
    for ax,data,title in zip(axes[0],(before,after),('Current throat / Y -529','Candidate separated level throat / Y -529')):
        values=lookup(points.reshape(-1,3),data).reshape(x.shape)
        ax.imshow(colours[values],extent=[-40,124,-475,-825],aspect='equal');ax.set(title=title,xlabel='X',ylabel='Z')
    d=json.loads((BASE/'continuous_upright/spread_level_throats/GROUND_CONTINUOUS_DESIGN.json').read_text())
    leg=next(l for l in d['legs'] if l['id']=='unit1/exit3/upright_continuous')
    p=np.concatenate([sample(s['controls'],257) for s in leg['centre_curve']['segments']])
    dist=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p[:,[0,2]],axis=0),axis=1))]
    keep=np.r_[True,np.diff(dist)>1e-7];p,dist=p[keep],dist[keep];ss=np.arange(0,dist[-1],2.)
    xx=np.interp(ss,dist,p[:,0]);zz=np.interp(ss,dist,p[:,2]);yy=np.arange(-662,-465)
    points=np.stack((np.broadcast_to(xx,(len(yy),len(ss))),np.broadcast_to(yy[:,None],(len(yy),len(ss))),np.broadcast_to(zz,(len(yy),len(ss)))),axis=-1)
    for ax,data,title in zip(axes[1],(before,after),('Current world along final centreline','Candidate world along final centreline')):
        values=lookup(points.reshape(-1,3),data).reshape(len(yy),len(ss))
        ax.imshow(colours[values],origin='lower',extent=[0,ss[-1],yy[0],yy[-1]],aspect='auto');ax.set(title=title,xlabel='Horizontal travel distance / m',ylabel='Y');ax.axhline(-482,c='yellow',lw=.6)
    fig.suptitle('Exact saved voxel candidate. Pink = outside measured sections; not a hole. Native art still pending.')
    fig.savefig(OUT/'ROOT_FINAL_CIVIL_SECTIONS.png',dpi=130);plt.close(fig)
    print(OUT/'ROOT_FINAL_CIVIL_SECTIONS.png',flush=True)

if __name__=='__main__':main()
