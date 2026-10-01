"""Read-only physically clear comparison cameras and honest projection residuals."""
from pathlib import Path
import json, math
import numpy as np
from scipy.optimize import least_squares
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/hangar_machinery/tv_shoulder_shells_v1'
SOURCE=ROOT/'artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2'


def direction(eye,target):
    d=np.asarray(target)-np.asarray(eye)
    return math.degrees(math.atan2(-d[0],d[2])),math.degrees(math.atan2(-d[1],np.linalg.norm(d[[0,2]])))


def project(points,eye,yaw,pitch,fov,aspect=556/422):
    ya,pi=map(math.radians,(yaw,pitch))
    f=np.array([-math.sin(ya)*math.cos(pi),-math.sin(pi),math.cos(ya)*math.cos(pi)])
    r=np.array([math.cos(ya),0,math.sin(ya)]);u=np.cross(f,r)
    q=np.asarray(points)-eye;depth=q@f;t=math.tan(math.radians(fov)/2)
    return np.stack([.5+(q@r)/(2*t*aspect*depth),.5-(q@u)/(2*t*depth)],axis=-1)


def clear_camera(w,g,position):
    feet=np.asarray(position);lo=feet+[-.31,0,-.31];hi=feet+[.31,1.83,.31]
    hit=[]
    for x in range(math.floor(lo[0]),math.floor(hi[0])+1):
        for y in range(math.floor(lo[1]),math.floor(hi[1])+1):
            for z in range(math.floor(lo[2]),math.floor(hi[2])+1):
                state=w.get(x,y,z);boxes=g.boxes(state)
                if boxes is None:hit.append({'position':[x,y,z],'state':state,'unknown':True});continue
                for b in boxes:
                    low=np.array(b[:3])+[x,y,z];high=np.array(b[3:])+[x,y,z]
                    if np.all(hi>low)&np.all(lo<high):hit.append({'position':[x,y,z],'state':state})
    return hit


def optical_ray(w,g,eye,target):
    d=np.asarray(target)-eye;length=np.linalg.norm(d);d/=length
    seen=None
    for distance in np.arange(.15,length-.5,.10):
        p=eye+d*distance;q=tuple(map(int,np.floor(p)))
        if q==seen:continue
        seen=q;state=w.block(q)
        if state is None:return {'position':q,'state':state,'unknown':True}
        name=state.partition('[')[0]
        if name in AIR|{'minecraft:barrier','minecraft:light','projectseele:lcl','minecraft:water'} or 'glass' in name:continue
        boxes=g.boxes(state)
        if boxes==[[0.,0.,0.,1.,1.,1.]]:return {'position':q,'state':state}
    return None


