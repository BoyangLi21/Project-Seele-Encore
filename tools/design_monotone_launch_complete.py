"""Root candidate: true vertical starts and strictly rising launch trajectories.

This is a spatial review packet, not an installable runtime directory. The
proposed extra deep translation keeps the long Hakone incline in rock below
the actual GeoFront cavity. Runtime ready-stop semantics are audited separately.
"""
from pathlib import Path
import argparse
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json
import math
import numpy as np
from scipy.spatial import cKDTree
from build_continuous_upright_directory_r52 import corner,segment,sample,verify_segments

parser=argparse.ArgumentParser();parser.add_argument('--base',type=Path,required=True);args=parser.parse_args()
BASE=args.base.resolve()
OUT=BASE/'monotone_launch_candidate';OUT.mkdir(exist_ok=True)
DROP=384
SOLES=(.224014043808,.223975896835,.183567047119)
CASES=[]
POINTS={}
for v,x in enumerate((72.5,30.5,-11.5)):
    for bank,z in enumerate((124.5,76.5,28.5),1):
        start=np.array([x,-646.-DROP,z-SOLES[v]])
        if bank==1:
            end=np.array([x,-466.,z-SOLES[v]])
            pieces=[segment([start,end])]
            notes='Pure vertical ascent at original first-bank XZ'
        elif bank==2:
            up=start+[0,128.,0]
            join=np.array([x,-410.,-35.5-SOLES[v]])
            end=np.array([x,84.,join[2]])
            first,last=corner(start,up,join,16),corner(up,join,end,16)
            pieces=[segment([start,first[0]]),segment(first),segment([first[-1],last[0]]),segment(last),segment([last[-1],end])]
            notes='Vertical launch, rising diagonal, retained city-well vertical'
        else:
            # The entire original carrier underside must clear the fixed
            # upper hatch at Y=-949 before the launch track turns. Its lowest
            # fork is 4.00993m below the foot frame: 86m of exact vertical rise
            # leaves 0.99m here. Keep the already reviewed fan endpoint and
            # all long rock-incline/cavity geometry unchanged.
            up=start+[0,96.,0]
            fan=start+[28 if v==0 else -28 if v==2 else 0,112.,-120.]
            # The unchanged original carrier retracts 64m after ejection.
            # A 100m terminal rise leaves 84m of pure vertical rail after
            # its 16m entry blend, keeping the whole lowered carrier captured.
            far=np.array([(-1130.,-1250.,-1370.)[v],75.,-1520.5-SOLES[v]])
            direction=far[[0,2]]-fan[[0,2]];offset=fan[[0,2]]-[30.,296.]
            t=(-offset@direction+math.sqrt((offset@direction)**2-(direction@direction)*(offset@offset-1900**2)))/(direction@direction)
            rock=fan.copy();rock[[0,2]]+=direction*t
            rock[1]+=math.tan(math.radians(12))*np.linalg.norm(direction*t)
            end=far+[0,100.,0]
            c1=corner(start,up,fan,10);c2=corner(up,fan,rock,20)
            c3=corner(fan,rock,far,24);c4=corner(rock,far,end,16)
            pieces=[segment([start,c1[0]]),segment(c1),segment([c1[-1],c2[0]]),segment(c2),
                segment([c2[-1],c3[0]]),segment(c3),segment([c3[-1],c4[0]]),segment(c4),segment([c4[-1],end])]
            notes='86m pure vertical clears the complete original carrier through the upper seal before rising fan; unchanged 12 degree rock incline and Hakone receiver'
        length=verify_segments(pieces)
        points=np.concatenate([sample(s['controls'],max(3,math.ceil(np.linalg.norm(np.ptp(s['controls'],axis=0))*1.5)+1)) for s in pieces])
        derivative=np.concatenate([sample((len(s['controls'])-1)*np.diff(s['controls'],axis=0),513) for s in pieces])
        assert (derivative[:,1]>0).all(),(v,bank,'Horizontal or descending launch tangent')
        assert all(np.all(np.diff(s['controls'],axis=0)[:,1]>0) for s in pieces),'Every Bezier control derivative must prove increasing Y'
        first_vector=np.array(pieces[0]['controls'][1])-pieces[0]['controls'][0]
        assert first_vector[0]==0 and first_vector[2]==0 and first_vector[1]>0
        if bank==1:assert np.ptp(points[:,0])<1e-10 and np.ptp(points[:,2])<1e-10
        projection=np.sum(derivative[:,1:]**2,axis=1)/np.sum(derivative**2,axis=1)
        assert projection.min()>=.01
        key=f'unit{v}/bank{bank}';POINTS[key]=points
        CASES.append(dict(id=key,variant=v,bank=bank,intent=('geofront','surface','hakone')[bank-1],
            body_world_quaternion_xyzw=[0,1,0,0],foot_start=start.tolist(),foot_end=end.tolist(),
            initial_exact_vertical_metres=float(first_vector[1]),length_metres=length,
            min_upward_tangent=float(np.min(derivative[:,1]/np.linalg.norm(derivative,axis=1))),
            centre_curve=dict(segments=pieces),notes=notes))
candidates=[];keys=list(POINTS)
for i,k in enumerate(keys):
    a=POINTS[k]
    for other in keys[i+1:]:
        b=POINTS[other];tree=cKDTree(b/np.array([34.,68.,34.]))
        hits=tree.query_ball_point(a/np.array([34.,68.,34.]),1,p=np.inf)
        n=sum(map(len,hits))
        if n:candidates.append(dict(a=k,b=other,pairs=n,first_a=a[next(j for j,h in enumerate(hits) if h)].tolist()))
cavity=[]
for case in CASES:
    if case['bank']!=3:continue
    p=POINTS[case['id']];r=np.linalg.norm(p[:,[0,2]]-[30,296],axis=1);inside=r<=1830
    max_top=float(np.max(p[inside,1]+63))
    cavity.append(dict(route=case['id'],highest_body_and_margin_y_inside_dome_radius1830=max_top,
        conservative_dry_geology_ceiling_y=-500,clearance=float(-500-max_top)))
    assert max_top<-500
doc=dict(schema='projectseele.complete.monotone-ascent-spatial-candidate.v1',world_written=False,installable=False,
    proposed_additional_hangar_terminal_bank_dy=-DROP,proposed_dimension_min_y=-1344,
    unchanged=['pyramid and office elevations','HQ station','surface city','original surface wells','original bay/ramp relative shape','bank spacing48','co-oriented southwest lake'],
    cases=CASES,conservative_pair_candidates=candidates,cavity_head_envelope_bound=cavity,
    status='Root spatial candidate; exact all-source/shell/retained-facility review required before moving any further facility')
(OUT/'MONOTONE_ASCENT_CANDIDATE.json').write_text(json.dumps(doc,indent=2),'utf8')
print(json.dumps(dict(routes=len(CASES),additional_drop=DROP,aabb_candidates=candidates,cavity_bounds=cavity)),flush=True)
