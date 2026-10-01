"""Read-only ownership, existing alternatives and view occlusion of three crossways."""
from pathlib import Path
from collections import deque,Counter
import json
import numpy as np
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from query_blocks import AIR
from plan_tv_cage_cameras_r44 import project

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/hangar_machinery/tv_shoulder_shells_v1'


def main():
    w=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW');w.box((-64,-448,-296),(128,-348,-190));w.load();g=Geometry(w)
    cameras=json.loads((OUT/'cameras.json').read_text(encoding='utf8'))
    rows=[];native_cases=[]
    for variant,cx in enumerate((-12,30,72)):
        component=[];states=Counter()
        for x in range(cx-17,cx+18):
            for z in range(-264,-260):
                for y in range(-399,-392):
                    state=w.get(x,y,z)
                    if state and state.partition('[')[0] not in AIR|{'projectseele:lcl'}:
                        component.append({'position':[x,y,z],'state':state});states[state]+=1
        lo,hi=cx-20,cx+20
        nodes=set()
        for x in range(lo,hi+1):
            for z in range(-274,-213):
                if g.standing((x,-394,z))['status']=='STATIC_STANDING':nodes.add((x,z))
        # The two actual side-gallery front stations, not arbitrary new ports.
        start,end=(cx-18,-258),(cx+18,-258)
        def route(mask,start_at=start,end_at=end):
            search=nodes-mask
            if start_at not in search or end_at not in search:return None
            previous={start_at:None};queue=deque([start_at])
            while queue:
                q=queue.popleft()
                if q==end_at:
                    path=[]
                    while q is not None:
                        datum=g.standing((q[0],-394,q[1]))['measured_standing_y']
                        path.append([q[0]+.5,datum,q[1]+.5]);q=previous[q]
                    return path[::-1]
                for d in ((1,0),(-1,0),(0,1),(0,-1)):
                    p=q[0]+d[0],q[1]+d[1]
                    if p in search and p not in previous and g.edge_clear((q[0],-394,q[1]),(p[0],-394,p[1])):
                        previous[p]=q;queue.append(p)
            return None
        mask={(x,z) for x in range(cx-17,cx+18) for z in range(-264,-260)}
        before,alternative=route(set()),route(mask)
        column_checks=[]
        for z in (-267,-266,-265):
            checked=[g.standing((x,-394,z)) for x in range(cx-18,cx+19)]
            column_checks.append({'z':z,'all_37_columns':checked,'all_static_standing':all(c['status']=='STATIC_STANDING' for c in checked)})
            for reverse in (False,True):
                lane=route(mask,(cx+18 if reverse else cx-18,z),(cx-18 if reverse else cx+18,z))
                assert lane,('Existing three-row alternative is disconnected',variant,z,reverse)
                native_cases.append({'id':f'r44/tv/front_alternative/{variant}/row_{z}/'+('reverse' if reverse else 'forward'),
                    'path':lane,'actual_floor_source':'native measured collision shapes; old crossway temporarily masked in plan only',
                    'required_state':'crossway candidate not applied; repeat after complete retirement, actual mechanical and MTR state changes, and cold reload'})
        interactions=[]
        for action,z in (('prepare',-254),('status',-252),('cancel',-250)):
            approach=(cx-18,z)
            for seed in (start,end):
                p=route(mask,seed,approach);assert p,(variant,action,seed)
                interactions.append({'action':action,'actual_button':[cx-19,-393,z],'approach':[cx-17.5,-394,z+.5],
                                     'route_from_actual_side_gallery':p,'native_use':'PENDING original named control interaction'})
        for side in (-1,1):
            target=(cx+side*3,-221)
            for seed in (start,end):
                p=route(mask,seed,target)
                interactions.append({'action':'existing_rear_boarding_approach','side':side,
                    'existing_hatch_reference':[cx+.5,-392.8,-223.5],'route_from_actual_side_gallery':p,
                    'native_use':'PENDING canonical capsule, boarding bridge and actual collision in every state'})
        rows.append({'variant':variant,'whole_original_component_bounds':[[cx-17,-399,-264],[cx+17,-393,-261]],
            'nonfluid_members':component,'members_by_complete_state':dict(states),
            'existing_side_gallery_station_pair':[start,end],'existing_static_shape_path':before,
            'path_if_whole_front_crossway_removed':alternative,
            'three_complete_front_alternative_rows':column_checks,'all_actual_control_and_rear_boarding_routes':interactions,
            'interpretation':'Measured existing-floor alternative only; no new endpoint, construction licence or native walk pass',
            'retirement_status':'NOT_PROPOSED until complete alternative, actual staff/control access, all equipment states and native full-width paths pass'})
    front=cameras[1];eye=np.asarray(front['position'])+[0,1.62,0]
    head_box=[-396.56427001953125,-384.9036865234375]
    levels=[]
    for y in (-399.,-397.,-396.5,-395.,-394.):
        points=[[30.5,y,-239.5],[30.5,y,-258.5]]
        levels.append({'water_surface_y':y,'depth_above_current_minus399_m':y+399,
            'projected_effective_uv':project(points,eye,front['yaw'],front['pitch'],front['fovDegrees']).tolist(),
            'head_chin_box_to_water_m':head_box[0]-y,'actual_crew_feet_freeboard_m':-394-y,
            'canonical_docked_capsule_lowest_y':-396.2718249709381,
            'docked_capsule_freeboard_m':-396.2718249709381-y})
    report={'world_write_performed':False,'crossways':rows,'lens':front,
        'wet_surface_same_camera_analysis':levels,'current_actual_lcl_surface_y':-399,
        'lcl_changes_proposed':False,'reference_limit':'TV purple liquid is used solely for geometry, never for the requested orange-red material',
        'decision':'Retain the actual four-metre personnel crossways pending a verified replacement. Their floor also masks the low beam rim from the legal front lens. Current 44-layer LCL, actor dimensions, sloped shoulder aprons and front machinery must be reviewed together; camera fitting alone cannot pass the TV composition.',
        'native_passed':False,'visual_passed':False}
    (OUT/'crossway_and_wet_surface_contract.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    (OUT/'front_alternative_native_cases.json').write_text(json.dumps(native_cases,indent=2),encoding='utf8')
    print(json.dumps({'crossways':[{'variant':r['variant'],'members':len(r['nonfluid_members']),
        'three_complete_clear_rows':all(c['all_static_standing'] for c in r['three_complete_front_alternative_rows']),
        'before_nodes':len(r['existing_static_shape_path'] or []),'alternative_nodes':len(r['path_if_whole_front_crossway_removed'] or [])} for r in rows],
        'native_route_cases':len(native_cases),'lcl_changed':False,'native_passed':False}))


if __name__=='__main__':main()
