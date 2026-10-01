"""Complete existing -367 upper gallery extension past its preserved sight-blocking beam.

The commissioned upper layer and r25-west-observation real native port are the
authority. Moves the entire front glazing, extends floor/foundation/ceiling and
joins all three bays, while preserving original beam, lift domain and every BE.
Exact forward/inverse candidate only; never calls world apply.
"""
from pathlib import Path
from collections import deque,Counter
import copy,hashlib,json,math
import numpy as np
import regional_voxels as v
from query_blocks import AIR,iter_block_entities
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from plan_tv_cage_cameras_r44 import direction,clear_camera,optical_ray
from hangar_tv_design_r44 import FULL_CUBE
from tv_upper_observation_design_r44 import members as source_members

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
ART=ROOT/'artifacts/rebuild_r44'
OUT=ART/'facility_transit_r44/tv_upper_observation_v1'
BODY=ART/'space_photos/installed_maps_hakone_and_tv_fullbody/20261001_045405/r44_hangar_body_surfaces.json'
FLOOR='projectseele:nerv_floor_panel';STRUCT='projectseele:nerv_structural_panel'
GLASS='projectseele:clear_glass';LIGHT='projectseele:nerv_strip_light'
STEP='minecraft:polished_blackstone_slab[type=bottom,waterlogged=false]'
FRONT_X=(-33,93);OLD_FACE=-275;NEW_FACE=-267;FEET=-367


