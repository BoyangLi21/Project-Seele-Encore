"""Finite civil envelopes around measured native track curves.

The track itself stays native. Half-block bearing surfaces remain below its
lowest datum within each voxel column, including sloping and diagonal curves.
"""
import math
import numpy as np


def dense_points(points, step=.25):
    p=np.asarray(points,float)
    if p.ndim!=2 or p.shape[1]!=3 or len(p)<2:
        raise ValueError('A native curve needs two or more XYZ points')
    result=[]
    for a,b in zip(p,p[1:]):
        length=np.linalg.norm((b-a)[[0,2]])
        if length<1e-8: continue
        count=max(1,math.ceil(length/step))
        result.extend(a+(b-a)*u for u in np.arange(count)/count)
    result.append(p[-1])
    return np.asarray(result)


def columns(curves, indices, half_width=1.75, platform_width=1.3, max_vertical_spread=1.5):
    result={}
    for index in indices:
        row=curves[index];p=dense_points(row['points'])
        width=platform_width if row.get('kind')=='platform' else half_width
        sides=np.linspace(-width,width,max(3,math.ceil(2*width/.2)+1))
        for k,q in enumerate(p):
            tangent=(p[min(len(p)-1,k+1)]-p[max(0,k-1)])[[0,2]]
            norm=np.linalg.norm(tangent)
            if norm<1e-8: continue
            normal=np.array([-tangent[1],tangent[0]])/norm
            for side in sides:
                x,z=map(int,np.floor(q[[0,2]]+normal*side+1e-8))
                v=result.setdefault((x,z),dict(low=float(q[1]),high=float(q[1]),curves=set()))
                v['low']=min(v['low'],float(q[1]));v['high']=max(v['high'],float(q[1]));v['curves'].add(index)
    for pos,v in result.items():
        if max_vertical_spread is not None and v['high']-v['low']>max_vertical_spread:
            raise ValueError(('Different rail levels require separate envelopes',pos,v))
    return result


def bearing(low):
    """Return (voxel Y, state, exact upper face), never above native rail."""
    top=math.floor(low*2+1e-7)/2
    if top==math.floor(top):
        return int(top)-1,'minecraft:light_gray_concrete',top
    return math.floor(top),'minecraft:stone_brick_slab[type=bottom,waterlogged=false]',top


def vertical_bounds(row, height=4.5):
    y,state,top=bearing(row['low'])
    return y,state,top,math.ceil(row['high']+height-1e-7)


def block_top(y,state):
    return y+(.5 if 'type=bottom' in state and '_slab[' in state else 1.)
