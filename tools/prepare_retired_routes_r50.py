"""Bounded original P1 reuse candidate; reads the sole construction world, never writes it."""
from pathlib import Path
from collections import Counter
import gzip,json,math
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from prepare_facilities_r48 import Author

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'artifacts/rebuild_r49/construction/SEELE_R49_WORLD'
OUT=ROOT/'artifacts/rebuild_r49/surface_r50/retired_routes_r50/P1_public_reuse_candidate_v1'
OLD_PLATFORM=-5325811690914780106
SOURCE=ROOT/'artifacts/world_expansion_r07/port_transit_geometry/ops.json.gz'

def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def cells(box):
    a,b,c,A,B,C=box
    for x in range(a,A+1):
        for y in range(b,B+1):
            for z in range(c,C+1):yield x,y,z

def main():
    assert not OUT.exists(),'Preserve previous exact candidates'
    native=json.loads((WORLD/'native_transit_r28.json').read_text(encoding='utf-8-sig'))
    assert not any(p['id']==OLD_PLATFORM for p in native['platforms']),'Original station is still operational; no retirement admitted'
    ops=json.load(gzip.open(SOURCE,'rt',encoding='utf-8'))
    approach=[o for o in ops if o['owner']=='r07/P1/city_walk']
    piers=[o for o in ops if o['owner']=='r07/P1/station_pier' and 438<=o['box'][0]<=558 and 453<=o['box'][2]<=496]
    assert len(approach)==6 and len(piers)==4
    original={q:o['state'] for o in approach for q in cells(o['box'])}
    assert len(original)==1584
    # R22 retired precisely this above-ground station volume. Retain its later
    # public guardrails and the supported forecourt, with no new underground port.
    frame=[470,77,457,554,108,487]
    source_points=set(original)|set(cells(frame))|{q for o in piers for q in cells(o['box'])}
    route_source=ROOT/'artifacts/rebuild_r44/surface_network/harbour_active_s1_link_v1/native_cases.json'
    successor=json.loads(route_source.read_text(encoding='utf-8-sig'))
    assert len(successor)==2 and successor[0]['path'][0]==[440.5,81,472.5] and successor[0]['path'][-1]==[372.5,81,230.5]
    assert any(p['id']==-1611773670322478178 for p in native['platforms']),'Real S1 successor platform absent'
    w=MeasuredWorld(WORLD)
    w.box((438,75,453),(558,109,496))
    for o in piers:w.box(tuple(o['box'][:3]),tuple(o['box'][3:]));w.around((o['box'][0],31,o['box'][2]),1)
    for p in successor[0]['path']:w.around(p,1)
    w.load();assert all(w.block(q) is not None for q in source_points),'Unread/proto source cells excluded whole'
    tags=dict(iter_block_entities(WORLD,w.dimension,(438,32,453),(558,109,496),selected_chunks=set(w.selected)))
    assert not tags,'Original receiver contains unexpected full NBT; preserve it and review before changing material'
    bearings=[]
    for o in piers:
        assert all(w.block(q)==o['state'] for q in cells(o['box']))
        q=o['box'][:3];below=w.get(q[0],31,q[2]);assert below not in AIR and below is not None
        bearings.append(dict(box=o['box'],exact_original_remaining=True,actual_base_state=below))
    changed={q:'minecraft:smooth_stone' for q,expected in original.items()
             if expected=='projectseele:nerv_floor_panel' and w.block(q)==expected}
    assert len(changed)==104,'Current original body differs from the complete measured 104-floor repair'
    differences=[dict(pos=q,original=v,current=w.block(q)) for q,v in original.items() if w.block(q)!=v]
    assert len(differences)==502
    source_rows=[]
    for q in sorted(source_points):
        before=w.block(q);after=changed.get(q,before)
        source_rows.append(dict(pos=list(q),before=before,after=after,before_nbt=None,after_nbt=None,
            owner='r50/retired_P1_public_plaza',reason='Original retired station approach reused as a plain supported public plaza link; preserve every later surface/guard and complete existing AIR'))
    OUT.mkdir(parents=True)
    author=Author(WORLD,OUT);author.s={q:w.block(q) for q in changed};author.t={}
    author.emit('M40_P1_supported_public_plaza', {q:(s,'Remove obsolete NERV station floor designation, retain the same complete supported public crossing',None) for q,s in changed.items()},
        dict(retired_platform=OLD_PLATFORM,original_source=str(SOURCE),original_positive_cells=1584,later_changed_cells_preserved=502,
             public_plaza_ground_frame=frame,original_bearings=bearings,new_underground_ports=False,native_verified=False,visual_verified=False))
    with gzip.open(OUT/'complete_generation_source.jsonl.gz','wt',encoding='utf-8') as f:
        for row in source_rows:f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
    author.all={tuple(r['pos']):r for r in source_rows};author.recipe()
    # Full actor/player shape admission remains for root. Record actual sample
    # obstacles honestly instead of repeating the stale R44 ready=false result.
    shapes=json.loads((WORLD/'native_collision_shapes.json').read_text(encoding='utf-8-sig'))
    route_failures=[];dynamic=[];unknown=[]
    for point in successor[0]['path']:
        x,y,z=point;ix,iz=math.floor(x),math.floor(z);floor=w.get(ix,math.floor(y-.001),iz);bs=shapes.get(floor)
        if bs is None:unknown.append(dict(point=point,state=floor,kind='floor'));continue
        yy=math.floor(y-.001)
        if not any(v[0]<=.2 and v[3]>=.8 and v[2]<=.2 and v[5]>=.8 and abs(yy+v[4]-y)<.001 for v in bs):route_failures.append(dict(point=point,state=floor,kind='actual_floor'))
        for yy in range(math.floor(y),math.ceil(y+1.8)):
            s=w.get(ix,yy,iz);bs=[] if s in AIR else shapes.get(s)
            if bs is None:unknown.append(dict(point=point,state=s,kind='head'));continue
            if any(v[0]<.8 and v[3]>.2 and v[2]<.8 and v[5]>.2 and yy+v[1]<y+1.8 and yy+v[4]>y+.001 for v in bs):
                target=dynamic if '_door' in s or 'ticket_barrier' in s else route_failures
                target.append(dict(point=point,state=s,kind='actual_head_envelope_requires_operation' if target is dynamic else 'actual_head_envelope'))
    cases=json.loads((WORLD/'quality_walk_cases.json').read_text(encoding='utf-8-sig'))
    retired=[c for c in cases if c['id'] in {'r07/P1/city_interchange','r07/P1/city_interchange/return'}];assert len(retired)==2
    new=[dict(c,id=c['id'].replace('r44/','r50/',1),native_passed=False,original_successor_source=str(route_source)) for c in successor]
    write(OUT/'metadata_patch.json',dict(schema=50,operations=[dict(file='quality_walk_cases.json',operation='replace_exact_two_entries_by_id',before=retired,after=new)],
        all_other_entries_preserved=True,world_written=False,root_only=True,requires_root_native_walk_before_acceptance=True))
    write(OUT/'report.json',dict(schema=50,world=str(WORLD),world_written=False,source_written=False,native_verified=False,visual_verified=False,
        original_platform_verified_retired=True,decision='PUBLIC_BEARING_REUSED_NOT_FLOATING_GRASS_OR_UNBOUNDED_STATION_EXCAVATION',
        changed_cells=len(changed),complete_generator_cells=len(source_rows),original_source_cells=1584,later_502_cells_unchanged=True,
        original_720_bearing_cells_unchanged=True,source_rows_include_complete_existing_AIR=True,
        obsolete_station_signs_and_body='No block entity or station sign remains in complete measured former station domain; above-ground contains only AIR plus42 later public edge-rail cells, preserved for safety.',
        successor=dict(platform=-1611773670322478178,route_points=len(successor[0]['path']),two_direction_cases=2,static_failures=route_failures,
                       dynamic_operations=dynamic,unknown_shapes=unknown,native_walked=False),
        generator='generation_recipe/file_patch.json: full current Static/Ground shard preserved; root must compose complete masks with simultaneous candidates, not replace whole conflicting shards',
        original_design_purpose='1995 TV separates ordinary surface/public transport from EVA sortie and deep restricted headquarters paths. Public plaza reuse and this precise discontinued P1 approach are original map engineering; no official scene-specific bridge demolition is claimed.',
        local_design_sources=['docs/TV_LAYOUT_REFERENCE_R08.md','docs/RECONSTRUCTION_R40.md','docs/REBUILD_R46.md','docs/QUALITY_CONTRACT_R43.md'],
        retired_producer_action='Old R07 P1 reconstruction must not be rerun in a native R22 through-service world; this complete source defines current public reuse and original deprecated platform never recreated.'))
    print('P1 original reuse',len(changed),'edits; full generator',len(source_rows),'cells; route failures',len(route_failures),'dynamic',len(dynamic),'unknown',len(unknown),flush=True)

if __name__=='__main__':main()
