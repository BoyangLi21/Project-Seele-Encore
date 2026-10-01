"""Three actual scene cameras with measured eye cells and visible section gates."""
from pathlib import Path
import argparse,json,math
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--after-v3',action='store_true');a=p.parse_args();assert not a.output.exists()
    scenes=[('installed_cavern_woodland',[-725.5,-474,649.5],[-699,-473,681],
        [-770,-502,610],[-650,-444,730],'Actual installed first-prefix native woodland; full landscape quality remains pending.'),
        ('surface_meadow_before_v2',[-2318.5,270,817.5],[-2312,207,840],
        [-2370,175,770],[-2260,295,895],'Actual existing surface topography before the new surface calibration; none of the first3573 planted cells were on the surface.'),
        ('viaduct_understory_before_v2',[-1010,66,281],[-1000,80,302],
        [-1070,30,238],[-945,115,353],'Actual founded viaduct and eligible natural ground below it, before v2 native under-bridge planting.')]
    world=MeasuredWorld(WORLD)
    for name,at,target,lo,hi,meaning in scenes:world.box(tuple(lo),tuple(hi))
    world.load();views=[];proof=[]
    excluded={'minecraft:barrier','minecraft:light','minecraft:water','projectseele:lcl','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:poppy','minecraft:dandelion','minecraft:snow'}
    for name,at,target,lo,hi,meaning in scenes:
        if a.after_v3:
            name=name.replace('_before_v2','_after_native_v3')
            if name.startswith('surface_meadow'):
                soil=[y for y in range(175,270) if (world.get(math.floor(at[0]),y,math.floor(at[2])) or '').split('[')[0] in {'minecraft:grass_block','minecraft:dirt','minecraft:podzol'}]
                assert soil,'No measured natural camera ground'
                at=[at[0],max(soil)+1,at[2]]
            meaning='Actual construction world after the 4660-cell/159-section second native ecology prefix, plus original first-prefix woodland. Installation is distinct from landscape approval.'
        eye=np.asarray(at)+[0,1.62,0];assert world.block(eye) in AIR,(name,eye,world.block(eye))
        delta=np.asarray(target)-eye;yaw=math.degrees(math.atan2(-delta[0],delta[2]));pitch=-math.degrees(math.atan2(delta[1],math.hypot(delta[0],delta[2])))
        ya,pi=map(math.radians,(yaw,pitch));forward=np.array([-math.sin(ya)*math.cos(pi),-math.sin(pi),math.cos(ya)*math.cos(pi)])
        right=np.array([math.cos(ya),0,math.sin(ya)]);up=np.cross(forward,right);sections={};misses=0
        for u in np.linspace(-1,1,33):
            for v in np.linspace(-1,1,19):
                direction=forward+right*u*(16/9)*math.tan(math.radians(35))+up*v*math.tan(math.radians(35));direction/=np.linalg.norm(direction)
                previous=None;hit=False
                for distance in np.arange(.5,105,.5):
                    q=tuple(np.floor(eye+direction*distance).astype(int))
                    if q==previous:continue
                    previous=q;state=world.block(q)
                    if state is None:break
                    block=state.split('[')[0]
                    if block in AIR or block in excluded or 'glass' in block or block.endswith(('_flower','_tulip')):continue
                    # These gates require an actually non-air native section;
                    # this is no collision-shape or complete occlusion claim.
                    sections.setdefault(tuple(int(x)//16 for x in q),tuple(map(int,q)));hit=True;break
                if not hit:misses+=1
        assert sections,(name,'No measured visible ground/vegetation/structure section')
        view=dict(file='r44_ecology_'+name+'.png',position=at,yaw=yaw,pitch=pitch,fovDegrees=70,
            warmupTicks=320,requiredSections=[list(q) for k,q in sorted(sections.items())],action='daytime:6000')
        views.append(view);proof.append(dict(file=view['file'],eye_state=world.block(eye),position=at,target=target,
            measured_boxes=[lo,hi],required_non_air_sections=len(sections),sampled_rays=33*19,rays_leaving_measurement_or_into_sky=misses,
            interpretation=meaning,world_written=False,actual_photo_captured=False,
            time_requirement='Root must set the primary world shared dayTime and verify GeoFront actual_day_time modulo24000=6000 with actual_fixed_time=-1; old custom-dimension setter was no-op.',
            gate_limit='Sampled first non-air sections for native render readiness; not a native collision or full occlusion proof. Actual framing and complete landscape image must be reviewed.'))
    a.output.mkdir(parents=True);(a.output/'itinerary.json').write_text(json.dumps(views,ensure_ascii=False,indent=2),'utf8')
    (a.output/'scope.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf8')
    print('Current non-solid eyes3; required sections',[(q['file'],q['required_non_air_sections']) for q in proof])


if __name__=='__main__':main()
