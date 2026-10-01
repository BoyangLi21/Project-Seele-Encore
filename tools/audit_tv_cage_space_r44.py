"""Read-only complete fixed/moving cage vs actors, capsule, crew and actual blocks."""
from pathlib import Path
from collections import Counter
import hashlib,json,math
import numpy as np
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/hangar_machinery/tv_shoulder_shells_v1'
SOURCE=ROOT/'artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2'


def overlaps(a,b,guard=0):return bool(np.all(a[1]>b[0]-guard)&np.all(a[0]<b[1]+guard))


def motion(c,p):
    def ramp(v,a,b):
        t=np.clip((v-a)/(b-a),0,1);return t*t*(3-2*t)
    if c['motion']=='translation_only_with_exact_facet_pad':
        return np.asarray(c['normal'])*2.1*ramp(p,0,.25)+[c['outboard_m']*ramp(p,.23,.88),0,0]
    if c['motion']=='telescoping_translation':return np.asarray(c['translation_open_local'])*ramp(p,*c['opening_interval'])
    return np.zeros(3)


def main():
    path=ROOT/'src/main/resources/assets/projectseele/mesh/tv_shoulder_shells_r44.json'
    d=json.loads(path.read_text(encoding='utf8'));frames=json.loads((SOURCE/'semantic_frame.json').read_text(encoding='utf8'))['bays']
    bodies=json.loads((SOURCE/'actual_render_body_surfaces_triangles.json').read_text(encoding='utf8'))['actors']
    w=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW');w.box((-64,-448,-296),(128,-348,-190));w.load();g=Geometry(w)
    body_hits=[];plug_hits=[];crew_hits=[];block_hits={};anchors={};wall_hits=[]
    for bay in frames:
        variant=bay['variant'];origin=np.asarray(bay['eva_feet'])+[0,-.96,0]
        plug=np.asarray(bay['capsule_sweep_negative'])
        crew=[]
        for side in (-1,1):
            for lane in (18,19):
                x=origin[0]+side*lane
                crew.append(np.array([[x-.3,-394.,-260.],[x+.3,-392.2,-224.]]))
        for c in d['components']:
            if c.get('variant',variant)!=variant or c['part'].startswith('thin_side_rails'):continue
            boxes=d['collision_parts'][c['part']]
            samples=[0.] if c['motion']=='fixed' else np.linspace(0,1,121)
            for opening in samples:
                move=origin+motion(c,opening)
                for local in boxes:
                    b=np.asarray(local)+move
                    for name,p in bodies[str(variant)]['parts'].items():
                        pb=np.asarray(p['world_bounds']).reshape(2,3)
                        if overlaps(b,pb,.20):body_hits.append({'variant':variant,'part':c['part'],'body':name,'opening':float(opening)})
                    if overlaps(b,plug):plug_hits.append({'variant':variant,'part':c['part'],'opening':float(opening)})
                    if any(overlaps(b,q) for q in crew):crew_hits.append({'variant':variant,'part':c['part'],'opening':float(opening)})
                    if b[0,0]<origin[0]-20.5 or b[1,0]>origin[0]+20.5 or b[0,2]<-267 or b[1,2]>-213:
                        wall_hits.append({'variant':variant,'part':c['part'],'opening':float(opening),'bounds':b.tolist()})
                    # Exact static world intersections; all 121 states remain
                    # in actor/capsule/crew checks, world is sampled at 11 states.
                    if c['motion']!='fixed' and round(float(opening)*120)%12:continue
                    for x in range(math.floor(b[0,0]),math.ceil(b[1,0])):
                        for y in range(math.floor(b[0,1]),math.ceil(b[1,1])):
                            for z in range(math.floor(b[0,2]),math.ceil(b[1,2])):
                                state=w.get(x,y,z)
                                if state is None:raise RuntimeError(('Unknown scene state',x,y,z))
                                if state.partition('[')[0] in AIR|{'minecraft:light','projectseele:lcl','minecraft:water'}:continue
                                for shape in g.boxes(state) or []:
                                    obstacle=np.asarray(shape).reshape(2,3)+[x,y,z]
                                    if not overlaps(b,obstacle):continue
                                    key=(variant,c['part'],x,y,z,state)
                                    row={'variant':variant,'part':c['part'],'position':[x,y,z],'state':state,'opening':float(opening)}
                                    if y<=-443:anchors[key]=row
                                    else:block_hits[key]=row
    report={'resource_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'body_guard_m':.20,
        'body_hits':body_hits,'capsule_full121_envelope_hits':plug_hits,'six_crew_lanes_hits':crew_hits,
        'wet_bay_wall_crossings':wall_hits,'existing_base_bearing_contacts':list(anchors.values()),
        'actual_world_intersections':list(block_hits.values()),'world_intersection_count':len(block_hits),
        'world_hits_by_variant_part':dict(Counter(f"{v}/{part}" for v,part,*rest in block_hits)),
        'native_passed':False,'visual_passed':False,'world_write_performed':False,
        'limit':'Conservative physical primitives versus actual submitted body bounds and complete capsule121 sweep. Exact vertex mesh test remains in generator receipt; native motion/occupied stop/cold reload are separate.'}
    (OUT/'actual_space_contract.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['body_hits','capsule_full121_envelope_hits','six_crew_lanes_hits','existing_base_bearing_contacts','actual_world_intersections','wet_bay_wall_crossings']}|{'body_hits':len(body_hits),'plug_hits':len(plug_hits),'crew_hits':len(crew_hits),'walls':len(wall_hits)}))


if __name__=='__main__':main()
