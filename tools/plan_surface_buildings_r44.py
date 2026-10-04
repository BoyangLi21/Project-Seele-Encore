"""Audit all authored entrances and plan measured, reversible Japanese street fronts.

This tool never opens a world for writing. Existing buildings, human contents,
stair cores and transit are preserved; only exact facade materials and public
iron-door pairs inside their authored bounds may change.
"""
from __future__ import annotations
from collections import Counter, deque
from pathlib import Path
import argparse, gzip, hashlib, json, math
import nbtlib
from measure_world_r40 import MeasuredWorld, properties
from query_blocks import AIR, iter_block_entities
from regional_voxels import canonical_state
from city_bookshop_interior_r45 import resolve_ground_floor_use,author_bookshop_displays,source_owned_sign_text,create_owned_envelopes,intersects_create
from city_clinic_interior_r45 import captured_bed_defaults,author_clinic_exam_bay

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts/rebuild_r44/city_buildings'
WORLD = ROOT / 'run/saves/SEELE_FIELD_R44_REVIEW'
OWNERS = ROOT / 'artifacts/repair_r43/facility_catalogue/authored_ownership.json'
PALETTE = {'minecraft:white_concrete', 'minecraft:light_gray_concrete',
           'minecraft:gray_concrete', 'minecraft:smooth_sandstone',
           'minecraft:polished_deepslate', 'minecraft:gray_stained_glass',
           'minecraft:smooth_stone', 'minecraft:red_terracotta'}
FRONTS = (
    ('neighbourhood_office', '町内事务所', 'minecraft:light_gray_concrete', 'minecraft:stone_brick_slab'),
    ('bookshop', '街角书店', 'minecraft:brown_terracotta', 'minecraft:smooth_stone_slab'),
    ('clinic', '社区诊所', 'minecraft:white_concrete', 'minecraft:quartz_slab'),
    ('coffee_house', '喫茶店', 'minecraft:green_terracotta', 'minecraft:dark_oak_slab'),
    ('household_store', '日用品商店', 'minecraft:light_gray_terracotta', 'minecraft:smooth_stone_slab'),
    ('local_office', '办公楼入口', 'minecraft:gray_concrete', 'minecraft:stone_brick_slab'),
    ('residential_lobby', '住宅入口', 'minecraft:light_gray_concrete', 'minecraft:smooth_stone_slab'),
    ('corner_market', '街角商店', 'minecraft:orange_terracotta', 'minecraft:smooth_stone_slab'),
)

def emit(folder, rows, records, summary):
    folder.mkdir(parents=True, exist_ok=True)
    for name, inverse in (('forward', False), ('inverse', True)):
        with gzip.open(folder / (name + '.jsonl.gz'), 'wt', encoding='utf8') as stream:
            for r in rows:
                row = dict(r)
                if inverse:
                    row['before'], row['after'] = r['after'], r['before']
                    row['before_nbt'], row['after_nbt'] = r['after_nbt'], r['before_nbt']
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    (folder / 'audit.json').write_text(json.dumps(dict(summary=summary, buildings=records), ensure_ascii=False, indent=2), 'utf8')
    (folder / 'positive_edit_mask.json').write_text(json.dumps([r['pos'] for r in rows]), 'utf8')
    (folder / 'native_walk_cases.json').write_text(json.dumps([c for b in records for c in b['native_walk_cases']], ensure_ascii=False, indent=2), 'utf8')
    manifest = dict(world=str(WORLD), dimension='projectseele:geofront', cells=len(rows),
        plan_format='exact-state-and-full-SNBT-jsonl-v1', write_policy='single root writer; strict state/NBT equality; inverse exists for every cell',
        source_ownership_sha256=hashlib.sha256(OWNERS.read_bytes()).hexdigest(),
        original_design=True, references=[
            dict(url='https://www.eva-info.jp/1051', scope='Official Tokyo-3/Hakone association only; no episode stills or exact-set claim'),
            dict(url='https://www.hakone.or.jp/morifure/hakoneyasuraginomori.html', scope='Real lakeside woodland and public pedestrian park; contemporary reference'),
        ], native_passed=False, visual_self_review='PENDING in-game photos', user_approved=False)
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf8')

