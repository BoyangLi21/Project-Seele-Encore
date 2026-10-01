"""Private final cage primitives vs fullactual body/crew/capsule/world/carrier sources.

Exact body SAT is in the generator; conservative body AABBs are reported as
diagnostics, never converted into fake penetration or silently called zero.
"""
from pathlib import Path
from collections import Counter
import argparse,json,hashlib,math,numpy as np
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from audit_tv_cage_space_r44 import motion,overlaps
from query_blocks import AIR
from author_tv_shoulder_installation_r44 import prism_hits_triangle
from build_tv_shoulder_shells_r44 import box_vertices

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44'
OUT=ART/'hangar_machinery/tv_shoulder_shells_v2'
RESOURCE=OUT/'tv_shoulder_shells_r44.json'
BODY=ART/'space_photos/installed_maps_hakone_and_tv_fullbody/20261001_045405/r44_hangar_body_surfaces.json'


def main(resource_path=RESOURCE,out_path=OUT):
    global RESOURCE,OUT
    RESOURCE,OUT=Path(resource_path),Path(out_path);OUT.mkdir(parents=True,exist_ok=True)
    d=json.loads(RESOURCE.read_text('utf8'));actors=json.loads(BODY.read_text('utf8'))['actors']
    frames=json.loads((ART/'facility_transit_r44/hangar_tv_calibration_v2/semantic_frame.json').read_text('utf8'))['bays']
    w=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW');w.box((-64,-448,-296),(128,-348,-190));w.load();g=Geometry(w)
    world_hits={};foundations={};known_bearings={};body_diagnostic=Counter();capsule=[];crew=[];wall=[];arrival=[];source_checks=[]
    for bay in frames:
        v=bay['variant'];origin=np.asarray(bay['eva_feet'])+[0,-.96,0];cx=bay['bed'][0]
        body_names=list(actors[str(v)]['parts']);body=np.array([actors[str(v)]['parts'][n]['world_bounds'] for n in body_names]).reshape(-1,2,3)
        plug=np.asarray(bay['capsule_sweep_negative'])
        lanes=np.array([[[origin[0]+s*x-.3,-394,-260],[origin[0]+s*x+.3,-392.2,-224]] for s in (-1,1) for x in (18,19)])
        # Inclusive original owner cells85..98/-399..-390/-264..-248
        # have this complete extent; the far face is -247, not -248.
        pocket=np.array([[85.,-399.,-264.],[99.,-389.,-247.]])
        for c in d['components']:
            if c.get('variant',v)!=v or c['part'].startswith('thin_side_rails'):continue
            local=np.array(d['collision_parts'][c['part']]);samples=[0.] if c['motion']=='fixed' else np.linspace(0,1,121)
            for opened in samples:
                boxes=local+origin+motion(c,float(opened))
                mask=np.all((boxes[:,None,1]>body[None,:,0]-.20)&(boxes[:,None,0]<body[None,:,1]+.20),axis=2)
                for i in np.flatnonzero(mask.any(0)):body_diagnostic[f'{v}/{c["part"]}/{body_names[i]}']+=int(mask[:,i].sum())
                if np.any(np.all((boxes[:,1]>plug[0])&(boxes[:,0]<plug[1]),axis=1)):capsule.append([v,c['part'],float(opened)])
                if np.any(np.all((boxes[:,None,1]>lanes[None,:,0])&(boxes[:,None,0]<lanes[None,:,1]),axis=2)):crew.append([v,c['part'],float(opened)])
                if np.any((boxes[:,0,0]<origin[0]-20.5)|(boxes[:,1,0]>origin[0]+20.5)|(boxes[:,0,2]<-267)|(boxes[:,1,2]>-213)):wall.append([v,c['part'],float(opened)])
                if v==2 and np.any(np.all((boxes[:,1]>pocket[0])&(boxes[:,0]<pocket[1]),axis=1)):arrival.append([c['part'],float(opened)])
                if c['motion']!='fixed' and round(float(opened)*120)%12:continue
                for b in boxes:
                    for x in range(math.floor(b[0,0]),math.ceil(b[1,0])):
                        for y in range(math.floor(b[0,1]),math.ceil(b[1,1])):
                            for z in range(math.floor(b[0,2]),math.ceil(b[1,2])):
                                state=w.get(x,y,z)
                                if state is None:raise RuntimeError(('Unknown complete equipment scene',x,y,z))
                                if state.partition('[')[0] in AIR|{'minecraft:light','projectseele:lcl','minecraft:water'}:continue
                                shapes=g.boxes(state)
                                if shapes is None:raise RuntimeError(('Actual world collision not exported',x,y,z,state))
                                if not any(overlaps(b,np.asarray(s).reshape(2,3)+[x,y,z]) for s in shapes):continue
                                row={'variant':v,'part':c['part'],'position':[x,y,z],'state':state,'opening':float(opened)};key=(v,c['part'],x,y,z)
                                if y<=-443:foundations[key]=row
                                elif c['part']=='cage_frame_lower_r44' and (x,y,z) in {(cx+s*17,-396,-240) for s in (-1,1)} and state=='projectseele:nerv_structural_panel':
                                    known_bearings[key]=row
                                else:world_hits[key]=row
    # Full authored carrier inventory, including lowered/rising spine, clamping
    # and padstroke, is checked against all fixed mechanical primitives. It is
    # deliberately not reduced to the29m visible topplate.
    cp=ROOT/'src/main/resources/assets/projectseele/mesh/tv_facilities_r16.json';carrier=json.loads(cp.read_text('utf8'))
    for v in range(3):
        fixed=[(c['part'],np.array(b)) for c in d['components'] if c.get('variant',v)==v and c['motion']=='fixed' and not c['part'].startswith('thin_side_rails') for b in d['collision_parts'][c['part']]]
        for name,values in carrier['parts'].items():
            if not name.startswith('carrier_') or name=='carrier_ram_unit':continue
            if name[-1:] in ('0','1','2') and int(name[-1])!=v:continue
            if name.startswith('carrier_contacts_'):continue # Actualnew pad/ram path supersedes this legacy fallback.
            triangles=np.array(values).reshape(-1,3,carrier['stride'])[:,:,:3]+[0,.96,0]
            samples=np.linspace(0,1,121) if name not in ('carrier_deck','carrier_deck_guides') else [1.]
            conflicts=[]
            for rise in samples:
                t=triangles.copy()
                if name not in ('carrier_deck','carrier_deck_guides'):t[:,:,1]-=64*(1-rise)
                if name.startswith('carrier_contact_pads_'):
                    smooth=np.clip((rise-.80)/.20,0,1);smooth=smooth*smooth*(3-2*smooth);t[:,:,2]+=6*(1-smooth)
                whole_low=t.min((0,1));whole_high=t.max((0,1));triangle_low=t.min(1);triangle_high=t.max(1)
                for part,b in fixed:
                    if not np.all((whole_high>=b[0])&(whole_low<=b[1])):continue
                    mask=np.all((triangle_high>=b[0])&(triangle_low<=b[1]),axis=1)
                    hits=sum(prism_hits_triangle(box_vertices(b),q,.003) for q in t[mask])
                    if hits:conflicts.append({'rise':float(rise),'fixed_part':part,'actual_triangle_hits':hits})
            source_checks.append({'variant':v,'carrier_part':name,'actual_source_triangles':len(triangles),'samples':len(samples),'conflicts':conflicts})
    report={'resource_sha256':hashlib.sha256(RESOURCE.read_bytes()).hexdigest(),'actual_fullbody_sha256':hashlib.sha256(BODY.read_bytes()).hexdigest(),
        'carrier_source_sha256':hashlib.sha256(cp.read_bytes()).hexdigest(),'all_states_crew_hits':crew,'capsule_full121_hits':capsule,
        'wet_envelope_hits':wall,'original_02_arrival_body_hits':arrival,'actual_world_intersections':list(world_hits.values()),
        'existing_foundation_bearing_contacts':list(foundations.values()),'declared_existing_crew_cantilever_contacts':list(known_bearings.values()),
        'body_AABB_diagnostic_overlaps':dict(body_diagnostic),'complete_carrier_fixed_part_exact_checks':source_checks,
        'world_state_samples_per_movingpart':11,'actor_capsule_crew_samples_per_movingpart':121,'world_write_performed':False,
        'native_passed':False,'visual_passed':False,'limits':'Generator full actualtriangle SAT governs body contact. Sources do not substitute for native continuous gantry/plug/carrier lifecycle or user art.'}
    (OUT/'complete_physical_interfaces.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({'crew':len(crew),'capsule':len(capsule),'wall':len(wall),'02_arrival':len(arrival),'world_hits':len(world_hits),
        'declared_cantilever_contacts':len(known_bearings),'carrier_checks':len(source_checks),'carrier_conflicts':sum(len(r['conflicts']) for r in source_checks)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--resource',type=Path,default=RESOURCE);parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args();main(args.resource,args.out)
