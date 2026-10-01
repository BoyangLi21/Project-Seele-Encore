"""Freeze reviewable exact city input, real station journeys and native cameras; no writes."""
from pathlib import Path
from collections import deque,Counter
import argparse,gzip,json,math,hashlib,shutil
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('--audit-report',type=Path);a=p.parse_args();output=a.plan/'construction_contract.json';assert not output.exists()
    district=json.loads((a.plan/'new_district.json').read_text('utf8'))
    rows=[json.loads(s) for s in gzip.open(a.plan/'forward.jsonl.gz','rt',encoding='utf8')]
    inverse=[json.loads(s) for s in gzip.open(a.plan/'inverse.jsonl.gz','rt',encoding='utf8')]
    assert len(rows)==len(inverse) and len({tuple(r['pos']) for r in rows})==len(rows)
    for first,back in zip(rows,inverse):
        assert first['pos']==back['pos'] and first['before']==back['after'] and first['after']==back['before']
        assert first.get('before_nbt')==back.get('after_nbt') and first.get('after_nbt')==back.get('before_nbt')
    patch={tuple(r['pos']):r['after'] for r in rows}
    allcases=json.loads((WORLD/'quality_walk_cases.json').read_text('utf8'))
    sourcecases=[c for c in allcases if '/station/'+district['operating_platform']+'/ground_entrance_' in c['id'] and not c['id'].endswith('/return')]
    civil_contract=ROOT/'artifacts/access_r22/transit/civil/station_contract.json'
    civil=json.loads(civil_contract.read_text('utf8'))
    source_station=next(s for s in civil['stations'] if any('/'+district['operating_platform']+'/' in c['id'] for c in s['walks']))
    if not sourcecases:sourcecases=[c for c in source_station['walks'] if '/ground_access_' in c['id'] and not c['id'].endswith('/return')]
    assert sourcecases,'Source actual station entrances must exist; do not create a station label'
    raw=np.load(ROOT/'artifacts/rebuild_r44/surface_network/road_complete_authority_stage3.columns.npz')
    station_goals=[tuple(math.floor(v) for v in c['path'][0]) for c in sourcecases]
    x0,x1,z0,z1=district['bounds'];x0=min(x0,min(q[0] for q in station_goals))-16;x1=max(x1,max(q[0] for q in station_goals))+16
    z0=min(z0,min(q[2] for q in station_goals))-16;z1=max(z1,max(q[2] for q in station_goals))+16
    select=(raw['coordinates'][:,0]>=x0)&(raw['coordinates'][:,0]<=x1)&(raw['coordinates'][:,1]>=z0)&(raw['coordinates'][:,1]<=z1)&((raw['flags']&7)==7)
    h={tuple(map(int,q)):float(y) for q,y in zip(raw['coordinates'][select],raw['actual_feet'][select])}
    forecourt=ROOT/'artifacts/rebuild_r44/surface_network/whole_station_forecourt_authority_v1/road_authority.json'
    for col in json.loads(forecourt.read_text('utf8'))['columns']:
        x,z=col['pos']
        if x0<=x<=x1 and z0<=z<=z1:h[x,z]=col['native_feet']
    # Recover the entire exact positive source station floor, including the
    # Tokyo and Kirisato stations omitted from the earlier three-station
    # authority supplement. Current native support/headroom still veto it.
    civil_ops=ROOT/'artifacts/access_r22/transit/civil/two_line_stations_and_viaducts/ops.json.gz'
    ops=json.load(gzip.open(civil_ops,'rt',encoding='utf8'))
    source_floors=[o for o in ops if o['owner']=='r22/station/'+district['operating_platform'] and o['box'][1]==o['box'][4]==source_station['ground'] and o['state']=='minecraft:smooth_stone']
    assert len(source_floors)==1
    x,y,z,X,Y,Z=source_floors[0]['box']
    for xx in range(x,X+1):
        for zz in range(z,Z+1):h[xx,zz]=y+1
    for col in json.loads((a.plan/'road_authority.json').read_text('utf8'))['columns']:h[tuple(col['pos'])]=col['native_feet']
    for authority in district.get('retained_current_street_authorities',[]):
        for col in json.loads(Path(authority).read_text('utf8'))['columns']:h[tuple(col['pos'])]=col['native_feet']
    x0=min(x0,min(q[0] for q in h));x1=max(x1,max(q[0] for q in h));z0=min(z0,min(q[1] for q in h));z1=max(z1,max(q[1] for q in h))
    # R23's real ground entrance extends beyond the rectangular R22 plinth.
    # These are frozen source-authored entrance legs, not invented road-mask
    # islands or permission inferred from a standing surface.
    for case in sourcecases:
        for first,last in zip(case['path'],case['path'][1:]):
            if abs(first[1]-last[1])>.01:continue
            length=max(abs(first[0]-last[0]),abs(first[2]-last[2]));steps=max(1,math.ceil(length*2))
            for i in range(steps+1):
                x=math.floor(first[0]+(last[0]-first[0])*i/steps);z=math.floor(first[2]+(last[2]-first[2])*i/steps)
                for dx in (-1,0,1):
                    for dz in (-1,0,1):h[x+dx,z+dz]=first[1]
    ymin=min([min(h.values())]+[r['pos'][1] for r in rows])-3;ymax=max([max(h.values())+7]+[r['pos'][1]+5 for r in rows])
    w=MeasuredWorld(WORLD);w.box((x0,min(40,math.floor(ymin)),z0),(x1,max(220,math.ceil(ymax)),z1));w.load()
    shapes={canonical_state(k):v for k,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    def state(q):return patch.get(q,w.block(q))
    def boxes(st):return [] if st in AIR else shapes.get(st)
    def standable(q,feet):
        x,z=q;supported=False
        for y in range(math.floor(feet)-2,math.ceil(feet)):
            b=boxes(state((x,y,z)))
            if b is not None and any(t[0]<=.2 and t[3]>=.8 and t[2]<=.2 and t[5]>=.8 and abs(y+t[4]-feet)<.001 for t in b):supported=True
        if not supported:return False
        for y in range(math.floor(feet),math.ceil(feet+1.8)):
            b=boxes(state((x,y,z)))
            if b is None or any(t[0]<.8 and t[3]>.2 and t[2]<.8 and t[5]>.2 and y+t[1]<feet+1.8 and y+t[4]>feet+.001 for t in b):return False
        return True
    valid={q:feet for q,feet in h.items() if standable(q,feet)}
    journeys=[];unresolved=[]
    for building in district['buildings']:
        sx,sy,sz=building['actual_street_handoff'];start=(int(sx),int(sz));todo=deque([start]);parents={start:None};target=None;source=None
        goals={(q[0],q[2]):c for q,c in zip(station_goals,sourcecases) if (q[0],q[2]) in valid and abs(valid[q[0],q[2]]-q[1])<.01}
        while todo:
            q=todo.popleft()
            if q in goals:target=q;source=goals[q];break
            for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
                nxt=q[0]+dx,q[1]+dz
                if nxt in valid and nxt not in parents and abs(valid[nxt]-valid[q])<=.501:parents[nxt]=q;todo.append(nxt)
        if target is None:
            near=[min(parents,key=lambda q:(q[0]-g[0])**2+(q[1]-g[2])**2) for g in station_goals]
            unresolved.append(dict(building=building['id'],start=start,start_statically_standable=start in valid,actual_station_goals=station_goals,
                goal_statically_standable=[(g[0],g[2]) in valid for g in station_goals],reachable_columns=len(parents),nearest_reachable=near,
                reason='Actual complete street graph does not reach the source operating-station entrance'));continue
        route=[];q=target
        while q is not None:route.append(q);q=parents[q]
        route.reverse();streetpath=[[x+.5,valid[x,z],z+.5] for x,z in route]
        existing_entry=json.loads(json.dumps(source))
        entry_case=next(c for c in json.loads((a.plan/'native_cases.json').read_text('utf8')) if c['id']==building['id']+'/public_entry/return')
        # End at the exact original station street approach, before the live
        # card barrier. Root's complete native card/boarding suite owns the
        # continuation through that gate; never pretend it is static air.
        path=entry_case['path']+streetpath[1:]
        identity=building['id']+'/to_operating_station'
        for suffix,pth in [('',path),('/return',path[::-1])]:journeys.append(dict(id=identity+suffix,path=pth,native_passed=False,source_station_case_id=source['id'],source_station_case_sha256=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest(),physical_street_columns=len(route)))
    exact_errors=[];earth=[]
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(x0,math.floor(ymin),z0),(x1,math.ceil(ymax),z1),selected_chunks=set(w.selected)))
    for r in rows:
        q=tuple(r['pos']);observed=w.block(q);tag=tags[q].snbt() if q in tags else None
        if observed!=r['before'] or tag!=r.get('before_nbt'):exact_errors.append(dict(pos=q,expected=r['before'],observed=observed,expected_nbt=r.get('before_nbt'),observed_nbt=tag))
    inherited_earth=None
    if (a.plan/'delta_provenance.json').exists():
        delta=json.loads((a.plan/'delta_provenance.json').read_text('utf8'));foundation_source=Path(delta['installed'])/'foundation_profiles.json'
        inherited_earth={v['building']:dict(v,inherited_source=str(foundation_source),inherited_source_sha256=sha(foundation_source)) for v in json.loads(foundation_source.read_text('utf8'))['buildings']}
    for b in district['buildings']:
        x,z,X,Z=b['bounds'];samples=[]
        if inherited_earth is not None:earth.append(inherited_earth[b['id']]);continue
        for xx in range(x,X+1):
            for zz in range(z,Z+1):
                ground=max([yy for yy in range(math.floor(ymin),math.ceil(ymax)) if (w.get(xx,yy,zz) or '').split('[')[0]=='minecraft:grass_block'],default=None)
                samples.append(dict(pos=[xx,zz],old_grass_y=ground,foundation_floor=b['floor'],cut_fill_metres=None if ground is None else b['floor']-ground))
        earth.append(dict(building=b['id'],full_footprint_columns=len(samples),maximum_cut_fill=max(abs(s['cut_fill_metres']) for s in samples if s['cut_fill_metres'] is not None),profiles=samples))
    cameras=[]
    def add(name,at,target,anchors,covered=None):
        eye=[at[0],at[1]+1.62,at[2]];observed=state(tuple(math.floor(v) for v in eye))
        if name.startswith('whole_') and observed not in AIR:
            options=[[cx*16+8,at[1],cz*16+8] for (cx,cz),status in w.status.items() if status=='full' and state((cx*16+8,math.floor(eye[1]),cz*16+8)) in AIR and all(math.dist([cx*16+8,eye[1],cz*16+8],q)<=148 for q in anchors)]
            assert options,('No actual loaded aerial whole-district camera',name)
            at=min(options,key=lambda p:math.dist(p,at));eye=[at[0],at[1]+1.62,at[2]];observed=state(tuple(math.floor(v) for v in eye))
        assert observed in AIR,(name,eye,observed)
        maximum=max(math.dist(eye,q) for q in anchors)
        assert maximum<=148,(name,'Required real component extends beyond bounded rd10 loading',maximum)
        d=[target[i]-eye[i] for i in range(3)];cameras.append(dict(file='r44_'+district['id']+'_'+name+'.png',position=at,yaw=math.degrees(math.atan2(-d[0],d[2])),pitch=-math.degrees(math.atan2(d[1],math.hypot(d[0],d[2]))),warmupTicks=360,requiredSections=anchors,action='daytime:6000',covered_components=covered or [],maximum_required_distance=maximum,required_render_distance_chunks=10))
    bx0,bx1,bz0,bz1=district['bounds'];meanfeet=sum(b['floor']+1 for b in district['buildings'])/len(district['buildings'])
    # Every complete building is covered by two bounded neighbourhood views.
    # Never attach a 500m-away district anchor to a rd10/160m camera.
    groups=[]
    for b in sorted(district['buildings'],key=lambda b:(b['bounds'][0],b['bounds'][1])):
        chosen=None
        for g in groups:
            boxes=[v['bounds'] for v in g]+[b['bounds']]
            if max(v[2] for v in boxes)-min(v[0] for v in boxes)<=80 and max(v[3] for v in boxes)-min(v[1] for v in boxes)<=80:chosen=g;break
        if chosen is None:groups.append([b])
        else:chosen.append(b)
    for index,g in enumerate(groups):
        ax=min(b['bounds'][0] for b in g);az=min(b['bounds'][1] for b in g);AX=max(b['bounds'][2] for b in g);AZ=max(b['bounds'][3] for b in g);height=sum(b['floor']+1 for b in g)/len(g)
        centre=[(ax+AX)/2,height+8,(az+AZ)/2];anchors=[]
        for b in g:
            x,z,X,Z=b['bounds'];anchors.extend([[xx,yy,zz] for xx in [x-1,X+1] for zz in [z-1,Z+1] for yy in [b['floor'],b['roof']+8]])
            anchors.append(b['door'])
        for corner,dx,dz in [('south_east',12,16),('north_west',-12,-16)]:add('whole_group'+str(index).zfill(2)+'_'+corner,[centre[0]+dx,height+54,centre[2]+dz],centre,anchors,[b['id'] for b in g])
    for b in district['buildings']:
        ex,feet,ez=b['entry'];hx,hy,hz=b['actual_street_handoff'];facing=b.get('facing','south');dx,dz={'south':(0,1),'north':(0,-1),'east':(1,0)}[facing]
        at=[ex+dx*3+.5,feet,ez+dz*3+.5]
        if state(tuple(math.floor(v) for v in [at[0],at[1]+1.62,at[2]])) not in AIR:at=[hx+.5,hy,hz+.5]
        add(b['id'].split('/')[-1]+'_front',at,[b['door'][0]+.5,b['floor']+2,b['door'][2]+.5],[b['door'],[b['bounds'][0],b['roof'],b['bounds'][1]]], [b['id']])
    assert set(b['id'] for b in district['buildings'])=={identity for c in cameras if c['file'].find('_whole_')>=0 for identity in c['covered_components']}
    (a.plan/'camera_itinerary.json').write_text(json.dumps(cameras,indent=2),'utf8')
    (a.plan/'station_journeys.json').write_text(json.dumps(dict(cases=journeys,unresolved=unresolved,source_station_cases=sourcecases,current_authorized_clear_street_columns=len(valid),source_cases_preserved=True,native_passed=False,world_written=False),ensure_ascii=False,indent=2),'utf8')
    (a.plan/'foundation_profiles.json').write_text(json.dumps(dict(buildings=earth,world_written=False),indent=2),'utf8')
    whole_file=a.audit_report or max((f for f in a.plan.glob('whole_component_audit*.json') if '.native_' not in f.name),key=lambda f:f.stat().st_mtime_ns)
    base=json.loads((a.plan/'native_cases.json').read_text('utf8'));floor_file=whole_file.with_suffix('.native_floor_cases.json');floorcases=json.loads(floor_file.read_text('utf8'))
    court_file=whole_file.with_suffix('.native_court_cases.json');courtcases=json.loads(court_file.read_text('utf8')) if court_file.exists() else []
    native_cases=base+floorcases+courtcases+journeys;assert len(native_cases)==len({c['id'] for c in native_cases})
    (a.plan/'all_native_cases.json').write_text(json.dumps(native_cases,ensure_ascii=False,indent=2),'utf8')
    whole=json.loads(whole_file.read_text('utf8'))
    sources=[ROOT/'tools/plan_new_city_blocks_r44.py',ROOT/'tools/audit_new_city_blocks_r44.py',ROOT/'tools/finalize_city_candidate_r44.py',
        ROOT/'tools/derive_installed_city_delta_r44.py',ROOT/'tools/query_blocks.py',ROOT/'tools/measure_world_r40.py',ROOT/'tools/regional_voxels.py',ROOT/'tools/inspect_map_assets.py',
        ROOT/'src/main/java/com/projectseele/world/CityPersonnelDoorR44.java',ROOT/'src/main/java/com/projectseele/registry/ModBlocks.java',ROOT/'src/main/java/com/projectseele/registry/ModItems.java',
        WORLD/'native_collision_shapes.json',ROOT/'artifacts/repair_r43/transit_resolved/native_snapshot.json',civil_contract,civil_ops]
    if (a.plan/'parcel_components.json').exists():
        sources.append(ROOT/'tools/plan_city_parcels_and_facades_r44.py')
        detail_contract=ROOT/'artifacts/rebuild_r44/city_expansion/rain_detail_assets_v3/shape_contract.json'
        sources.append(detail_contract)
        sources.extend(Path(e['path']) for e in json.loads(detail_contract.read_text('utf8'))['files'])
    if (a.plan/'architecture_components.json').exists():
        sources.extend([ROOT/'tools/city_period_architecture_r44.py',ROOT/'tools/plan_city_period_revision_r44.py',ROOT/'tools/render_city_terrain_candidate_r44.py'])
    if district.get('producer_design_file'):sources.append(Path(district['producer_design_file']))
    sources.extend(Path(p) for p in district.get('retained_current_street_authorities',[]))
    if district.get('preserved_margin_audit_file'):sources.append(Path(district['preserved_margin_audit_file']))
    fixture_guard=ROOT/'tools/information_fixture_guard_r44.py'
    if fixture_guard.exists():sources.append(fixture_guard)
    if (a.plan/'tv_landmark_components.json').exists():sources.append(ROOT/'tools/tv_landmark_architecture_r44.py')
    review=json.loads((a.plan/'audit.json').read_text('utf8'))
    source_inputs=a.plan/'source_inputs';source_inputs.mkdir()
    epochs=[]
    for i,f in enumerate(sources):
        snapshot=source_inputs/(str(i).zfill(2)+'_'+f.name);shutil.copy2(f,snapshot)
        epochs.append(dict(path=str(snapshot.resolve()),original_path=str(f.resolve()),sha256=sha(snapshot),immutable_snapshot=True))
    repair=(a.plan/'delta_provenance.json').exists()
    contract=dict(plan=str(a.plan.resolve()),district=district['id'],new_buildings=0 if repair else len(district['buildings']),new_occupied_floors=0 if repair else len(district['floors']),
        complete_existing_building_components_reviewed=len(district['buildings']) if repair else 0,complete_existing_floor_planes_reviewed=len(district['floors']) if repair else 0,
        static_full_component_passed=whole['static_passed'],exact_current_preconditions_passed=not exact_errors,exact_errors=exact_errors,station_journeys_complete=not unresolved,
        native_cases=len(native_cases),current_world_written=False,native_passed=False,actual_photos_captured=False,visual_passed=False,authoritative_release_ready=False,
        root_may_apply_to_single_review_world=whole['static_passed'] and not exact_errors and not unresolved and not review['held'] and not review['rail_conflicts'],
        files={name:dict(path=str((a.plan/name).resolve()),sha256=sha(a.plan/name)) for name in ['forward.jsonl.gz','inverse.jsonl.gz','new_district.json','ecology_reservations.json','road_authority.json','all_native_cases.json','station_journeys.json','camera_itinerary.json','foundation_profiles.json']},
        source_epochs=epochs,source_world_identity='The single local authorized SEELE_FIELD_R44_REVIEW; source local world and all player/entity/traffic progress remain independent',
        requires_before_apply=['Root owns the world write window and rechecks every exact old state/full NBT against this forward input.',
            'Root has compiled the CityPersonnelDoorR44 registry and current resources; source hash is required, not an assumption of installed class.',
            'This forward contains '+str(len(district['buildings']))+' complete building components and its exact street changes. An installed repair delta must not replay any prior full-city forward.',
            'Merge full actual roof/stair-head/door/all-width street protection into both future provider epochs before reseeding ecology.'],
        requirements_after_apply=['Run all_native_cases.json with existing native FakePlayer movement and real manual door use.',
            'Capture camera_itinerary.json on the actual shader client, review entrances, side facade, eaves/drainage, stairs, all public floors/roofs and whole terrain transition.',
            'True driven full-size vehicle sweeps/turns, real station boarding and state/reload remain mandatory.',
            'Read back exact installed copy; never copy QA world player/entity/traffic progress into source.'],
        scope='This '+str(len(district['buildings']))+'-building '+district['id']+' construction candidate advances actual city expansion. It does not close global cities/independent housing,799 road objects or675 old tree obligations; native and actual shader acceptance remain separate.')
    if whole.get('source_shape_native_verification_pending'):
        contract['new_source_model_collision_boxes_verified']=True;contract['new_class_native_collision_shapes_required']=whole['source_shape_dependencies']
        contract['new_classes_native_verified']=False
        contract['requires_before_apply'].append('Root compiles/initializes CityRainPipeR44 and CityRainGutterR44 and remeasures all12 registered states with ShapeInputsR44. Check source/model parity and exact real collision boxes before placing this new registered-state delta.')
    output.write_text(json.dumps(contract,ensure_ascii=False,indent=2),'utf8')
    print(district['id'],'applyable to REVIEW',contract['root_may_apply_to_single_review_world'],'journeys',len(journeys),'unresolved',len(unresolved),'nativecases',len(native_cases),'exact-errors',len(exact_errors),'maxearth',max(r['maximum_cut_fill'] for r in earth),flush=True)


if __name__=='__main__':main()
