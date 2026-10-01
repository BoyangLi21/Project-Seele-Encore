"""Existing worker contact view and copied upper observer gallery viewpoints.

Both are grounded on the measured retained floor, with whole human footprints.
No camera is placed on air and no support is removed for a head-only screenshot.
"""
from pathlib import Path
import json,math
import numpy as np
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from plan_tv_cage_cameras_r44 import direction,clear_camera,optical_ray,project

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/hangar_machinery/tv_role_views_v1'
BODY=ROOT/'artifacts/rebuild_r44/space_photos/installed_maps_hakone_and_tv_fullbody/20261001_045405/r44_hangar_body_surfaces.json'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    actors=json.loads(BODY.read_text('utf8'))['actors']
    contacts=json.loads((ROOT/'artifacts/rebuild_r44/facility_transit_r44/hangar_shoulder_contact_v3/contacts.json').read_text('utf8'))['contacts']
    w=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW');w.box((-64,-448,-296),(128,-348,-190));w.load();g=Geometry(w)
    views=[];proof=[]
    for variant,cx in enumerate((-11.5,30.5,72.5)):
        row=next(c for c in contacts if c['variant']==variant and c['side']==1)
        target=np.asarray(row['contact_centre_fixed_gantry_local'])+[cx,-442.96,-239.5]
        position=np.array([cx+18,-394,-251.5]);yaw,pitch=direction(position+[0,1.62,0],target)
        views.append({'file':f'r44_tv_worker_contact_{variant}.png','position':position.tolist(),
            'yaw':yaw,'pitch':pitch,'fovDegrees':58,'warmupTicks':360,
            'requiredSections':[[math.floor(cx+18),-395,-251],[math.floor(cx+7),-391,-238],[math.floor(cx+14),-392,-244]],
            'role':'Original two-lane -394 worker deck, actual restraint installation and pad/ram inspection; not an upper-body observation claim'})
        position=np.array([cx,-367,-279.5]);target=np.array([cx,-389.4,-241.0]);yaw,pitch=direction(position+[0,1.62,0],target)
        views.append({'file':f'r44_tv_upper_observer_{variant}.png','position':position.tolist(),
            'yaw':yaw,'pitch':pitch,'fovDegrees':58,'warmupTicks':360,
            'requiredSections':[[math.floor(cx),-368,-279],[math.floor(cx),-384,-240],[math.floor(cx),-393,-258]],
            'role':'Retained copied -368 glass/structural public floor; feet -367 upper observation gallery, whole upper EVA and bay machinery'})
    for view in views:
        p=np.asarray(view['position']);foot=[]
        for dx in (-.299,0,.299):
            for dz in (-.299,0,.299):
                q=tuple(map(math.floor,p+[dx,0,dz]));standing=g.standing(q)
                assert standing['status']=='STATIC_STANDING',('Role camera not on a complete existing floor',view,q,standing)
                foot.append(standing)
        hit=clear_camera(w,g,p);assert not hit,('Role camera body enters original wall/structure',view,hit)
        variant=int(view['file'].split('_')[-1].split('.')[0]);a=actors[str(variant)]
        points=[]
        if 'worker' in view['file']:
            row=next(c for c in contacts if c['variant']==variant and c['side']==1)
            points=[(np.asarray(row['contact_centre_fixed_gantry_local'])+[a['x'],-442.96,a['z']]).tolist()]
        else:
            for name in ('head','torso_upper','pylon_l','pylon_r'):
                bb=np.asarray(a['parts'][name]['world_bounds']).reshape(2,3);points.append(bb.mean(0).tolist())
        rays=[optical_ray(w,g,p+[0,1.62,0],t) for t in points]
        proof.append({'file':view['file'],'whole_grounded_human_footprint':foot,'solid_camera_hits':hit,
            'actual_job_target_world':points,'native_block_optical_first_hits':rays,
            'pixel_projection':project(points,p+[0,1.62,0],view['yaw'],view['pitch'],view['fovDegrees'],aspect=16/9).tolist(),
            'limit':'Actual authored moving meshes and body self-occlusion remain native photo checks; block rays alone do not prove pad-visible or complete body view'})
    (OUT/'cameras.json').write_text(json.dumps(views,indent=2),encoding='utf8')
    (OUT/'contract.json').write_text(json.dumps({'world_write_performed':False,'native_passed':False,'visual_passed':False,
        'actual_body_source':str(BODY),'original_upper_authority':'R20 copies SOURCE X-40..104/Y-467..-350/Z-145..-70 to DZ-144, preserving original upper observation rooms/floor; this script does not declare new rooms from standing tests',
        'proof':proof},indent=2),encoding='utf8')
    print(json.dumps({'views':len(views),'block_occlusions':[{p['file']:p['native_block_optical_first_hits']} for p in proof],
        'grounded_footprints':len(proof)*9,'native_passed':False}))


if __name__=='__main__':main()
