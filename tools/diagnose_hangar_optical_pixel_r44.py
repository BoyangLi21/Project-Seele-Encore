"""Read-only voxel-ray attribution of the old S1 upper-right blue patch.

The old capture did not record effective FOV, so both setting70 and flight77
are retained. Dynamic rendered leaves and shaders require a native witness;
this deliberately does not call an unblocked voxel ray a real roof hole.
"""
from pathlib import Path
import hashlib,json,math
import numpy as np
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1]
SHOT=ROOT/'artifacts/rebuild_r44/space_photos/fixed_hangar_gpu_shader_profile/20261001_005524'
OUT=ROOT/'artifacts/rebuild_r44/hangar_machinery/blue_patch_attribution_v1'


def slab(eye,direction,lo,hi):
    tiny=np.abs(direction)<1e-10
    if np.any(tiny&((eye<lo)|(eye>hi))):return None
    d=np.where(tiny,1e-10,direction)
    a=(lo-eye)/d;b=(hi-eye)/d;near=max(0,float(np.minimum(a,b).max()));far=float(np.maximum(a,b).min())
    return near if far>=near else None


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    view=json.loads((SHOT/'itinerary.json').read_text('utf8'))[0]
    eye=np.asarray(view['position'])+[0,1.62,0];yaw,pitch=map(math.radians,(view['yaw'],view['pitch']))
    forward=np.array([-math.sin(yaw)*math.cos(pitch),-math.sin(pitch),math.cos(yaw)*math.cos(pitch)])
    right=np.array([math.cos(yaw),0,math.sin(yaw)]);up=np.cross(forward,right)
    rays=[];w=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW')
    for fov in (70,77):
        for px,py in ((1123,264),(1138,260),(1145,255),(1120,254),(1134,269)):
            u=(px+.5)/1280*2-1;v=1-(py+.5)/720*2;t=math.tan(math.radians(fov)/2)
            direction=forward+right*u*(16/9)*t+up*v*t;direction/=np.linalg.norm(direction)
            cells=list(dict.fromkeys(tuple(map(int,np.floor(eye+direction*dist))) for dist in np.arange(.10,350,.18)))
            for q in cells:w.around(q,0)
            rays.append({'fov':fov,'pixel':[px,py],'direction':direction,'cells':cells})
    w.load();g=Geometry(w);rows=[]
    for ray in rays:
        transparent=[];hit=None;unknown=None
        for q in ray['cells']:
            state=w.block(q)
            if state is None:unknown={'position':q,'reason':'Actual chunk not fully known'};break
            name=state.partition('[')[0]
            if name in AIR|{'minecraft:light','projectseele:lcl','minecraft:water'}:continue
            if name=='minecraft:barrier' or 'glass' in name:
                transparent.append({'position':q,'state':state});continue
            boxes=g.boxes(state)
            if boxes is None:unknown={'position':q,'state':state,'reason':'No actual native shape'};break
            points=[]
            for box in boxes:
                value=slab(eye,ray['direction'],np.array(box[:3])+q,np.array(box[3:])+q)
                if value is not None:points.append(value)
            if points:
                distance=min(points);hit={'position':q,'state':state,'distance_m':distance,
                    'actual_block_surface_world':(eye+ray['direction']*distance).tolist()};break
        rows.append({'fov':ray['fov'],'pixel':ray['pixel'],'direction':ray['direction'].tolist(),
            'first_native_opaque_shape':hit,'transparent_block_interfaces':transparent,'unknown':unknown,
            'voxel_ray_leaves_scope':hit is None and unknown is None})
    report={'source_photo_sha256':hashlib.sha256((SHOT/'r44_fixed_hangar_profile.png').read_bytes()).hexdigest(),
        'actual_camera_eye':eye.tolist(),'source_setting_fov':70,'old_effective_fov':'UNRECORDED;70/77 both diagnostic candidates',
        'current_world_read_only':str(w.world),'rays':rows,'world_write_performed':False,
        'decision':'No roof fill authorised by this pixel. First actual native surfaces are candidates; original runtime leaf progress/rendered triangles and old effective lens/shader are required for exact pixel causality.'}
    (OUT/'contract.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({'rays':[{'fov':r['fov'],'pixel':r['pixel'],'hit':r['first_native_opaque_shape'],
        'transparent_count':len(r['transparent_block_interfaces']),'unknown':r['unknown']} for r in rows]}))


if __name__=='__main__':main()
