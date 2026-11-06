"""Map measured saved block tops alongside declared roads and native rails."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from author_hakone_lakefront import Editor
from render_hakone_installed_map import color
from query_blocks import AIR

def review(a):
    a.out.mkdir(exist_ok=False,parents=True)
    x,z,X,Z=json.loads((a.source/'capture.json').read_text('utf8'))['bounds_xz']
    shape=(Z-z+1,X-x+1);im=np.zeros((*shape,3));height=np.full(shape,-129);e=Editor(a.source)
    for file in (a.source/'source').glob('*.npz'):
        rx,rz=map(int,file.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        visible=np.asarray([s.split('[')[0]not in AIR|{'minecraft:light','minecraft:barrier','projectseele:period_fixture_part'}for s in r['names']]);rgb=np.asarray([color(s)for s in r['names']])
        for(cx,cz),v in zip(r['coords'],r['after']):
            y=np.where(visible[v],np.arange(448)[:,None,None],0).max(0);top=np.take_along_axis(v,y[None],axis=0)[0]
            area=np.s_[int(cz)*16-z:int(cz)*16-z+16,int(cx)*16-x:int(cx)*16-x+16];im[area]=rgb[top];height[area]=y-128
        e.regions.clear()
    np.savez_compressed(a.out/'top.npz',bounds=[x,z,X,Z],rgb=im,height=height)
    with np.load(a.authority/'network.npz')as f:
        bx,bz,_,_=map(int,f['bounds']);area=np.s_[z-bz:Z-bz+1,x-bx:X-bx+1];walk=f['walk'][area]
    catalog=[r for r in json.loads((a.authority/'catalog.json').read_text('utf8'))if 'site'in r and x<r['site']['centre'][0]<X and z<r['site']['centre'][1]<Z]
    curves=json.loads((a.authority/'native-curves.json').read_text('utf8'));fig,axes=plt.subplots(1,2,figsize=(18,12),dpi=140)
    for ax in axes:
        ax.imshow(im,extent=[x,X+1,Z+1,z]);ax.set_xlim(x,X);ax.set_ylim(Z,z);ax.grid(alpha=.25)
        for row in curves['trains']:
            p=np.asarray(row['points']);sel=(p[:,0]>=x)&(p[:,0]<=X)&(p[:,2]>=z)&(p[:,2]<=Z)
            if sel.any():ax.plot(p[sel,0],p[sel,2],color='#ee7777',lw=1)
    for n,r in enumerate(catalog):
        px,pz=r['site']['centre'];h=r['site']['floor'];fresh='installed_neighbourhood'in r
        axes[0].annotate(f'{n}:{h}',(px,pz),fontsize=8,color='#121236',bbox=dict(fc='#b3ffd2'if fresh else'white',alpha=.8,pad=.2))
    overlay=np.zeros((*shape,4));overlay[walk]=[1,.75,.15,.7];axes[1].imshow(overlay,extent=[x,X+1,Z+1,z])
    axes[0].set_title('Current saved blocks; index : building floor')
    axes[1].set_title('Declared public surface; red = native rail')
    fig.tight_layout();fig.savefig(a.out/'map.png');plt.close(fig)
    (a.out/'parcel-key.json').write_text(json.dumps([dict(n=n,**r)for n,r in enumerate(catalog)],ensure_ascii=False,indent=2),'utf8')
    print('Mapped',len(catalog),'current parcels; saved surface and declared planning frame kept distinct',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','authority','out'):p.add_argument('--'+name,type=Path,required=True)
    review(p.parse_args())
