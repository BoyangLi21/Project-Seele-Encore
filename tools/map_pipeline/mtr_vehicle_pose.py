"""Finite rigid-car poses following the MTR 4.0.5 runtime bytecode.

Read-only mathematical helper: no JAR, registry, save or Simulator access.
Source branches frozen in odawara-interchange-pose-source-v1:
  VehicleCar.<init>: hasOneBogie iff bogie1Position == bogie2Position.
  Vehicle.getVehicleCarsAndPositions: each actual bogie offset is sampled.
  Vehicle.getBogiePositions, bytecode offsets 14..120: clamp to complete
    consist bounds; radius=clamp(min(distance to both ends),0.1,1); clamp
    the two samples to [lowerEnd,upperEnd-0.001].
  PositionAndRotation(Vector,Vector): midpoint and second-minus-first yaw.
  PositionAndRotation(list,VehicleCar), offsets 20..248: one-bogie reuse or
    two-bogie average/yaw, then subtract mean(bogie offsets) along body yaw.

``direction`` maps increasing model-local Z onto increasing (+1) or decreasing
(-1) rail distance. It is not the name of MTR's reversed boolean. The caller
must supply the two resource bogie offsets explicitly, including zero/zero.
Absent consist bounds means both bogies are >=1m from complete-train ends;
callers near a consist end must pass bounds or distances, not rely on this.
Rail endpoints and complete-train endpoints are distinct concepts.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from shapely.geometry import LineString
from shapely.ops import unary_union
from map_pipeline.vehicle_envelopes import point,rectangle

SOURCE_BRANCHES={
    'single_bogie':'VehicleCar.<init>: equal offsets set hasOneBogie',
    'bogie_samples':'Vehicle.getBogiePositions bytecode 14..120',
    'bogie_midpoint':'PositionAndRotation(Vector,Vector) bytecode 1..11',
    'body_pose':'PositionAndRotation(list,VehicleCar) bytecode 20..248',
}

def pose(line,distance,bogie1_position,bogie2_position,*,consist_bounds=None,
         consist_end_distances=None,direction=1,extend=True):
    """Return rendered body origin, local-Z direction and left normal in X/Z.

    ``consist_bounds`` is (lowerDistanceAlongRail, upperDistanceAlongRail).
    ``consist_end_distances`` is (distanceToLowerEnd,distanceToUpperEnd) from
    the nominal car centre; it is useful when enveloping a moving whole car.
    Both independent bogie offsets are model-local distances from that centre.
    """
    if direction not in(-1,1)or not all(math.isfinite(float(v))for v in(distance,bogie1_position,bogie2_position)):
        raise ValueError('Finite car centre/bogie offsets and direction +/-1 required')
    if consist_bounds is not None and consist_end_distances is not None:raise ValueError('Specify one complete-consist boundary form')
    if consist_end_distances is not None:
        if len(consist_end_distances)!=2 or any(not math.isfinite(float(v))or v<0 for v in consist_end_distances):raise ValueError('Finite nonnegative consist-end distances required')
        consist_bounds=(distance-consist_end_distances[0],distance+consist_end_distances[1])
    if consist_bounds is None:lower,upper=-math.inf,math.inf
    else:
        lower,upper=map(float,consist_bounds)
        if not all(map(math.isfinite,(lower,upper)))or upper-lower<=.001:raise ValueError('Complete-consist interval must exceed 0.001m')
    def bounded(value,hi=upper):return max(lower,min(hi,value))
    def bogie(offset):
        s=bounded(distance+direction*offset)
        radius=max(.1,min(1.,abs(s-lower),abs(s-upper)))
        a=point(line,bounded(s-direction*radius,upper-.001),extend)
        b=point(line,bounded(s+direction*radius,upper-.001),extend)
        return(a+b)/2,b-a
    first,one_direction=bogie(bogie1_position)
    if bogie1_position==bogie2_position:
        raw_centre=first;u=one_direction
    else:
        second,_=bogie(bogie2_position);raw_centre=(first+second)/2;u=second-first
    norm=np.linalg.norm(u)
    if not np.isfinite(norm)or norm<=1e-12:raise ValueError('Degenerate runtime bogie direction')
    u=u/norm;centre=raw_centre-u*(bogie1_position+bogie2_position)/2
    return centre,u,np.array([-u[1],u[0]])

def envelope(line,*,length,width,bogie1_position,bogie2_position,
             lateral_margin=0,longitudinal_margin=0,spacing=.125,extend=True,
             consist_end_distances=None,directions=(1,-1)):
    """Union full rigid-car rectangles along a finite centre-distance interval.

    Width and length describe the selected model-height band, not a whole-height
    box. Callers must still clip actual block collision boxes in Y. Symmetric
    bogies have identical symmetric-rectangle sweeps in the two directions.
    """
    if min(length,width,spacing)<=0 or min(lateral_margin,longitudinal_margin)<0 or spacing>1:
        raise ValueError('Positive sizes, <=1m sampling and nonnegative margins required')
    if not directions or any(d not in(-1,1)for d in directions):raise ValueError('Explicit +/-1 directions required')
    if bogie1_position==-bogie2_position and consist_end_distances is None:directions=(directions[0],)
    a,b=length/2+longitudinal_margin,width/2+lateral_margin
    samples=np.linspace(0,line.length,math.ceil(line.length/spacing)+1)
    return unary_union([rectangle(*pose(line,float(s),bogie1_position,bogie2_position,
        consist_end_distances=consist_end_distances,direction=d,extend=extend),-a,a,-b,b)
        for d in directions for s in samples])

def self_check():
    """Finite regression cases against closed-form straight/circular geometry."""
    rows=[]
    def check(name,actual,expected,tolerance=1e-8):
        error=float(np.max(np.abs(np.asarray(actual)-np.asarray(expected))));rows.append(dict(name=name,maximum_error=error,tolerance=tolerance,passed=error<=tolerance))
    line=LineString([(0,0),(100,0)])
    for offsets in[(-6,6),(0,0),(-1,5),(2,2)]:
        for direction in(-1,1):
            cp,u,n=pose(line,50,*offsets,direction=direction);check('straight-origin-'+str((offsets,direction)),cp,[50,0]);check('straight-direction-'+str((offsets,direction)),u,[direction,0])
    cp,u,_=pose(line,5,0,0,consist_end_distances=(.5,.5));check('complete-consist-upper-epsilon',cp,[4.9995,0]);check('complete-consist-yaw',u,[1,0])
    for s in(0,100):check('finite-line-end-extension-'+str(s),pose(line,s,-6,6)[0],[s,0])
    radius=50.;angles=np.linspace(-1.4,1.4,56001);arc=LineString(np.column_stack((radius*np.cos(angles),radius*np.sin(angles))));mid=arc.length/2
    cp,u,_=pose(arc,mid,-6,6);check('circular-two-bogie-body-origin',cp,[radius*math.cos(6/radius)*math.cos(1/radius),0],2e-6);check('circular-two-bogie-yaw',u,[0,1],2e-7)
    cp,u,_=pose(arc,mid,0,0);check('circular-one-bogie-origin',cp,[radius*math.cos(1/radius),0],2e-6)
    # Closed form for asymmetric -1/+5 offsets: two smoothed bogie centres,
    # followed by a 2m origin correction along the chord yaw.
    p1=radius*math.cos(1/radius)*np.array([math.cos(-1/radius),math.sin(-1/radius)])
    p2=radius*math.cos(1/radius)*np.array([math.cos(5/radius),math.sin(5/radius)]);direction=(p2-p1)/np.linalg.norm(p2-p1);expected=(p1+p2)/2-direction*2
    cp,u,_=pose(arc,mid,-1,5);check('circular-asymmetric-origin',cp,expected,2e-6);check('circular-asymmetric-yaw',u,direction,2e-7)
    poly=envelope(line,length=20,width=3,bogie1_position=-6,bogie2_position=6,spacing=.5);check('finite-envelope-bounds',poly.bounds,[-10,-1.5,110,1.5])
    rejected=False
    try:pose(line,50,0,0,consist_bounds=(50,50))
    except ValueError:rejected=True
    rows.append(dict(name='zero-length-consist-rejected',passed=rejected))
    return dict(errors=[q['name']for q in rows if not q['passed']],cases=rows,source_branches=SOURCE_BRANCHES,world_written=False,simulator_started=False)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--self-check',type=Path,required=True);a=p.parse_args();r=self_check();a.self_check.write_text(json.dumps(r,indent=2),'utf8');print('MTR body pose cases',len(r['cases']),'errors',r['errors']);raise SystemExit(bool(r['errors']))
