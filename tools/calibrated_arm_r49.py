"""Two-bone arm solver with an explicit upper-arm axial-twist guard.

Endpoint accuracy alone accepts a reversed humerus. Candidate elbow planes
are evaluated against the actual bind arm axis, preserving segment lengths.
This is a project guard, not a claim of physiological motion simulation.
"""
import copy
import numpy as np
from scipy.spatial.transform import Rotation as R
from anatomical_hinge_r35 import solve as solve_hinge


def axial_twist(q, axis):
    axis=np.asarray(axis,float);axis/=np.linalg.norm(axis)
    xyzw=q.as_quat();angle=2*np.arctan2(xyzw[:3]@axis,xyzw[3])
    return float((angle+np.pi)%(2*np.pi)-np.pi)


def solve(p,P,upper,lower,end,joint,target,pole,axis,orientation=None):
    origin=p.point(upper);direction=np.asarray(target)-origin
    direction/=max(np.linalg.norm(direction),1e-8)
    requested=np.asarray(pole,float)-direction*(np.asarray(pole)@direction)
    if np.linalg.norm(requested)<1e-7:
        requested=np.array([0.,0,1])-direction*direction[2]
    requested/=max(np.linalg.norm(requested),1e-8)
    best=None
    for angle in (0,180,30,-30,60,-60,90,-90,120,-120,150,-150):
        plane=R.from_rotvec(direction*np.radians(angle)).apply(requested)
        trial=copy.deepcopy(p)
        result=solve_hinge(trial,P,upper,lower,end,joint,target,plane,axis,orientation)
        twist=abs(axial_twist(trial.q[upper],np.asarray(joint)-P[upper]))
        excess=max(0,twist-np.radians(75))
        # Prefer the requested elbow plane when it does not reverse the arm.
        # Choosing its opposite is appropriate only when that original plane
        # caused the old almost-180-degree limb roll.
        score=excess*excess*10000+twist*twist*.05+(1-plane@requested)*.15
        if best is None or score<best[0]:best=(score,trial,result,twist,angle)
        if angle==0 and twist<np.radians(60):break
        if angle==180 and twist<np.radians(15):break
    _,trial,result,twist,angle=best
    for name in (upper,lower,end):
        p.setq(name,trial.q[name]);p.setp(name,trial.p[name])
    result.update(upper_axial_twist_degrees=float(np.degrees(twist)),elbow_plane_adjustment_degrees=angle,
                  axial_guard_passed=twist<=np.radians(75)+1e-6)
    return result
