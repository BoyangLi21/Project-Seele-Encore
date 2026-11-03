"""Roadside drainage, retaining faces and pedestrian protection on graded streets.

No room, original fixture, native clearance or parcel payload is appropriated.
Drain covers retain the commissioned surface height and full walking width.
"""
import numpy as np
from scipy.ndimage import distance_transform_edt
from map_pipeline.corridors import alignment
from hakone_earthworks import road_blocks
from prepare_hakone_togendai_neighbourhood import PAVE
from plan_ashi_landscape_r54 import SOIL,PLANTS
from query_blocks import AIR

EMPTY=AIR|PLANTS|{'minecraft:light'}

def decorate(e,d,spec,rows,details,preserved):
    x,z,X,Z=map(int,d['bounds']);shape=d['walk'].shape
    distance,nearest=distance_transform_edt(~d['walk'],return_indices=True)
    plot_distance=distance_transform_edt(~d['plots'])
    details.update(drain_covers=[],retaining_faces=[],slope_handrails=[],engineered_retaining_faces=[])
    for face in spec.get('engineered_retaining_faces',[]):
        count=0
        for px in range(face['x'][0],face['x'][1]+1):
            pz=face['z'];h=int(d['ground'][pz-z,px-x])
            for Y in range(face['bottom'],h-2):
                pos=(px,Y,pz)
                if preserved(pos)or e.state(*pos).split('[')[0]not in SOIL:continue
                state='minecraft:stone_bricks'if (px-face['x'][0])%8==0 or (Y-face['bottom'])%8==0 else'minecraft:light_gray_concrete'
                e.put(*pos,state);count+=1
        details['engineered_retaining_faces'].append(dict(**face,cells=count))
    # Small flush drain covers sit in the gutter beside the carriageway.
    for row in spec['streets']:
        curve,s=alignment(row)
        for at in np.arange(16,s[-1]-8,24):
            k=int(np.argmin(abs(s-at)));t=curve[k+1,[0,2]]-curve[k-1,[0,2]];t/=np.linalg.norm(t);n=np.array([-t[1],t[0]])
            for side in (-1,1):
                px,pz=map(int,np.rint(curve[k,[0,2]]+n*side*(row['width']/2+.6)));j,i=pz-z,px-x
                if not(0<=j<shape[0]and 0<=i<shape[1])or not d['walk'][j,i]or d['road'][j,i]:continue
                floor,slab=road_blocks(d['grade2'][j,i]);pos=(px,int(floor),pz)
                if preserved(pos)or e.state(*pos).split('[')[0]not in PAVE:continue
                state='minecraft:polished_blackstone_slab[type=bottom,waterlogged=false]'if slab else'minecraft:polished_deepslate'
                e.put(*pos,state);details['drain_covers'].append(list(pos))
    # Exposed retaining faces follow the walking edge, not a rectangular pad.
    # Only existing soil is faced; the natural slope and road datum stay put.
    for j,i in np.argwhere((distance>0)&(distance<=1.05)&(plot_distance>2)):
        J,I=nearest[:,j,i];px,pz=int(i+x),int(j+z);floor,slab=road_blocks(d['grade2'][J,I]);floor=int(floor)
        dx,dz=int(np.sign(i-I)),int(np.sign(j-J));u,v=i+3*dx,j+3*dz
        if not(0<=v<shape[0]and 0<=u<shape[1])or d['walk'][v,u]or d['plots'][v,u]:continue
        drop=floor-int(d['ground'][v,u])
        if drop<3:continue
        faced=[]
        for Y in range(max(floor-5,int(d['ground'][j,i])-5),floor+1):
            pos=(px,Y,pz)
            if preserved(pos)or e.state(*pos).split('[')[0]not in SOIL:continue
            state='minecraft:stone_bricks'if (px+pz)%7==0 else'minecraft:light_gray_concrete'
            e.put(*pos,state);faced.append(Y)
        if faced:details['retaining_faces'].append(dict(x=px,z=pz,ys=faced))
        # A one-block-high rail is outside the three-clear-block public path.
        base=int(d['ground'][j,i])
        if drop<4 or not faced or not 0<=floor-base<=3:continue
        if any(preserved((px,Y,pz))for Y in range(base+1,floor+2)):continue
        if any(e.state(px,Y,pz).split('[')[0]not in EMPTY for Y in range(base+1,floor+2)):continue
        for Y in range(base+1,floor+1):e.put(px,Y,pz,'minecraft:stone_bricks')
        horizontal=abs(i-I)>=abs(j-J)
        state='minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]'if horizontal else'minecraft:iron_bars[east=true,north=false,south=false,waterlogged=false,west=true]'
        e.put(px,floor+1,pz,state);details['slope_handrails'].append([px,floor+1,pz])