def lift_negative(q):
    return -33<=q[0]<=-25 and -376<=q[1]<=-360 and -284<=q[2]<=-274


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if list(OUT.glob('*/applied_*/receipt.json')):raise RuntimeError('Applied gallery revision is immutable')
    lo,hi=(-43,-448,-290),(105,-350,-212)
    w=MeasuredWorld(WORLD);w.box(lo,hi);w.load();g=Geometry(w)
    tags={q:copy.deepcopy(t) for q,t in iter_block_entities(WORLD,v.DIM,(-43,-379,-290),hi)}
    actors=json.loads(BODY.read_text('utf8'))['actors']
    frames=json.loads((ART/'facility_transit_r44/hangar_tv_calibration_v2/semantic_frame.json').read_text('utf8'))['bays']
    actual_lifts=json.loads((ART/'lift_lifecycle/20261001_015604/result.json').read_text('utf8'))
    port=next(r for r in actual_lifts['resolved_interfaces'] if r['lift']=='r25-west-observation' and r['approach_walk_y']==-367)
    assert port['actual_client_exit'] if 'actual_client_exit' in port else True
    start=tuple(map(math.floor,port['approach']))
    assert g.standing(start)['status']=='STATIC_STANDING',('Existing original real lift approach no longer standing',port,g.standing(start))
    changes={};protected=[];dependencies={};beam=[]
    allowed={STRUCT,FLOOR,GLASS,LIGHT,'projectseele:nerv_wall_panel','projectseele:nerv_machine_edge',
        'projectseele:nerv_shaft_panel','minecraft:light_gray_stained_glass'}
    for state in (FLOOR,STRUCT,GLASS,LIGHT):assert g.boxes(state)==FULL_CUBE,('Known full native public structure required',state)
    assert g.boxes(STEP)==[[0.,0.,0.,1.,.5,1.]],('Actual half-step support required',STEP,g.boxes(STEP))
    def put(q,after,purpose):
        before=w.block(q)
        if before is None:raise RuntimeError(('Unknown whole original gallery member',q))
        if lift_negative(q):protected.append({'position':q,'state':before,'reason':'Complete original native elevator/approach domain'});return
        if q in tags:raise RuntimeError(('Original whole device cannot be silently relocated',q,tags[q].snbt()))
        if before==after:return
        if before.partition('[')[0] not in AIR|allowed:raise RuntimeError(('Other original owner in gallery revision',q,before,purpose))
        if q in changes and changes[q][0]!=after:raise RuntimeError(('Conflicting complete gallery member',q))
        changes[q]=(after,purpose)
    # Preserve the entire current horizontal steel beam, not a camera-sized
    # cut. The new foundation meets its exact top at Y-369.
    for cx in (-12,30,72):
        for x in range(cx-18,cx+19):
            for y in range(-373,-368):
                q=(x,y,-271);state=w.block(q)
                if state and state.partition('[')[0] not in AIR:
                    beam.append({'position':q,'state':state});dependencies[q]=state
        assert any(r['position'][0]==cx and r['position'][1]==-370 for r in beam),('No actual retained transverse bearing',cx)
    # Clear5m-high old glass/wall plane as one complete internal frontage.
    # Its retained overhead header/roof atY-362 is joined by the new ceiling.
    for q,state,purpose in source_members():put(q,state,purpose)
    assert not any(q in changes for q in [tuple(r['position']) for r in beam]),'Preserved beam overwritten'
    before_get=w.get;after={q:s for q,(s,purpose) in changes.items()};w.get=lambda x,y,z:after.get((x,y,z),before_get(x,y,z))
    nodes=set()
    for x in range(-34,95):
        for z in range(-287,-267):
            if g.standing((x,FEET,z))['status']=='STATIC_STANDING':nodes.add((x,z))
    def route(a,b):
        if a not in nodes or b not in nodes:return None
        previous={a:None};queue=deque([a])
        while queue:
            q=queue.popleft()
            if q==b:
                path=[]
                while q is not None:path.append([q[0]+.5,FEET,q[1]+.5]);q=previous[q]
                return path[::-1]
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                target=q[0]+dx,q[1]+dz
                if target in nodes and target not in previous and g.edge_clear((q[0],FEET,q[1]),(target[0],FEET,target[1])):
                    previous[target]=q;queue.append(target)
        return None
    rows=[];cases=[];views=[];vision=[]
    for z in range(-273,-268):
        # Full public rows cross all threebay joins; keep both directions.
        path=route((-32,z),(92,z));assert path,('Whole new width disconnected',z)
        rows.append({'z':z,'columns':125,'all_nine_point_native_standing':all((x,z) in nodes for x in range(-32,93))})
        assert rows[-1]['all_nine_point_native_standing'],('New row has an unreviewed gap',rows[-1])
        for reverse in (False,True):cases.append({'id':f'r44/upper_observer/full_width/{z}'+('/return' if reverse else ''),'path':path[::-1] if reverse else path})
    for variant,cx in enumerate((-11.5,30.5,72.5)):
        def actual_landmarks(position):
            result=[]
            for name in ('head','torso_upper','pylon_l','pylon_r'):
                part=actors[str(variant)]['parts'][name];tri=np.array([t['world_vertices'] for t in part['top_band_triangles']])
                bb=np.asarray(part['world_bounds']).reshape(2,3);middle=bb.mean(0)
                centroids=tri.mean(1);normal=np.array([t['world_outward_normal'] for t in part['top_band_triangles']])
                toward=position+[0,1.62,0]-centroids;toward/=np.linalg.norm(toward,axis=1)[:,None]
                facing=np.sum(normal*toward,axis=1)>.10;assert facing.any(),('No actual camera-facing submitted armour facets',variant,name)
                chosen=centroids[np.flatnonzero(facing)[np.argmin(np.linalg.norm(centroids[facing]-middle,axis=1))]]
                result.extend([chosen,np.asarray(part['top_surface_points'][0])])
            return result
        options=[]
        # The stand is a continuous public floor. Evaluate its whole authored
        # frontage, retaining original actual armour points/beam occlusions;
        # people may change view position, actors and support never move.
        for offset in [0,*[s*i for i in range(1,17) for s in (-1,1)]]:
            candidate=np.array([cx+offset,FEET+.5,-267.5]);points=actual_landmarks(candidate)
            ray_hits=[optical_ray(w,g,candidate+[0,1.62,0],p) for p in points]
            options.append((sum(bool(h) for h in ray_hits),abs(offset),candidate,points,ray_hits))
        best=min(options,key=lambda p:p[:2])
        supplement=min(options,key=lambda p:(sum(bool(a) and bool(b) for a,b in zip(best[4],p[4])),p[1]))
        assert not any(a and b for a,b in zip(best[4],supplement[4])),('Actual crown/front armour invisible from the complete authored stand',variant,[(p[2].tolist(),p[0]) for p in options])
        position,points,ray_hits=best[2:]
        target=np.array([cx,-389.4,-241.0]);yaw,pitch=direction(position+[0,1.62,0],target)
        q=tuple(map(math.floor,position));path=route((start[0],start[2]),(q[0],-269));assert path,('Original real lift port not connected to every observation bay',variant,start,q)
        path.extend([[float(position[0]),FEET,-268.5],position.tolist()])
        for dx in (-.299,0,.299):
            for dz in (-.299,0,.299):
                px,pz=position[0]+dx,position[2]+dz;bx,bz=math.floor(px),math.floor(pz)
                support=g.boxes(w.get(bx,-367,bz))
                assert any(b[0]<=px-bx<=b[3] and b[2]<=pz-bz<=b[5] and abs(-367+b[4]-position[1])<.001 for b in support),('Raised real stand lacks full footprint bearing',variant,px,pz,support)
        for reverse in (False,True):cases.append({'id':f'r44/upper_observer/real_lift_to_bay_{variant}'+('/return' if reverse else ''),'path':path[::-1] if reverse else path})
        hit=clear_camera(w,g,position);assert not hit,('Actual grounded observer intersects structure',variant,hit)
        vision.append({'variant':variant,'grounded_position':position.tolist(),'actual_body_landmarks_world':[p.tolist() for p in points],
            'block_optical_first_hits':ray_hits,'preserved_transverse_beam_now_behind_eye':True,
            'secondary_grounded_position':supplement[2].tolist(),'secondary_block_optical_first_hits':supplement[4],
            'every_required_actual_front_surface_and_crown_visible_from_real_stand':True,
            'single_position_clear_landmarks':8-best[0],'limit':'One retained crane/support occlusion is explicit. The adjacent real view position reveals the other crown; no beam is removed and no x-ray all-pixels visibility is claimed.'})
        views.append({'file':f'r44_tv_upper_observer_extended_{variant}.png','position':position.tolist(),'yaw':yaw,'pitch':pitch,
            'fovDegrees':58,'warmupTicks':360,'requiredSections':[[math.floor(cx),-368,-268],[math.floor(cx),-384,-240],[math.floor(cx),-370,-271]],
            'role':'Complete existing upper observation gallery extended past preserved beam, actual standing floor and real lift connection'})
        secondary=supplement[2];syaw,spitch=direction(secondary+[0,1.62,0],target)
        views.append({'file':f'r44_tv_upper_observer_extended_{variant}_other_crown.png','position':secondary.tolist(),
            'yaw':syaw,'pitch':spitch,'fovDegrees':58,'warmupTicks':360,'requiredSections':views[-1]['requiredSections'],
            'role':'Adjacent true raised-stand position reveals crown behind the preserved crane/support; existing head/chest remain in the same field'})
        secondary_path=route((start[0],start[2]),(math.floor(secondary[0]),-269));assert secondary_path
        secondary_path.extend([[float(secondary[0]),FEET,-268.5],secondary.tolist()])
        for reverse in (False,True):cases.append({'id':f'r44/upper_observer/other_crown_bay_{variant}'+('/return' if reverse else ''),'path':secondary_path[::-1] if reverse else secondary_path})
    for view in views:
        position=np.asarray(view['position']);assert not clear_camera(w,g,position)
        for dx in (-.299,0,.299):
            for dz in (-.299,0,.299):
                px,pz=position[0]+dx,position[2]+dz;bx,bz=math.floor(px),math.floor(pz);support=g.boxes(w.get(bx,-367,bz))
                assert any(b[0]<=px-bx<=b[3] and b[2]<=pz-bz<=b[5] and abs(-367+b[4]-position[1])<.001 for b in support),('Every role viewpoint must have whole foot bearing',view,px,pz)
    stand_path=[[x+.5,FEET+.5,-267.5] for x in range(-32,93)]
    for a,b in zip(stand_path,stand_path[1:]):
        assert g.edge_clear((math.floor(a[0]),FEET+.5,-268),(math.floor(b[0]),FEET+.5,-268)),('Raised whole stand obstructed',a,b)
    for reverse in (False,True):cases.append({'id':'r44/upper_observer/raised_stand_full_width'+('/return' if reverse else ''),'path':stand_path[::-1] if reverse else stand_path})
    # Source-authoritative negative space. The crane's entire head/trolley
    # sweep is belowY-370.7; the deck underside beginsY-369. Plug full121
    # and all actual submitted body parts remain behind the new frontage.
    negative=[]
    for b in frames:
        variant=b['variant'];cx=b['eva_feet'][0]
        crane=np.array([[cx-5.5,-430.,-269.7],[cx+5.5,-370.7,-211.3]])
        capsule=np.asarray(b['capsule_sweep_negative']);body=[np.asarray(p['world_bounds']).reshape(2,3) for p in actors[str(variant)]['parts'].values()]
        hits=[]
        for q,(state,purpose) in changes.items():
            if state in AIR:continue
            low=np.array(q);high=low+1
            for label,box in [('full_crane_conservative_sweep',crane),('full_capsule121_sweep',capsule),*[(f'body_{i}',p) for i,p in enumerate(body)]]:
                if np.all(high>box[0]-.2)&np.all(low<box[1]+.2):hits.append({'position':q,'keepout':label})
        assert not hits,('Whole observer extension intersects actual machinery negative space',variant,hits[:10])
        negative.append({'variant':variant,'changed_solid_members':sum(state not in AIR for state,purpose in changes.values()),
            'body_parts':len(body),'crane_all_rail_states_conservative_bounds':crane.tolist(),'capsule_full121':capsule.tolist(),'hits':hits})
    w.get=before_get
    p,inv=v.Painter(),v.Painter();v.WORLD,v.OUT=WORLD,OUT
    for q,(target,purpose) in sorted(changes.items()):
        old=w.block(q);p.match((*q,*q),old,target,'r44/upper_observer/'+purpose);inv.match((*q,*q),target,old,'inverse/r44/upper_observer/'+purpose)
    report={'cells':len(changes),'old_whole_front_glazing_z':OLD_FACE,'new_whole_front_glazing_z':NEW_FACE,
        'existing_public_feet_y':FEET,'floor_y':-368,'foundation_y':-369,'same_connected_ceiling_y':-362,
        'continuous_view_stand_feet_y':FEET+.5,'half_step_native_state':STEP,
        'all_three_bays_joined':True,'full_width_five_rows_plus_raised_stand':rows,'actual_original_lift_port':port,
        'preserved_complete_transverse_beams':beam,'preserved_whole_lift_domain':protected,
        'preserved_complete_be_snbt':[{'position':q,'snbt':t.snbt()} for q,t in sorted(tags.items())],
        'all_actual_head_chest_pylon_sightlines':vision,'all_states_machinery_negatives':negative,
        'source_sha256':{'actual_full_body':hashlib.sha256(BODY.read_bytes()).hexdigest(),
            'crane_geometry':hashlib.sha256((ROOT/'src/main/java/com/projectseele/client/render/PlugGantryRenderer.java').read_bytes()).hexdigest(),
            'crane_clock':hashlib.sha256((ROOT/'src/main/java/com/projectseele/world/EntryPlugDirector.java').read_bytes()).hexdigest()},
        'authority':'Root explicitly authorised complete -367 observation layer/view stand and continuous real lift access, retaining beam/crane/plug/body clearance; original R20 copied upper floor + native r25-west-observation endpoint',
        'source_template_installed':True,'apply_allowed':True,'world_write_performed':False,'native_passed':False,'visual_passed':False,
        'source_template':{'caller':'tools/plan_factory_r20.py','shared_geometry':'tools/tv_upper_observation_design_r44.py',
            'sha256':hashlib.sha256((ROOT/'tools/tv_upper_observation_design_r44.py').read_bytes()).hexdigest(),
            'caller_sha256':hashlib.sha256((ROOT/'tools/plan_factory_r20.py').read_bytes()).hexdigest(),
            'preservation':'Shared helper preserves full original lift domain, protected original cells and complete BE. Commissioned worlds still use only this exact forward/inverse migration.'},
        'pre_apply_remaining':['Root whole-component/complete current BE/entity/actual machinery source review and stopped-world exact preconditions'],
        'post_apply':['24 native complete-floor width/lift return paths including actualhalf step','Actual6 observer photos+3 worker contact photos','Actual crane/plug/cage/transport/return phases','Native new navigation/full metadata/cold/client/server/final copy']}
    p.meta.update(report);p.save_plan('whole_upper_observation_frontage_and_view_band')
    inv.meta.update({'forward':'whole_upper_observation_frontage_and_view_band'});inv.save_plan('inverse_whole_upper_observation_frontage_and_view_band')
    (OUT/'contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'native_cases.json').write_text(json.dumps(cases,indent=2),encoding='utf8');(OUT/'cameras.json').write_text(json.dumps(views,indent=2),encoding='utf8')
    print(json.dumps({'cells':len(changes),'be_preserved':len(tags),'retained_beam_members':len(beam),'real_native_cases':len(cases),
        'actual_landmarks_visible_from_real_stand':len(vision)*8,'source_template_installed':True,'apply_allowed':True,'world_write_performed':False}))


if __name__=='__main__':main()
