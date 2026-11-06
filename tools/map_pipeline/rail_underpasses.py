"""Finite ground-road exceptions below a retained elevated railway.

Only original air/soil and the declared former road surface are editable.
Bridge members, foundations, native devices and the track envelope stay owned.
"""
import numpy as np
from hakone_earthworks import road_blocks
from plan_ashi_landscape_r54 import SOIL, PLANTS
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT


def editable_underpass_column(editor, x, z, low, high, boxes, old_walk, old_grade):
    mask = np.zeros(high - low + 1, bool)
    for a, b, c, A, B, C in boxes:
        if not (a <= x <= A and c <= z <= C):
            continue
        # The legacy retained train guard extends thirty blocks below rail
        # and seven above. An exception must end below the real deck guard.
        if B > high - 11:
            raise ValueError(('Underpass enters railway deck or clearance', x, z, B, high))
        floor, slab = road_blocks(old_grade)
        for y in range(max(low, b), min(high, B) + 1):
            state = editor.state(x, y, z, original=True)
            bare = state.split('[')[0]
            old_surface = old_walk and y == int(floor) and bare in PAVEMENT and ('type=bottom' in state) == bool(slab)
            if bare in AIR | SOIL | PLANTS | {'minecraft:light'} or old_surface:
                mask[y - low] = True
    return mask


def physical_deck_ceilings(curves,bounds,radius=4.5):
    """Lowest permitted soffit Y beneath the actual track swept footprint.

    The 4.5 m half-width includes the running vehicle and lateral allowance.
    Original concrete, piers and bridge blocks remain immutable independently.
    A point outside this footprint is not below a train merely because it is
    inside the legacy square +/-8 m terrain-preservation guard.
    """
    x,z,X,Z=map(int,bounds);zz,xx=np.mgrid[z:Z+1,x:X+1]
    centres=np.column_stack((xx.ravel()+.5,zz.ravel()+.5));limit=np.full(len(centres),319,int)
    for row in curves:
        points=np.asarray(row['points'],float)
        for a,b in zip(points[:-1],points[1:]):
            if max(a[0],b[0])+radius<x or min(a[0],b[0])-radius>X+1 or max(a[2],b[2])+radius<z or min(a[2],b[2])-radius>Z+1:continue
            delta=(b-a)[[0,2]];length2=float(delta@delta)
            t=np.clip((centres-a[[0,2]])@delta/max(length2,1e-12),0,1)
            near=a[[0,2]]+t[:,None]*delta
            touched=np.sum((centres-near)**2,axis=1)<=radius**2
            ceiling=np.floor(a[1]+t*(b[1]-a[1])).astype(int)-3
            limit[touched]=np.minimum(limit[touched],ceiling[touched])
    return {(int(px),int(pz)):int(y)for px,pz,y in zip(xx.ravel(),zz.ravel(),limit)}


def allowed_roof_infill_column(editor, x, z, low, high, boxes,physical_deck_ceiling=None):
    """Permit only solid soffit infill below the lowest retained running rail.

    This never licenses excavation: original bridge members remain unchanged,
    and the finished cell must be concrete. A supplied limit is measured from
    the swept track footprint; otherwise both conservative guard bounds apply.
    """
    mask=np.zeros(high-low+1,bool)
    ceiling=min(high-10,low+28)if physical_deck_ceiling is None else int(physical_deck_ceiling)
    for a,b,c,A,B,C in boxes:
        if not(a<=x<=A and c<=z<=C):continue
        for y in range(max(low,b),min(high,B,ceiling)+1):
            original=editor.state(x,y,z,original=True).split('[')[0]
            actual=editor.state(x,y,z).split('[')[0]
            if original in AIR|SOIL and actual=='minecraft:light_gray_concrete':mask[y-low]=True
    return mask
