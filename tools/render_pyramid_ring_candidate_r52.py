"""Exact proposed upper ring plans, with centre-line connectivity witness."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.ndimage import label
from r52_spatial_plan import BASE
from plan_pyramid_ring_links_r52 import LINKS

d=np.load(BASE/'pyramid_floor_review/CURRENT.npz');a=d['states'];p=list(map(str,d['palette']));o=d['origin']
folder=BASE/'pyramid_ring_links/upper_public_ring_closures';q=np.load(folder/'BEFORE_AFTER.npz');new=q['after'];qo=q['origin'];qp=list(map(str,q['palette']))
for s in qp:
    if s not in p:p.append(s)
m=np.array([p.index(s)for s in qp]);dy,dz,dx=qo[[1,2,0]]-o[[1,2,0]];h,l,w=new.shape;a[dy:dy+h,dz:dz+l,dx:dx+w]=m[new]
fig,axs=plt.subplots(1,2,figsize=(13,8),layout='constrained');empty=np.array([s in ('minecraft:air','minecraft:cave_air','minecraft:void_air')for s in p]);report=[]
for ax,y in zip(axs,(-485,-457)):
    i=y-o[1];foot=a[i];walk=empty[foot]&empty[a[i+1]]&~empty[a[i-1]]
    rgb=np.ones((*foot.shape,3))*.83;rgb[~empty[foot]]=[.17,.24,.27];rgb[walk]=[.69,.82,.64];rgb[np.array(['glass'in s for s in p])[foot]]=[.17,.69,.78]
    ax.imshow(rgb,origin='lower',extent=(o[0]-.5,o[0]+a.shape[2]-.5,o[2]-.5,o[2]+a.shape[1]-.5));ax.set_title(f'Proposed public ring Y={y}');ax.set_xlim(-24,93);ax.set_ylim(256,399);ax.grid(alpha=.2)
    labels,n=label(walk);nodes=LINKS[y];ids=[int(labels[z-o[2],x-o[0]])for x,z in nodes]
    assert len(set(ids))==1 and ids[0]>0,(y,ids)
    report.append(dict(y=y,centre_nodes=nodes,connected_same_component=True,world_written=False,native=False))
fig.savefig(folder/'PLAN_VIEW.png',dpi=120);(folder/'STATIC_CENTRE_CONNECTIVITY.json').write_text(json.dumps(report,indent=2),'utf8');print(report)
