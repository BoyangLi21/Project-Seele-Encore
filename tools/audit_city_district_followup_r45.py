"""Current 96-object/identity/topology preconditions, through query_blocks only."""
import sys,json,gzip,hashlib,math,copy
from pathlib import Path
from collections import Counter
sys.dont_write_bytecode=True
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,palette_state
from measure_city_placements_r45 import unpack_pos
from regional_voxels import canonical_state
from install_city_rigid_metadata_r45 import same_tag
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r45/city_motion_sol_followup';WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW';DATA=WORLD/'dimensions/projectseele/geofront/data'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8')
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    topology=ROOT/'artifacts/rebuild_r45/city_motion/whole_topology_v2';bundle=ROOT/'artifacts/rebuild_r45/city_motion/install_bundle_v4'
    manifest=read(topology/'manifest.json');install=read(bundle/'manifest.json')
    identity=str(nbtlib.load(DATA/'projectseele_tokyo3_building_world_id_r44.dat')['data']['WorldUUID'])
    district=nbtlib.load(DATA/'projectseele_tokyo3_retraction.dat')['data']['Districts'][0]
    assert identity==manifest['world_id']==install['world_selector']['world_id']
    assert len(manifest['records'])==96 and sorted(r['index'] for r in manifest['records'])==list(range(96))
    w=MeasuredWorld(WORLD);objects=[];expected={};chunk_dependencies=set()
    for row in manifest['records']:
        index=row['index'];candidate=Path(row['cargo']);assert sha(candidate)==row['sha256'];building=nbtlib.load(candidate)['data']['Buildings'][0]
        centre=unpack_pos(int(building['Centre']));h=int(building['Height']);half=int(building['Half']);base=19-h if index<93 else -61
        footprint=building.get('R45Footprint');a,b,c,d=tuple(int(footprint[k]) for k in ('MinX','MaxX','MinZ','MaxZ')) if footprint is not None else (-half,half,-half,half)
        body=(b-a+1)*(d-c+1)*(h+4);ground=(b-a+1)*(d-c+1)
        before=DATA/candidate.name;source_tag=nbtlib.load(before)['data']['Buildings'][0] if before.exists() else building
        for cell in source_tag['Cargo']:
            x,y,z=unpack_pos(int(cell['Pos']));q=(centre[0]+x,base+y,centre[2]+z)
            assert q not in expected,('Cross-owner source collision',q,index)
            expected[q]=(index,cell);w.box(q,q)
        source_be=sum('NBT' in cell for cell in source_tag['Cargo']);added=len(building['Cargo'])-len(source_tag['Cargo'])
        old_byte_match=before.exists() and sha(before)==row['source'].get('source_archive_sha256') if index<93 else not before.exists()
        if index<93:
            original={int(cell['Pos']):cell for cell in source_tag['Cargo']};target={int(cell['Pos']):cell for cell in building['Cargo']}
            assert all(same_tag(cell,target[pos]) for pos,cell in original.items())
        chunks={(x,z) for x in range((centre[0]+a)//16,(centre[0]+b+1)//16+1) for z in range((centre[2]+c)//16,(centre[2]+d+1)//16+1)};chunk_dependencies|=chunks
        objects.append(dict(index=index,kind='generated' if index<93 else 'imported',centre=centre,full_cargo=len(building['Cargo']),original_cargo=len(source_tag['Cargo']),original_full_BE=source_be,added_floor_cells=added,
            source_archive= str(before),source_archive_exists=before.exists(),source_archive_epoch_matches=old_byte_match,candidate_sha256=sha(candidate),
            source_endpoint_base=base,target_surface_base=centre[1],height=h,footprint=[a,b,c,d],preparation_scan_cells=2*body+ground,
            rigid_detach_place_cells_lower_bound=2*len(building['Cargo']),ground_footprint_cells=ground,
            primitive_motion_ticks=math.ceil(abs(centre[1]-base)/.25)+math.ceil(abs(centre[1]-base)/.25)%2,
            route_chunk_dependencies=sorted(chunks),fixed_original_core=bool(source_tag['FixedStreetCore']) if index<93 else False))
    w.load();allpoints=list(expected);lo=tuple(min(q[k] for q in allpoints) for k in range(3));hi=tuple(max(q[k] for q in allpoints) for k in range(3))
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    counters=Counter();differences=[];full_be=0;be_differences=[];be_classes=Counter()
    for q,(index,cell) in expected.items():
        expected_state=canonical_state(palette_state(cell['State']));actual=w.block(q);tag=copy.deepcopy(cell.get('NBT'))
        if tag is not None:
            full_be+=1
            for k,v in zip(('x','y','z'),q):tag[k]=nbtlib.Int(v)
        eq_state=expected_state==actual;eq_tag=same_tag(tag,tags.get(q));counters['EXACT_FULL_STATE_NBT' if eq_state and eq_tag else 'DIFFERENT']+=1
        if tag is not None:
            actual_tag=tags.get(q);comparison=copy.deepcopy(actual_tag) if actual_tag is not None else None
            native_packing_only=False
            if comparison is not None and 'keepPacked' not in tag and isinstance(comparison.get('keepPacked'),nbtlib.Byte) and int(comparison['keepPacked'])==0:
                comparison.pop('keepPacked');native_packing_only=same_tag(tag,comparison)
            be_classes['EXACT_RAW_NBT' if eq_tag else 'ONLY_SERIALIZED_KEEP_PACKED_0' if native_packing_only else 'OTHER_FULL_NBT_DIFFERENCE']+=1
            if not eq_tag:be_differences.append(dict(index=index,pos=q,kind='ONLY_SERIALIZED_KEEP_PACKED_0' if native_packing_only else 'OTHER_FULL_NBT_DIFFERENCE',expected_full_snbt=tag.snbt(),actual_full_snbt=actual_tag.snbt() if actual_tag is not None else None))
        if not(eq_state and eq_tag) and len(differences)<100: differences.append(dict(index=index,pos=q,expected_state=expected_state,actual_state=actual,full_nbt_equal=eq_tag,expected_full_snbt=tag.snbt() if tag is not None else None,actual_full_snbt=tags[q].snbt() if q in tags else None))
    write('actual96_inventory.json',dict(world=str(WORLD),world_id=identity,district_full_snbt=district.snbt(),objects=objects,generated=93,imported=3,unique_source_coordinates=len(expected),source_full_BE=full_be,actual_status=dict(counters),difference_samples=differences,
        topology_authority_installed=(DATA/'projectseele_city_rigid_topology_r45_8246338109520.dat').exists(),control_WAL_installed=(DATA/'projectseele_city_rigid_control_r45_8246338109520.dat').exists(),
        metadata_WAL_in_bundle=(bundle/'metadata_wal.json').exists(),production_enabled=False,current_chunks=dict(Counter(w.status.values())),actual_full_BE_classes=dict(be_classes),world_written=False))
    write('complete1471_BE_serialized_differences.json',dict(actual_full_BE_classes=dict(be_classes),all_full_snbt_differences=be_differences,engine_field_not_removed_from_any_world_or_candidate=True,world_written=False))
    topology_rows=0;before_count=after_count=other_count=0;patch_diffs=[]
    for line in gzip.open(topology/'forward.jsonl.gz','rt',encoding='utf8'):
        row=json.loads(line);q=tuple(row['pos']);w.box(q,q);topology_rows+=1
    w.load()
    for line in gzip.open(topology/'forward.jsonl.gz','rt',encoding='utf8'):
        row=json.loads(line);q=tuple(row['pos']);actual=w.block(q)
        if actual==row['before']:before_count+=1
        elif actual==row['after']:after_count+=1
        else:
            other_count+=1
            if len(patch_diffs)<100:patch_diffs.append(dict(pos=q,before=row['before'],after=row['after'],actual=actual))
    write('actual_topology_preconditions.json',dict(positive_coordinates=topology_rows,before_match=before_count,after_match=after_count,foreign_current_state=other_count,foreign_samples=patch_diffs,
        forward_sha256=sha(topology/'forward.jsonl.gz'),inverse_sha256=sha(topology/'inverse.jsonl.gz'),installation_not_inferred_from_matches=True,world_written=False))
    c1=ROOT/'artifacts/rebuild_r45/city_motion/create_probe_v3/first_roundtrip_native/complete.json';result=read(c1)
    write('c1_effective_scope.json',dict(source=str(c1),source_sha256=sha(c1),passed=result['passed'],source_cells=result['cargo_cells'],source_full_BE=result['full_block_entities'],max_server_armorstand_feet_error=result['server_armorstand_max_feet_error'],unchanged_threshold=.35,
        input=str(ROOT/'artifacts/rebuild_r45/city_motion/native_control/20261002_085939/input.json'),anchor=[2048,160,2048],travel_distance=60,one_shadow_cargo_only=True,source_city_placements=result['controller_world_block_placements'],full96_migration_verified=False,player_client_collision_verified=result['native_client_collision_verified'],endpoint_transaction_ready=result['production_endpoint_transaction_ready']))
    count=sum(r['preparation_scan_cells'] for r in objects);work=sum(r['rigid_detach_place_cells_lower_bound']+2*r['ground_footprint_cells'] for r in objects);maxmotion=max(r['primitive_motion_ticks'] for r in objects)
    write('cost_and_dependencies.json',dict(current_candidate_objects=96,unique_mandatory_chunk_tickets=len(chunk_dependencies),route_chunks=sorted(chunk_dependencies),prepare_scan_cells=count,optimistic_prepare_ticks_4096=math.ceil(count/4096),rigid_endpoint_work_upper_model=work,
        optimistic_endpoint_placement_ticks_4096=math.ceil(work/4096),motion_ticks=maxmotion,motion_seconds_at20TPS=maxmotion/20,
        durations_seconds_are_not_native_performance=True,cargo_immutable_cache_effect='Avoid repeated full Plan.cargo construction during preflight/spawn/verify; retain complete per-cell BE copies',
        hard_phase_barriers_retained=['begin','worldTouched before first placement','per-object WAL durable before OPEN','phase transitions','SPAWN owner insertion','endpoint world native flush','COMMIT','FAULT','normal server stop'],
        server_heap_generator='tools/build_server_ready_pack.py',server_memory_source_verified='-Xms2G\n-Xmx20G' in (ROOT/'tools/build_server_ready_pack.py').read_text('utf8'),source_not_built=True,world_written=False))
    print('Actual96',dict(counters),'BE',full_be,'topology',before_count,after_count,other_count,'unique chunks',len(chunk_dependencies),'candidate motion ticks',maxmotion,flush=True)
if __name__=='__main__':main()
