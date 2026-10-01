"""Require sampled visible pressure-shell sections, rather than three distant anchors."""
from pathlib import Path
import argparse, json, math
import numpy as np
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2/root_surface_views.json'
OUT=ROOT/'artifacts/rebuild_r44/hangar_machinery/visible_shell_photo_contract'
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--itinerary',type=Path,default=BASE);parser.add_argument('--out',type=Path,default=OUT);args=parser.parse_args()
    views=json.loads(args.itinerary.read_text('utf8'));world=MeasuredWorld(WORLD)
    world.box((-64,-448,-296),(128,-348,-190));world.load();geometry=Geometry(world)
    full=[[0.,0.,0.,1.,1.,1.]];records=[]
    # R44 inspection explicitly uses and records a 70-degree vertical field.
    # Visibility is checked against measured opaque cubes;
    # translucent liquid/glazing and invisible gate barriers cannot hide walls.
    for view in views:
        fov=view.get('fovDegrees',70);assert 30<=fov<=110
        eye=np.asarray(view['position'],dtype=float)+[0,1.62,0]
        yaw,pitch=map(math.radians,(view['yaw'],view['pitch']))
        forward=np.array([-math.sin(yaw)*math.cos(pitch),-math.sin(pitch),math.cos(yaw)*math.cos(pitch)])
        right=np.array([math.cos(yaw),0,math.sin(yaw)]);up=np.cross(forward,right)
        sections={};misses=0;unknown=set()
        for u in np.linspace(-1,1,65):
            for v in np.linspace(-1,1,39):
                tangent=math.tan(math.radians(fov/2))
                direction=forward+right*u*(16/9)*tangent+up*v*tangent;direction/=np.linalg.norm(direction)
                previous=None;hit=False
                for distance in np.arange(.4,155,.4):
                    q=tuple(np.floor(eye+direction*distance).astype(int))
                    if q==previous:continue
                    previous=q;state=world.block(q)
                    if state is None:break
                    name=state.partition('[')[0]
                    if name in AIR or name in {'minecraft:barrier','minecraft:light','minecraft:water','projectseele:lcl'} or 'glass' in name:continue
                    boxes=geometry.boxes(state)
                    if boxes is None:unknown.add(state);continue
                    if boxes!=full:continue
                    key=tuple(int(x)//16 for x in q);sections.setdefault(key,tuple(map(int,q)));hit=True;break
                if not hit:misses+=1
        assert not unknown,('Unknown visible material needs classification',sorted(unknown))
        for q in view['requiredSections']:sections.setdefault(tuple(x//16 for x in q),tuple(q))
        view['requiredSections']=[list(v) for k,v in sorted(sections.items())]
        view['warmupTicks']=max(view.get('warmupTicks',0),300)
        records.append(dict(file=view['file'],vertical_fov_degrees=fov,required_section_count=len(sections),rays=65*39,
                            rays_leaving_measured_enclosure=misses,unknown_states=[],
                            limit='Sampled measured opaque shell only; actual complete image and moving entity submissions still require visual review'))
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'itinerary.json').write_text(json.dumps(views,indent=2),'utf8')
    (args.out/'contract.json').write_text(json.dumps(records,indent=2),'utf8')
    print('Visible-shell section gates:',[(r['file'],r['required_section_count']) for r in records],flush=True)


if __name__=='__main__':main()