def main():
    global WORLD
    parser=argparse.ArgumentParser();parser.add_argument('--world', type=Path, default=WORLD)
    args=parser.parse_args();WORLD=args.world.resolve()
    authored_signs={}
    if (ART/'forward.jsonl.gz').exists():
        with gzip.open(ART/'forward.jsonl.gz','rt',encoding='utf8') as stream:
            for line in stream:
                r=json.loads(line)
                if r.get('after_nbt') and '_wall_sign[' in r['after']:
                    authored_signs[tuple(r['pos'])]=nbtlib.parse_nbt(r['after_nbt'])
    assert WORLD.name == 'SEELE_FIELD_R44_REVIEW', 'Only the root-authorized construction world is measured'
    bs=json.loads(OWNERS.read_text('utf8'))['buildings']
    clinic_bed_defaults={}
    clinic_native_capture=ROOT/'artifacts/rebuild_r44/world_composition/city_archive_closeout/native_initialized_be_candidates.json'
    clinic_world_type=WORLD/'datapacks/tv_world_preview/data/projectseele/dimension_type/geofront.json'
    clinic_beds_allowed=clinic_world_type.exists() and json.loads(clinic_world_type.read_text('utf8')).get('bed_works') is True
    if clinic_native_capture.exists() and clinic_beds_allowed:clinic_bed_defaults=captured_bed_defaults(json.loads(clinic_native_capture.read_text('utf8')))
    create_envelopes=[]
    create_contract=ROOT/'artifacts/rebuild_r45/city_motion/whole_topology_v2/manifest.json'
    if create_contract.exists():create_envelopes=create_owned_envelopes(json.loads(create_contract.read_text('utf8')))
    assert len(bs)==193
    shape_path=ROOT/'artifacts/rebuild_r44/source_world_backup/native_collision_shapes.json'
    shapes={canonical_state(k):v for k,v in json.loads(shape_path.read_text('utf8')).items()}
    rows={};records=[];counts=Counter();missing=set()
    for i,b in enumerate(bs):
        x0,y0,z0=b['planned_bounds'][0];x1,y1,z1=b['planned_bounds'][1]
        transport_scope=b['id'].startswith('airport/')
        if b['id'] in ('tokyo_south/13-05','tokyo_south/13-06'):
            receipt=json.loads((WORLD/'regional_quality_r03_structures.json').read_text('utf8'))
            assert receipt['cropped'][b['id']]==152 and receipt['receipt']['verified']
            x1=152
        w=MeasuredWorld(WORLD);lo=(x0-12,y0-8,z0-12);hi=(x1+12,y1+2,z1+16);w.box(lo,hi);w.load()
        tags={q:t for q,t in iter_block_entities(WORLD,b['dimension'],lo,hi)}
        def put(q, after, reason, allowed=PALETTE, after_nbt=None):
            if transport_scope:
                counts['preserved_transport_owned_write_attempts']+=1;return False
            q=tuple(q);before=w.block(q)
            if before is None:
                counts['unmeasured_candidate']+=1;return False
            old_tag=tags.get(q);before_nbt=old_tag.snbt() if old_tag is not None else None
            after=canonical_state(after)
            if before==after and before_nbt==after_nbt:return True
            if old_tag is not None and after_nbt is None:
                counts['preserved_block_entities']+=1;return False
            if before.partition('[')[0] not in allowed:
                counts['preserved_non_template_states']+=1;return False
            if q in rows:assert rows[q]['after']==after,(q,'conflicting frontage operations')
            rows[q]=dict(pos=q,before=before,after=after,before_nbt=before_nbt,after_nbt=after_nbt,owner=b['id'],reason=reason)
            return True
        doors=[]
        for feet in b['planned_floor_feet']:
            for z in range(z0,z1+1):
                for x in range(x0,x1+1):
                    state=w.get(x,feet,z)
                    if state is None or not state.partition('[')[0].endswith('_door'):continue
                    if properties(state).get('half')!='lower':continue
                    upper=w.get(x,feet+1,z)
                    pair_ok=upper is not None and properties(upper).get('half')=='upper' and upper.partition('[')[0]==state.partition('[')[0]
                    exterior=x in (x0,x1) or z in (z0,z1)
                    doors.append(dict(pos=[x,feet,z],state=state,upper=upper,pair_complete=pair_ok,exterior=exterior))
                    if pair_ok and state.partition('[')[0]=='minecraft:iron_door':
                        for q,old in (((x,feet,z),state),((x,feet+1,z),upper)):
                            put(q,old.replace('minecraft:iron_door','projectseele:city_personnel_door'),
                                'public entrance or room has a usable personnel latch',{'minecraft:iron_door'})
        # Ordinary two-storey office/house facades are authored at this exact
        # south wall. Old danchi use a private, different envelope and remain intact.
        style_index=int(hashlib.sha256(b['id'].encode()).hexdigest()[:8],16)%len(FRONTS)
        if b['style']=='residential' and style_index in (0,2,5):style_index=6
        identity,label,accent,awning=FRONTS[style_index]
        identity,label=resolve_ground_floor_use(identity,label,b['style'])
        if transport_scope:identity,label='preserved_transport_facility',b['id'].split('/')[-1]
        clinic_contents=None
        if identity=='clinic' and b['style']=='office' and not transport_scope:
            def clinic_put(q,state,owner,reason,nbt):
                return put(q,state,reason,{'minecraft:smooth_quartz','minecraft:air'},nbt)
            def clinic_protected(positions):
                return any(tuple(q) in tags for q in positions) or intersects_create(positions,create_envelopes)
            clinic_contents=author_clinic_exam_bay(b,w.block,clinic_put,clinic_bed_defaults,clinic_protected)
        bookshop_contents=None
        if identity=='bookshop' and b['style']=='office':
            def display_put(q,state,owner,reason):
                return put(q,state,reason,{'minecraft:smooth_quartz','minecraft:black_stained_glass','minecraft:bookshelf'})
            def display_protected(positions):
                return any(tuple(q) in tags for q in positions) or intersects_create(positions,create_envelopes)
            bookshop_contents=author_bookshop_displays(b,w.block,display_put,display_protected)
        if b['style']!='old_danchi':
            cx=b['entry'][0];feet=b['planned_floor_feet'][0]
            for x in range(x0+2,x1-1):
                # A restrained storefront band stays in the actual wall plane.
                if abs(x-cx)<=2:continue
                put((x,feet+3,z1),accent,'original neighbourhood frontage fascia')
            for x in range(cx-4,cx+5):
                put((x,feet+3,z1+1),awning+'[type=top,waterlogged=false]',
                    'shallow rain canopy above the complete three-high approach',AIR)
            for x in (x0+1,x1-1):
                for y in (feet,feet+1,feet+2):
                    put((x,y,z1),'minecraft:polished_andesite','frontage pier and continuous plinth')
            # Existing sign support is deliberately independent of the doorway.
            q=(cx+3,feet+2,z1+1);tag=tags.get(q)
            if tag is not None and str(tag.get('id',''))=='minecraft:sign' and source_owned_sign_text(tag,authored_signs.get(q)):
                after_tag=nbtlib.parse_nbt(tag.snbt())
                for face in ('front_text','back_text'):
                    if face in after_tag:
                        after_tag[face]['messages']=nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':s},ensure_ascii=False)) for s in (label,'入口 / 出口','人员通行',b['id'].split('/')[-1])])
                put(q,w.block(q),'replace numeric-only street sign with a legible public entrance', {w.block(q).partition('[')[0]},after_tag.snbt())
            elif w.block(q) in AIR and w.get(q[0],q[1],z1) not in AIR|{None}:
                text=nbtlib.Compound({'messages':nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text':s},ensure_ascii=False)) for s in (label,'入口 / 出口','人员通行',b['id'].split('/')[-1])]),'color':nbtlib.String('black'),'has_glowing_text':nbtlib.Byte(0)})
                new_tag=nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'front_text':text,'back_text':nbtlib.parse_nbt(text.snbt()),'is_waxed':nbtlib.Byte(1)})
                put(q,'minecraft:birch_wall_sign[facing=south,waterlogged=false]','supported legible public entrance sign',AIR,new_tag.snbt())
        # Native collision shapes, measured bearing and real hinge opening.
        def collision(state):
            if state is None:return None
            name=state.partition('[')[0]
            if name in AIR|{'minecraft:light'}:return []
            if 'hinge' in properties(state):
                state=state.replace('open=false','open=true')
                if state.startswith('projectseele:city_personnel_door'):state=state.replace('projectseele:city_personnel_door','minecraft:iron_door')
            result=shapes.get(state)
            if result is None:missing.add(state)
            return result
        feet=b['planned_floor_feet'][0]
        def clear(x,z):
            for y in (feet,feet+1):
                for q in collision(w.get(x,y,z)) or ():
                    if q[0]<.8 and q[3]>.2 and q[2]<.8 and q[5]>.2 and y+q[1]<feet+1.8 and y+q[4]>feet+.001:return False
                if collision(w.get(x,y,z)) is None:return False
            return True
        candidates=[d for d in doors if d['exterior'] and d['pos'][1]==feet]
        if b['style']=='old_danchi' and b.get('entry'):
            # The historical danchi manifest defines an open north stair
            # landing as its public entrance, rather than an apartment door.
            ex,_,ez=b['entry']
            if ez==z0-1:candidates.append(dict(pos=[ex,feet,z0],open_arch=True))
        tests=[];entrances=[]
        for d in candidates:
            x,_,z=d['pos'];dx,dz=(0,1) if z==z1 else (0,-1) if z==z0 else (1,0) if x==x1 else (-1,0)
            a=[x+.5,feet,z+.5];outside=[x+dx*2+.5,feet,z+dz*2+.5];inside=[x-dx*2+.5,feet,z-dz*2+.5]
            support=[]
            for n in range(-2,3):
                xx,zz=x+dx*n,z+dz*n;bs=collision(w.get(xx,feet-1,zz))
                bearing=bs is not None and any(q[0]<=.5<=q[3] and q[2]<=.5<=q[5] and abs(q[4]-1)<.001 for q in bs)
                support.append(dict(pos=[xx,feet,zz],bearing=bearing,clear=clear(xx,zz)))
            status='MEASURED_THRESHOLD_CONTINUOUS_NATIVE_USE_PENDING' if all(s['bearing'] and s['clear'] for s in support) else 'APPROACH_OR_APERTURE_REVIEW_REQUIRED'
            entrances.append(dict(door=d['pos'],normal=[dx,0,dz],threshold=support,status=status))
            action='open authored stair landing' if d.get('open_arch') else 'use door before walking'
            tests.extend([dict(id=b['id']+'/entry/'+str(len(entrances)),start=outside,end=inside,door=None if d.get('open_arch') else d['pos'],action=action),dict(id=b['id']+'/exit/'+str(len(entrances)),start=inside,end=outside,door=None if d.get('open_arch') else d['pos'],action=action)])
        status='ENTRANCES_MEASURED_NATIVE_PENDING' if candidates and all(e['status'].startswith('MEASURED_') for e in entrances) else 'REVIEW_REQUIRED'
        counts[status]+=1
        records.append(dict(id=b['id'],style=b['style'],street_front=identity if b['style']!='old_danchi' else 'preserved_old_danchi',
            planned_bounds=b['planned_bounds'],public_doors=doors,entrances=entrances,status=status,native_walk_cases=tests,
            actual_building_bounds=[[x0,y0,z0],[x1,y1,z1]],
            bookshop_ground_floor_components=bookshop_contents,
            clinic_ground_floor_components=clinic_contents,transport_owned_write_scope_preserved=transport_scope,
            floor_coverage='R43 all-storey and all-stair evidence inherited; current entrances measured; interiors and visual review pending'))
        if i%25==0:print('Measured authored building',i+1,'/193',flush=True)
    summary=dict(buildings=len(records),door_pairs=sum(len(b['public_doors']) for b in records),
        exact_changes=len(rows),states=dict(Counter(r['after'].partition('[')[0] for r in rows.values())),
        counts=dict(counts),unknown_collision_shapes=sorted(missing),
        unreviewed=[b['id'] for b in records if b['status']=='REVIEW_REQUIRED'],native_passed=False,visual_passed=False)
    emit(ART,list(rows.values()),records,summary);print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
