"""Exact historical primitive attribution for R52's measured roof exceptions.

Observed coordinates/states come from Root's current native-shape receipt.
Primitive matching identifies provenance, never capacity or native driving.
"""
import gzip, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path

ART=Path('D:/eva/artifacts')
OUT=Path('.Codex/r52_runtime_close/roads_readonly/VEHICLE_COMPONENT_PROVENANCE.json')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def primitive_index(states,extra_ops=()):
    ops_sources=[
        ART/'world_quality_r02/extension_land_all/ops.json.gz',
        ART/'facility_r23/station_details/waiting_rooms_native_gates_and_guidance/ops.json.gz',
        ART/'facility_r23/access_finish/clear_station_ports_and_defense_access/ops.json.gz',
        ART/'facility_r23/stations/separated_stairs_and_guarded_platforms/ops.json.gz',
        ART/'world_quality_r02/estate_stations/ops.json.gz',
        ART/'facility_r30/lighting_refinement/interior_route_pendants/ops.json.gz',
        ART/'facility_r24/stations/supported_period_station_details/ops.json.gz',
        ART/'rebuild_r44/facility_transit_r44/platform_information_all_v1/mounted_platform_maps/ops.json.gz',
        ART/'access_r22/transit/civil/two_line_stations_and_viaducts/ops.json.gz',
        ART/'facility_r23/stations/verified_stair_landings_and_bridge_clearance/ops.json.gz',
    ]
    # Finite explicit operation exports only; no recursive artifact search.
    board_root=ART/'facility_r30/board_mounts'
    board_ops=sorted(board_root.glob('*/ops.json.gz'))
    ops_sources.extend(board_ops)
    ops_sources.extend(sorted((ART/'facility_r24/shops').glob('*/ops.json.gz')))
    ops_sources.extend(extra_ops)
    buckets=defaultdict(list);pins=[]
    for p in ops_sources:
        if not p.is_file():continue
        pins.append(dict(path=str(p),sha256=sha(p)))
        with gzip.open(p,'rt',encoding='utf8') as f:ops=json.load(f)
        for order,q in enumerate(ops):
            if q.get('state') not in states or q.get('mode')=='heightfield':continue
            if p==ops_sources[0] and q['owner'] not in ('extension/road_tunnel_roof','extension/tunnel_light'):continue
            b=q['box'];primitive=dict(source=str(p),owner=q['owner'],box=b,state=q['state'],operation_index=order)
            for cx in range(b[0]//16,b[3]//16+1):
                for cz in range(b[2]//16,b[5]//16+1):buckets[cx,cz].append(primitive)
    # The installed R45 station's precise material amendments, not a broad
    # room rectangle or a guessed association with a nearby station.
    station_tail=ART/'rebuild_r45/school_hakone_agent/hakone_v5/forward.jsonl.gz'
    pins.append(dict(path=str(station_tail),sha256=sha(station_tail)))
    with gzip.open(station_tail,'rt',encoding='utf8') as f:
        for line in f:
            q=json.loads(line)
            if q['after'] not in states:continue
            x,y,z=q['pos'];primitive=dict(source=str(station_tail),owner=q.get('owner','r45/hakone'),
                box=[x,y,z,x,y,z],state=q['after'],reason=q.get('reason'))
            buckets[x//16,z//16].append(primitive)
    shop_file=ART/'facility_r24/shops/contract.json'
    pins.extend(dict(path=str(p),sha256=sha(p)) for p in [shop_file,Path('tools/detail_station_shops_r24.py')])
    for shop in json.loads(shop_file.read_text('utf8'))['shops']:
        # Exact explicit fill formula; delta-only ops omit unchanged cells.
        x=shop['box'][0]+7;g=shop['floor'];z=shop['box'][2]+17
        for b,st,kind in [([x-6,g+4,z-12,x+5,g+4,z-12],'minecraft:green_terracotta','fascia'),
                          ([x-7,g+5,z-17,x+5,g+5,z-11],'minecraft:smooth_quartz_slab[type=bottom,waterlogged=false]','roof'),
                          ([x-6,g+1,z-16,x+5,g+4,z-16],'minecraft:white_concrete','back_wall'),
                          *[([x+u,g+1,z-15,x+u,g+4,z-12],'minecraft:white_concrete','side_or_partition_wall') for u in (-6,1,5)],
                          *[([x+u,g+1,z-12,x+u,g+1,z-12],'minecraft:green_terracotta','lower_front_panel') for u in (-5,-4,-1,0)],
                          ([x+4,g+1,z-12,x+4,g+1,z-12],'projectseele:period_fixture[facing=south,kind=cafe_counter]','counter')]:
            primitive=dict(source='tools/detail_station_shops_r24.py',owner='r24/station_cafe/'+shop['title']+'/'+kind,
                box=b,state=st,formula_metadata=str(shop_file))
            for cx in range(b[0]//16,b[3]//16+1):
                for cz in range(b[2]//16,b[5]//16+1):buckets[cx,cz].append(primitive)
    plots_file=ART/'world_quality_r02/surface_layout.json'
    canopies={}
    for q in json.loads(plots_file.read_text('utf8'))['kept_plots']:
        if 'storeys' not in q:continue
        x=q['entry'][0];z=q['bounds'][3];y=q['floor']+4
        for X in range(x-3,x+4):
            for Z in (z+1,z+2):canopies[X,y,Z]=dict(owner='r03/'+q['id']+'/entry_canopy',
                source='tools/refine_world_quality_r03.py:surface',state='minecraft:smooth_stone_slab[type=top,waterlogged=false]')
    frontage_file=ART/'facility_r24/city_frontages/contract.json'
    for q in json.loads(frontage_file.read_text('utf8'))['frontages']:
        x=q['original_entry'][0];z=q['bounds'][3];y=q['floor']+4
        for X in range(x-12,x+13):
            for Z in (z+1,z+2):canopies[X,y,Z]=dict(owner='r24/frontage/'+q['id']+'/entry_canopy',
                source='tools/detail_city_frontages_r24.py',state='minecraft:smooth_stone_slab[type=top,waterlogged=false]')
    pins.extend(dict(path=str(p),sha256=sha(p)) for p in [plots_file,frontage_file,
        Path('tools/refine_world_quality_r03.py'),Path('tools/detail_city_frontages_r24.py'),
        Path('tools/author_hakone_station_r45.py')])
    return buckets,canopies,pins

def main():
    receipt=ART/'r52_fresh_from_r51_20261009/final_map_audit/full_road_columns/CURRENT_ROAD_COLUMNS.json'
    observed=json.loads(receipt.read_text('utf8'))
    rows=[q for q in observed['issues'] if q['kind']=='VEHICLE_COMPONENT_REVIEW']
    states={min(q['obstruction'],key=lambda r:r[2])[1] for q in rows}
    buckets,canopies,pins=primitive_index(states)
    counts=Counter();classified=[]
    for q in rows:
        x,f,z=q['position'];o=min(q['obstruction'],key=lambda r:r[2]);y,st,minimum=o
        matches=[]
        for primitive in buckets[x//16,z//16]:
            b=primitive['box']
            if st==primitive['state'] and b[0]<=x<=b[3] and b[1]<=y<=b[4] and b[2]<=z<=b[5]:matches.append(primitive)
        if st=='minecraft:smooth_stone_slab[type=top,waterlogged=false]' and (x,y,z) in canopies:
            matches.append(canopies[x,y,z])
        if -1459<=x<=-1448 and z==688 and y==109 and st=='minecraft:oak_planks':
            matches.append(dict(owner='r45/hakone/staff_office/complete_ceiling',
                source='tools/author_hakone_station_r45.py:service_room',
                box=[-1460,109,683,-1447,109,690],state=st))
        status='EXACT_HISTORICAL_PRIMITIVE_MATCHES_OBSERVED_STATE' if matches else 'COMPONENT_SOURCE_UNRESOLVED_RETAIN_REVIEW'
        # First authoritative construction family is just a reporting bucket;
        # preserve every overlapping provenance rather than claiming uniqueness.
        owner=matches[0]['owner'] if matches else None
        counts[(owner.split('/')[0] if owner else 'unresolved',status)]+=1
        classified.append(dict(q,headroom_m=minimum-f,nearest_obstruction=o,
            source_primitive_matches=matches,status=status,vehicle_clearance_passed=False))
    result=dict(world=observed['world'],world_written=False,source_receipt=str(receipt),source_receipt_sha256=sha(receipt),
        source_component_pins=pins,observed_vehicle_columns=len(rows),
        component_family_counts=[dict(family=k[0],status=k[1],columns=v) for k,v in counts.items()],columns=classified,
        native_vehicle_route_passed=False,all_components_passed=False,
        limitations=['Attribution requires exact observed state and primitive coordinate; a station rectangle is never enough.',
            'Every overlapping historical match is preserved; this is not proof that a historical export is the latest owner.',
            'Matched roof/porch provenance is not a full width, intended vehicle capacity, native passage or art PASS.',
            'The inherited 6m screen cannot justify demolition of declared components.',
            'Root current road receipt predates its airport intersection correction; never relabel as after-repair.'])
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(dict(counts));print('unresolved nearest:',dict(Counter(q['nearest_obstruction'][1] for q in classified if not q['source_primitive_matches'])))

if __name__=='__main__':main()