def main():
    w=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW');w.box((-64,-448,-296),(128,-348,-190));w.load();g=Geometry(w)
    actors=json.loads((SOURCE/'actual_render_body_surfaces_triangles.json').read_text(encoding='utf8'))['actors']
    frames=json.loads((SOURCE/'semantic_frame.json').read_text(encoding='utf8'))['bays']
    a=actors['1'];head=np.asarray(a['parts']['head']['world_bounds']).reshape(2,3)
    # These are observed part-box extrema, not invented exact chin/crown points.
    points=np.array([[30.5,head[1,1],head[:,2].mean()],[30.5,head[0,1],head[:,2].mean()],
        [22.30,-388.96,-238.5],[38.70,-388.96,-238.5],
        [19.75,-392.20,-259.175],[41.25,-392.20,-259.175],[30.5,-394.80,-259.175]])
    target=np.array([[(373-94)/556,32/422],[(373-94)/556,215/422],
        [(230-94)/556,135/422],[(514-94)/556,138/422],
        [(214-94)/556,241/422],[(538-94)/556,241/422],[(373-94)/556,286/422]])
    def residual(p):return (project(points,np.array([30.5,p[0],p[1]]),0,p[2],p[3])-target).reshape(-1)
    blocked_fit=least_squares(residual,[-379,-294,18,40],bounds=([-394,-295,-10,30],[-365,-267,35,80]))
    # The numerically best lens sits beyond the measured solid Z=-275 face.
    # Keep it as a rejected comparison, and fit in front of that actual face.
    fitted=least_squares(residual,[-375,-273.5,25,60],bounds=([-394,-273.6,-10,30],[-365,-267,50,110]))
    fitted.x[3]=round(float(fitted.x[3]))
    eye=np.array([30.5,fitted.x[0],fitted.x[1]]);position=eye-[0,1.62,0]
    views=[];evidence=[]
    for variant in (0,1,2):
        shift=np.array([(variant-1)*42,0,0]);p=position+shift
        view={'file':f'r44_tv_cage_front_{variant}.png','position':p.tolist(),'yaw':0.,
            'pitch':float(fitted.x[2]),'fovDegrees':int(fitted.x[3]),'warmupTicks':360,
            'requiredSections':[[int(frames[variant]['eva_feet'][0]),-395,-261],
                [int(frames[variant]['eva_feet'][0]),-374,-246],
                [int(frames[variant]['eva_feet'][0]),-355,-246]],
            'role':'tv_cage effective-frame comparison; camera floats in existing open observation volume'}
        hits=clear_camera(w,g,p)
        rays=[optical_ray(w,g,p+[0,1.62,0],q+shift) for q in points]
        evidence.append({'file':view['file'],'body_collision_hits':hits,'landmark_opaque_ray_hits':rays})
        assert not hits,('Comparison camera crosses measured solid',view,hits)
        assert not any(rays[:6]),('Principal actor/beam comparison is hidden behind real opaque structure',view,rays)
        if rays[6]:
            view['knownOcclusion']='Existing four-metre front personnel crossway masks the beam lower rim in this front comparison. Upper beam and all head/shoulder landmarks have clear measured rays.'
        views.append(view)
    rear_eye=np.array([44.5,-376.1,-220.5]);socket=np.asarray(frames[1]['socket']['origin'])
    yaw,pitch=direction(rear_eye,socket)
    rear={'file':'r44_tv_cage_rear_neck_1.png','position':(rear_eye-[0,1.62,0]).tolist(),
        'yaw':yaw,'pitch':pitch,'fovDegrees':58,'warmupTicks':360,
        'requiredSections':[[30,-395,-222],[30,-374,-228],[38,-355,-228]],
        'role':'user four original neck frames: above and behind right shoulder, canonical socket focus'}
    hits=clear_camera(w,g,rear['position']);assert not hits,(rear,hits)
    evidence.append({'file':rear['file'],'body_collision_hits':hits,'socket_opaque_ray_hit':optical_ray(w,g,rear_eye,socket)})
    views.append(rear)
    # Retain the existing user's side vantage with a narrower lens as a third
    # independent angle; the front comparison no longer hides behind its rail.
    side={'file':'r44_tv_cage_side_1.png','position':[48.5,-394.,-251.5],
        'yaw':56.309932474020215,'pitch':-8.880130903241223,'fovDegrees':58,'warmupTicks':360,
        'requiredSections':[[48,-395,-251],[26,-374,-246],[38,-355,-246]],'role':'retained original lateral working-gallery camera'}
    hits=clear_camera(w,g,side['position']);assert not hits,(side,hits)
    evidence.append({'file':side['file'],'body_collision_hits':hits});views.append(side)
    (OUT/'cameras.json').write_text(json.dumps(views,indent=2),encoding='utf8')
    report={'reference_valid_pixels':[94,0,650,422],'reference_effective_aspect':556/422,
        'native_crop_for_1280x720':[166,0,1114,720],'projection_source':'Actual actor head world bounds, authored shell and beam vertices; box extrema are approximate visual landmarks',
        'fitted_eye':eye.tolist(),'fov_degrees':float(fitted.x[3]),'pitch_degrees':float(fitted.x[2]),
        'landmark_reference_uv':target.tolist(),'landmark_candidate_uv':project(points,eye,0,fitted.x[2],fitted.x[3]).tolist(),
        'rms_effective_frame_error':float(np.sqrt(np.mean(residual(fitted.x)**2))),
        'rejected_better_projection':{'eye':[30.5,float(blocked_fit.x[0]),float(blocked_fit.x[1])],
            'rms':float(np.sqrt(np.mean(residual(blocked_fit.x)**2))),
            'reason':'Measured Z=-275 structural face blocks every landmark; not a permissible inspection lens'},
        'evidence':evidence,'world_write_performed':False,'native_passed':False,'visual_passed':False,
        'limit':'Reference geometry and actual EVA head/forebeam ratios cannot all be made identical by a lens change. Residual remains an art failure to evaluate, not a claimed TV match. Current static world does not include this mesh; native visibility still required.'}
    (OUT/'camera_contract.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({'views':views,'rms':report['rms_effective_frame_error'],'evidence':evidence}))


if __name__=='__main__':main()
