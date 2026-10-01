"""Complete918 original rolling-beam cells into real registered I-profile shapes.

Exact native six-state union verified, same bearing, running-plane and gauge.
No track truncation and no geometry-only air replacement.
"""
from pathlib import Path
import copy,json,hashlib,itertools,numpy as np
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,AIR
from tv_crane_girder_design_r44 import running_state

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44'
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';OUT=ART/'facility_transit_r44/tv_native_crane_girders_v1'
NATIVE=ART/'native_walks/actual_crane_girder_shapes/20261001_081900/r44_crane_girder_shapes.json'


def same_union(a,b):
    a=np.array(a).reshape(-1,2,3);b=np.array(b).reshape(-1,2,3)
    cuts=[sorted(set(np.round(np.concatenate([a[:,0,i],a[:,1,i],b[:,0,i],b[:,1,i]]),10))) for i in range(3)]
    for p in itertools.product(*[(np.array(c[:-1])+c[1:])/2 for c in cuts]):
        p=np.array(p);inside=lambda boxes:np.any(np.all((p>boxes[:,0]-1e-10)&(p<boxes[:,1]+1e-10),axis=1))
        if inside(a)!=inside(b):return False
    return True


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    native=json.loads(NATIVE.read_text('utf8'));assert len(native['collision_shapes'])==len(native['outline_shapes'])==6
    expected=json.loads((ART/'hangar_machinery/tv_crane_girder_v1/asset_contract.json').read_text('utf8'))['source_expected_shapes_m']
    unions=[]
    for key,boxes in native['collision_shapes'].items():
        statekey=key.partition('[')[2][:-1];assert same_union(boxes,expected[statekey]),('Native collision/model union mismatch',key)
        assert same_union(boxes,native['outline_shapes'][key]),('Native outline differs',key)
        a=np.array(boxes).reshape(-1,2,3);assert a.min()>=0 and a.max()<=1,'Profiles must remain a subset of old physical cube'
        unions.append({'state':key,'native_partition_count':len(boxes),'exact_union_matches_source_models':True})
    w=MeasuredWorld(WORLD);w.box((-35,-379,-273),(96,-350,-212));w.load()
    tags={q:copy.deepcopy(t) for q,t in iter_block_entities(WORLD,v.DIM,(-35,-379,-273),(96,-350,-212))}
    p,inv=v.Painter(),v.Painter();v.WORLD,v.OUT=WORLD,OUT;changes=[];dependencies={};support=[]
    frames=json.loads((ART/'facility_transit_r44/hangar_tv_calibration_v2/semantic_frame.json').read_text('utf8'))['bays']
    for bay in frames:
        cx=bay['bed'][0]
        for x in (cx-4,cx+4):
            for z in range(-266,-215):
                for y in range(-376,-373):
                    q=(x,y,z);old=w.block(q);assert old=='projectseele:nerv_machine_edge' and q not in tags,('Complete actual rolling-owner changed',q,old)
                    after=running_state(y,z);assert after in native['collision_shapes']
                    p.match((*q,*q),old,after,'r44/complete_native_igirders');inv.match((*q,*q),after,old,'inverse/r44/complete_native_igirders')
                    changes.append({'position':q,'before':old,'after':after})
            for z in (-264,-246,-228):
                q=(x,-377,z);assert w.block(q)=='projectseele:nerv_structural_panel',('Actual bottom bearing absent',q,w.block(q));dependencies[q]=w.block(q)
                support.append({'variant':bay['variant'],'rolling_center_x':x+.5,'world_z':z,'existing_under_bracket':q,
                    'native_base_bottom_y':-376,'whole_base_flange_contacts_native_full_bracket':True})
        for side in (-1,1):
            for z in (-264,-246,-228):
                for x in range(min(cx+side*4,cx+side*8),max(cx+side*4,cx+side*8)+1):dependencies[x,-377,z]=w.get(x,-377,z)
                for y in range(-377,-353):dependencies[cx+side*8,y,z]=w.get(cx+side*8,y,z)
        zs=[r['crane_eye'][2] for r in bay['capsule_route_samples']]
        assert min(zs)-2.8>=-266 and max(zs)+2.8<=-215
        for z in np.linspace(min(zs),max(zs),121):
            for wheelz in (z-2.8,z+2.8):
                state=running_state(-374,int(np.floor(wheelz)))
                boxes=np.array(native['collision_shapes'][state]).reshape(-1,2,3)
                for px in (.32,.5,.68):
                    assert any(abs(b[1,1]-1)<1e-9 and b[0,0]<=px<=b[1,0] and b[0,2]<=wheelz%1<=b[1,2] for b in boxes),('Actual fullwheel tread support lost',state,z,px)
    assert len(changes)==918
    report={'cells':918,'six_native_union_proofs':unions,'native_shape_source':str(NATIVE),'native_shape_sha256':hashlib.sha256(NATIVE.read_bytes()).hexdigest(),
        'exact_original_owner_cells':changes,'complete_existing_bottom_bearing_relations':support,
        'whole_preserved_support_dependencies':[{'position':q,'state':s} for q,s in sorted(dependencies.items())],
        'complete_current_be':[{'position':q,'snbt':t.snbt()} for q,t in sorted(tags.items())],
        'running_surface_y_before_after':[-373,-373],'bottom_bearing_y_before_after':[-376,-376],'railcenter_offsets_before_after':[[-4,4],[-4,4]],
        'native_wheel_contact':'All121 current capsule/crane positions, four wheelz±2.8 and actual.36m tread width sampled across full native top flange',
        'clearance':'Everynew native solid is a strict subset of its old fullcube; existing body/plug/crew sweptspaces cannot acquire a new obstacle',
        'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('tools/plan_factory_r20.py','tools/plan_hangar_structure_r44.py','tools/repair_world_details_r26.py','tools/tv_crane_girder_design_r44.py','src/main/java/com/projectseele/world/TvCraneGirderR44.java')},
        'source_template_installed':True,'apply_allowed':True,'world_write_performed':False,'native_passed':False,'visual_passed':False,
        'pre_apply':['Root stopped-world exact918/native6shape/model/sourcecurrent/dependencies/fullBE/entity/oldinverse review'],
        'post_apply':['Realcontinuous trolley/crane/plug allstates and cancellation/return','Repeat24 realobserver paths and sourcejob images','Native final0..2 factory/cold/MP/finalcopy']}
    p.meta.update(report);p.save_plan('complete_native_crane_igirders');inv.meta.update({'forward':'complete_native_crane_igirders'});inv.save_plan('inverse_complete_native_crane_igirders')
    (OUT/'contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'cells':918,'native_union':len(unions),'actual_bearings':len(support),'dependencies':len(dependencies),'body_clearance_by_subset':True,'world_write_performed':False}))


if __name__=='__main__':main()
