"""Offline plan and section views of the composed airport road candidate."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from author_hakone_lakefront import Editor
from map_pipeline.corridors import alignment
from map_pipeline.launch_earthworks import ground
from query_blocks import AIR


def color(state):
    name=state.split('[')[0]
    if name in AIR or name in {'minecraft:light','minecraft:structure_void'}:return [.88,.94,.97]
    if 'grass_block'in name:return [.38,.51,.29]
    if 'dirt'in name:return [.49,.39,.27]
    if 'tactile'in name:return [.95,.72,.12]
    if 'asphalt'in name or name=='minecraft:black_concrete':return [.20,.22,.23]
    if 'marking'in name or name=='minecraft:white_concrete':return [.88,.89,.87]
    if 'sea_lantern'in name:return [.80,.96,.90]
    if 'glass'in name:return [.48,.70,.74]
    if 'stone_brick'in name:return [.46,.48,.47]
    if 'smooth_stone'in name or 'floor_panel'in name:return [.67,.69,.67]
    return [.55,.57,.54]


def top(e,bounds):
    x,z,X,Z=bounds;heights=np.full((Z-z+1,X-x+1),-129,np.int16)
    rgb=np.zeros((*heights.shape,3))
    for rx in range(x//512,X//512+1):
        for rz in range(z//512,Z//512+1):
            r=e.region(rx*512,rz*512);names=r['names'];colors=np.asarray([color(s)for s in names])
            solid=np.asarray([s.split('[')[0]not in AIR|{'minecraft:light','minecraft:structure_void'}for s in names])
            for (cx,cz),v in zip(r['coords'],r['after']):
                px,pz=int(cx)*16,int(cz)*16;l,t,R,B=max(x,px),max(z,pz),min(X,px+15),min(Z,pz+15)
                if l>R or t>B:continue
                iy=np.where(solid[v],np.arange(448)[:,None,None],-1).max(0)
                iz,ix=np.mgrid[:16,:16];surface=colors[v[np.maximum(0,iy),iz,ix]]
                a=np.s_[t-z:B-z+1,l-x:R-x+1];b=np.s_[t-pz:B-pz+1,l-px:R-px+1]
                heights[a]=(iy-128)[b];rgb[a]=surface[b]
            e.regions.clear()
    return heights,rgb


def render(candidate,out):
    out.mkdir(parents=True,exist_ok=True);e=Editor(candidate)
    spec=json.loads((candidate/'authored-design.json').read_text('utf8'))['streets'][0]
    curve,s=alignment(spec)
    with np.load(candidate/'earthworks'/(spec['id']+'.npz'))as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);h=ground(e,[x,z,X,Z]);i=np.rint(curve[:,0]).astype(int)-x;j=np.rint(curve[:,2]).astype(int)-z
    fig=plt.figure(figsize=(15,9));gs=fig.add_gridspec(2,2,height_ratios=[1.5,1])
    ax=fig.add_subplot(gs[0,0]);nb=[710,980,830,1070];ht,rgb=top(e,nb)
    shade=LightSource(315,50).shade_rgb(rgb,ht,vert_exag=.65,blend_mode='soft')
    ax.imshow(shade,extent=[nb[0]-.5,nb[2]+.5,nb[3]+.5,nb[1]-.5]);ax.set_title('Airport approach: final saved-block surfaces')
    ax.scatter([740],[1052],c='#d78d00',s=25);ax.annotate('Existing terminal entrance',(740,1052),(760,1063),arrowprops={'arrowstyle':'-','color':'#6b4a13'},fontsize=9)
    ax.set_xlabel('X / m');ax.set_ylabel('Z / m')
    ax=fig.add_subplot(gs[0,1]);sb=[595,1600,690,1705];ht,rgb=top(e,sb)
    ax.imshow(LightSource(315,50).shade_rgb(rgb,ht,vert_exag=.65,blend_mode='soft'),extent=[sb[0]-.5,sb[2]+.5,sb[3]+.5,sb[1]-.5]);ax.set_title('Southern portal and retained town-road connection');ax.set_xlabel('X / m');ax.set_ylabel('Z / m')
    ax=fig.add_subplot(gs[1,0]);ax.plot(s,h[j,i],color='#657b48',label='Final terrain above centreline');ax.plot(s,curve[:,1],color='#333d47',label='Road walking surface')
    t0,t1=spec['tunnel']['along'];ax.axvspan(t0,t1,color='#9eabb6',alpha=.16,label='Bored section');ax.set_xlabel('Distance along road / m');ax.set_ylabel('Y / m');ax.set_title('Actual composed terrain and gentler longitudinal alignment');ax.legend(fontsize=8,loc='upper right');ax.grid(alpha=.2)
    ax=fig.add_subplot(gs[1,1]);ys=range(76,102);zs=range(1020,1059)
    cells=np.asarray([[color(e.state(740,y,zz))for zz in zs]for y in ys]);ax.imshow(cells,origin='lower',extent=[1019.5,1058.5,75.5,101.5],interpolation='nearest',aspect='equal')
    ax.set_title('Entrance section X740: original floor and canopy');ax.set_xlabel('Z / m');ax.set_ylabel('Y / m')
    fig.suptitle('Airport road candidate — offline geometry review, not in-game visual acceptance',fontsize=13)
    fig.tight_layout();path=out/'airport-connection-review.png';fig.savefig(path,dpi=170);plt.close(fig);print(path,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();render(a.candidate,a.out)
