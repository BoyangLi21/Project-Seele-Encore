"""Continuous elbow plane from the authored pose, with the same axial guard."""
import copy
import numpy as np
from scipy.spatial.transform import Rotation as R
from anatomical_hinge_r35 import solve as hinge
from calibrated_arm_r49 import axial_twist

def solve(p,P,upper,lower,end,joint,target,pole,axis,orientation=None):
    origin=p.point(upper);direction=np.asarray(target)-origin;direction/=max(np.linalg.norm(direction),1e-8)
    side=upper[-1]
    normals=getattr(p,'r52_elbow_normals',{})
    if side in normals:
        normal=np.asarray(normals[side],float).copy();projected=normal-direction*(normal@direction)
        if np.linalg.norm(projected)<1e-6:
            old=np.asarray(p.r52_elbow_directions[side],float)
            transport=R.from_rotvec(normal*np.pi) if old@direction<-.999999 else R.align_vectors([direction],[old])[0]
            projected=transport.apply(normal);projected-=direction*(projected@direction)
        projected/=max(np.linalg.norm(projected),1e-8);reference=np.cross(projected,direction)
    else:
        reference=np.asarray(getattr(p,'r52_elbow_poles',{}).get(side,p.point(upper,joint)-origin),float).copy()
        reference-=direction*(reference@direction)
    if np.linalg.norm(reference)<1e-6:
        reference=np.asarray(pole,float)-direction*(np.asarray(pole)@direction)
    reference/=max(np.linalg.norm(reference),1e-8)
    guide=p.q[upper];best=None
    for angle in [0]+[v for a in range(1,181) for v in (a,-a)]:
        plane=R.from_rotvec(direction*np.radians(angle)).apply(reference);trial=copy.deepcopy(p)
        result=hinge(trial,P,upper,lower,end,joint,target,plane,axis,orientation)
        twist=abs(axial_twist(trial.q[upper],np.asarray(joint)-P[upper]))
        guide_error=(guide.inv()*trial.q[upper]).magnitude()
        score=max(0,twist-np.radians(75))**2*10000+guide_error**2+.001*np.radians(angle)**2
        if best is None or score<best[0]:best=(score,trial,result,twist,angle)
        if twist<=np.radians(75)+1e-8:break
    _,trial,result,twist,angle=best
    for name in (upper,lower,end):p.setq(name,trial.q[name]);p.setp(name,trial.p[name])
    result.update(upper_axial_twist_degrees=float(np.degrees(twist)),elbow_plane_adjustment_degrees=angle,axial_guard_passed=twist<=np.radians(75)+1e-6)
    return result
