"""Retire the complete obsolete R26 upper longitudinal beams, preserving load paths.

Actual trolley top-chord triangles intersect this old owner. The commissioned
R44 lower tracks, bearings, drop hangers, roof and both complete crossframes
stay exact. Source callbacks are corrected separately; no world apply here.
"""
from pathlib import Path
import copy,hashlib,json,numpy as np
import regional_voxels as v
import build_tv_machinery_r16 as mesh
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from author_tv_shoulder_installation_r44 import prism_hits_triangle
from build_tv_shoulder_shells_r44 import box_vertices

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
ART=ROOT/'artifacts/rebuild_r44';OUT=ART/'facility_transit_r44/tv_duplicate_upper_runways_v1'
EDGE='projectseele:nerv_machine_edge'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    w=MeasuredWorld(WORLD);w.box((-35,-379,-273),(96,-350,-212));w.load()
    tags={q:copy.deepcopy(t) for q,t in iter_block_entities(WORLD,v.DIM,(-35,-379,-273),(96,-350,-212))}
    changes={};dependencies={};crossframes=[];tracks=[];clearance=[];owner_members=[];already_air=[];pressure_face=[]
    frames=json.loads((ART/'facility_transit_r44/hangar_tv_calibration_v2/semantic_frame.json').read_text('utf8'))['bays']
    source=(ROOT/'src/main/java/com/projectseele/client/render/PlugGantryRenderer.java').read_text('utf8')
    assert 'box(x-.25,1.09,-3.6,.50,.16,7.2,GREEN)' in source,'Actual author topchord changed; remeasure'
    assert 'box(x-.08,.21,-3.6,.16,.88,7.2,EDGE)' in source,'Actual author vertical web changed; remeasure'
    mesh.PARTS.clear();mesh.use('actual_trolley_source_chords')
    for side in (-1,1):
        mesh.box(side*4-.25,1.09,-3.6,.50,.16,7.2,0x56705A)
        mesh.box(side*4-.08,.21,-3.6,.16,.88,7.2,0x8D9A86)
    tri=np.asarray(mesh.PARTS['actual_trolley_source_chords']).reshape(-1,3,6)[:,:,:3]
    for b in frames:
        variant=b['variant'];cx=b['bed'][0]
        for x in (cx-4,cx+4):
            for y in range(-372,-369):
                for z in range(-270,-214):
                    q=(x,y,z);state=w.block(q)
                    assert q not in tags,('Whole R26 upper-owner has device',q)
                    owner_members.append({'position':q,'state':state})
                    if state in AIR:already_air.append(q);dependencies[q]=state;continue
                    if state=='projectseele:nerv_shaft_panel' and z==-267:
                        assert w.get(x-1,y,z)==w.get(x+1,y,z)=='projectseele:clear_glass',('Complete pressure pane not proven',q)
                        pressure_face.append(q);changes[q]=(state,'projectseele:clear_glass')
                    else:
                        assert state==EDGE,('Whole R26 upper-owner differs',q,state)
                        changes[q]=(state,'minecraft:air')
            for y in range(-376,-373):
                for z in range(-266,-215):
                    q=(x,y,z);state=w.block(q)
                    assert state==EDGE,('Actual complete lower wheel track lost',q,state)
                    dependencies[q]=state
            tracks.append({'variant':variant,'x_cell':x,'rolling_center_world_x':x+.5,'run_z_solid_extent':[-266,-215],
                'beam_bottom_y':-376,'continuous_running_surface_y':-373,'trolley_source_y':-373,
                'wheel_bottom_local_y':0,'source_profile':'R44 supports remain exact; top of lower tracks coincides with four moving wheel bottoms'})
        for z in (-271,-214):
            for x in range(cx-19,cx+20):
                for y in range(-373,-368):
                    q=(x,y,z);state=w.block(q)
                    if state and state.partition('[')[0] not in AIR:
                        crossframes.append({'position':q,'state':state});dependencies[q]=state
        for side in (-1,1):
            for z in (-264,-246,-228):
                for x in range(min(cx+side*4,cx+side*8),max(cx+side*4,cx+side*8)+1):
                    q=(x,-377,z);dependencies[q]=w.block(q)
                for y in range(-377,-353):
                    q=(cx+side*8,y,z);dependencies[q]=w.block(q)
        origin=np.array([cx+.5,-373,-230.])
        actual=tri+origin;before_hits=0;lower_hits=0
        for q in changes:
            if abs(q[0]-cx)>5:continue
            box=np.array([q,np.asarray(q)+1]);mask=np.all((actual.max(1)>=box[0])&(actual.min(1)<=box[1]),axis=1)
            before_hits+=sum(prism_hits_triangle(box_vertices(box),t,.001) for t in actual[mask])
        for q in dependencies:
            if q[1] not in (-376,-375,-374) or q[0] not in (cx-4,cx+4):continue
            box=np.array([q,np.asarray(q)+1]);mask=np.all((actual.max(1)>=box[0])&(actual.min(1)<=box[1]),axis=1)
            lower_hits+=sum(prism_hits_triangle(box_vertices(box),t,.001) for t in actual[mask])
        assert before_hits>0 and lower_hits==0,('Source real-triangle root cause not proven',variant,before_hits,lower_hits)
        zs=[r['crane_eye'][2] for r in b['capsule_route_samples']]
        assert min(zs)-2.8>-266 and max(zs)+2.8<-215,'Complete121 current capsule/trolley wheel route not supported'
        clearance.append({'variant':variant,'actual_source_trolley_triangles':len(tri),'original_upper_real_triangle_intersections':before_hits,
            'retained_lower_real_triangle_intersections':lower_hits,'upper_after_retirement_intersections':0,
            'actual_capsule121_trolley_z_extent':[min(zs),max(zs)],'four_wheel_contact_z_extent':[min(zs)-2.8,max(zs)+2.8],
            'front_continuous_track_margin_m':min(zs)-2.8+266,'rear_continuous_track_margin_m':-215-max(zs)-2.8,
            'bound_limit':'Source geometry at actualfixed runningY; capsule121 is currentnormal workflow. Arbitrary manual clamp extreme±25 can exceed four-wheel supports and is not automatically a validated travel permission.'})
    assert len(owner_members)==1008 and len(changes)+len(already_air)==1008
    p,inv=v.Painter(),v.Painter();v.WORLD,v.OUT=WORLD,OUT
    for q,(state,after) in sorted(changes.items()):
        p.match((*q,*q),state,after,'r44/whole_r26_upper_longitudinal_runway_retirement')
        inv.match((*q,*q),after,state,'inverse/r44/whole_r26_upper_longitudinal_runway_retirement')
    report={'cells':len(changes),'complete_former_owner_volume':1008,'complete_owner_members':owner_members,
        'already_retired_air_members_preserved':already_air,'pressure_glazing_restored_members':pressure_face,
        'original_owner_source':'tools/repair_world_details_r26.py exactold9m shifted EDGE longitudinal runways',
        'retired_complete_bounds_by_bay':[[[cx-4,-372,-270],[cx+4,-370,-215]] for cx in (-12,30,72)],
        'actual_correct_running_tracks':tracks,'source_trolley_triangle_before_after':clearance,
        'complete_preserved_crossframes':crossframes,'full_structural_dependencies':[{'position':q,'state':s} for q,s in sorted(dependencies.items())],
        'preserved_complete_original_be':[{'position':q,'snbt':t.snbt()} for q,t in sorted(tags.items())],
        'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
            'tools/repair_world_details_r26.py','tools/plan_hangar_structure_r44.py','src/main/java/com/projectseele/client/render/PlugGantryRenderer.java','src/main/java/com/projectseele/world/HangarStructuralFrameR44.java')},
        'before_side_section':{'upper_old_y':[-372,-370],'trolleyY':-373,'actual_trolley_topchord_y':[-371.91,-371.75],
            'correct_lower_y':[-376,-374],'running_surface':-373,'headroom_and_body':'Whole old upperbeam sits4m too high and intersects moving girder; retirement is structural duplication correction, not a view-only cut'},
        'source_template_installed':True,'apply_allowed':True,'world_write_performed':False,'native_passed':False,'visual_passed':False,
        'pre_apply':['Root exclusive exact1008 before/inverse/wholecurrentBE/entities/dependencies/source epoch review'],
        'post_apply':['Native crane/plug couplings/raise/return/full121 contact and clearance','Repeat24 observer native walking/lift routes','Actual sixgrounded observer and threeworker images after final cage/wetwall finish','Cold/MP/finalcopy'],
        'structural_roles_retained':'WholeZ-271 frontbearing/Z-214 rearframe, continuousR44 lowerrolling beams, all18 drop hangers/brackets and actual2-layer roof; original observationfloor, stepdais and gallery/lift/controls unchanged'}
    p.meta.update(report);p.save_plan('whole_obsolete_r26_upper_runways')
    inv.meta.update({'forward':'whole_obsolete_r26_upper_runways'});inv.save_plan('inverse_whole_obsolete_r26_upper_runways')
    (OUT/'contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'cells':len(changes),'dependencies':len(dependencies),'crossframe_members':len(crossframes),'original_be':len(tags),
        'real_triangle_before_after':clearance,'source_stable':True,'world_write_performed':False}))


if __name__=='__main__':main()
