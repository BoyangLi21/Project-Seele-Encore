"""Root far-ridge design over the measured native surface; no world writes."""
import json,math
import numpy as np
from r52_spatial_plan import BASE

out=BASE/'far_yashima';d=np.load(out/'FAR_SURFACE.npz');old=d['height'];origin=d['origin'];assert d['status'].all()and not d['authored'].any()
z,x=np.indices(old.shape);x=x+origin[0];z=z+origin[1]
centre=np.array([-1250.,-1410.]);target=np.array([30.5,348.5]);f=target-centre;f/=np.linalg.norm(f);right=np.array([f[1],-f[0]])
u=(x-centre[0])*right[0]+(z-centre[1])*right[1];v=(x-centre[0])*f[0]+(z-centre[1])*f[1]
height=old.astype(float).copy()
for cx,cz,rx,rz,peak in [(-1390,-1570,275,275,194),(-1250,-1410,280,275,190),(-1110,-1530,145,220,148)]:
    r2=((x-cx)/rx)**2+((z-cz)/rz)**2;bell=np.maximum(0,1-r2)**2
    height=np.maximum(height,old+np.maximum(0,peak-old)*bell)
# A grass-topped, rounded operational shelf is cut into the city-facing ridge.
# Every surrounding slope blends into native terrain rather than a square rim.
radius=((u/93)**2+((v+2)/106)**2)**.5
t=np.clip((radius-1)/.8,0,1);blend=1-t*t*(3-2*t)
height=height*(1-blend)+174*blend
height=np.rint(np.maximum(height,old)).astype(np.int16)
# The plateau is below the rear summit, with a clear outward gun direction.
active=height!=old
assert not active[:8].any()and not active[-8:].any()and not active[:,:8].any()and not active[:,-8:].any(),'Ridge leaves native blending margin'
def at(a,b,y=175):
    p=centre+right*a+f*b;return[round(float(p[0])-.5)+.5,y,round(float(p[1])-.5)+.5]
points=dict(unit01_arrival=at(-65,-50),unit00_arrival=at(65,-50),unit01_prone_feet=at(0,-60),unit00_shield=at(0,62),cannon_bay_centre=at(0,12,174),command_console=at(-66,-3),personnel_arrival=at(-80,-45),service_rack=at(67,12))
for name,p in points.items():assert int(height[math.floor(p[2])-origin[1],math.floor(p[0])-origin[0]])==174,(name,p)
report=dict(world_written=False,centre_xz=centre.tolist(),forward_xz=f.tolist(),right_xz=right.tolist(),platform_floor_y=174,ramiel_feet=[30.5,114,348.5],ramiel_scale=4,attack_range=2600,distance_to_city_target=float(np.linalg.norm(target-centre)),points=points,old_soil_range=[int(old.min()),int(old.max())],new_range=[int(height.min()),int(height.max())],changed_columns=int(active.sum()),max_adjacent_step=int(max(np.abs(np.diff(height.astype(int),axis=0)).max(),np.abs(np.diff(height.astype(int),axis=1)).max())),old_native_terrain_preserved_outside_exact_mask=True,pending=['full block/tree/source inspection','terrain installation','old supply component migration','actual gun/door/pilot contact frames'])
(out/'RIDGE_DESIGN.json').write_text(json.dumps(report,indent=2),'utf8');np.savez_compressed(out/'RIDGE_HEIGHTS.npz',origin=origin,before=old,after=height,active=active)
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
fig=plt.figure(figsize=(13,6));ax=fig.add_subplot(121);ax.imshow(height,origin='lower',extent=[origin[0],origin[0]+old.shape[1],origin[1],origin[1]+old.shape[0]],cmap='terrain',vmin=40,vmax=200)
for name,p in points.items():ax.plot(p[0],p[2],'ro',ms=3);ax.annotate(name,(p[0],p[2]),fontsize=5)
ax.set_title('Root final far-ridge design (2140 m from target)');ax.grid(alpha=.25)
ax=fig.add_subplot(122,projection='3d');s=8;ax.plot_surface(x[::s,::s],z[::s,::s],height[::s,::s],cmap='terrain',vmin=40,vmax=200,linewidth=0,antialiased=True);ax.set_zlim(40,240);ax.view_init(elev=26,azim=-38);ax.set_title('Natural ridges + recessed grass operating shelf')
fig.tight_layout();fig.savefig(out/'RIDGE_DESIGN.png',dpi=150);plt.close(fig);print(json.dumps(report),flush=True)
