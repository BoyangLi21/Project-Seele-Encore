"""Require the coast's full physical and geographic proof before publication."""
import argparse,gzip,json
from pathlib import Path
import numpy as np
from shapely.geometry import shape,box
from shapely.ops import unary_union

NAME='Odawara Miyukinohama and Hamacho coastal promenade'

def verify(a):
    C=a.candidate;spec=json.loads((C/'plan/authored-design.json').read_text('utf8'))
    if spec['name']!=NAME:raise ValueError('Unexpected coast specification')
    check=json.loads((C/'independent-check.json').read_text('utf8'))
    if check['errors']or json.loads((C/'functional-check.json').read_text('utf8'))['errors']:raise ValueError('Unresolved physical coast check')
    before=json.loads((a.before_components/'floating-components.json').read_text('utf8'))
    after=json.loads((a.after_components/'floating-components.json').read_text('utf8'))
    capture=json.loads((C/'capture.json').read_text('utf8'))
    for r in (before,after):
        if r['full_chunks']!=capture['chunk_statuses']['full']or r['definite_floating']or r['unknown_components']:raise ValueError('Incomplete or floating coast volume')
    with np.load(C/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    with np.load(spec['geographic_water_mask'])as f:
        if not np.array_equal(f['bounds'],d['bounds']):raise ValueError('Wrong water frame')
        if np.any(f['wet']&(d['walk']|d['plots'])):raise ValueError('Coastal public or plot water overlap')
    water_edits=0
    for p in (C/'delta').glob('*.npz'):
        with np.load(p)as f:
            names=list(map(str,f['palette']));ids=np.asarray([s.split('[')[0]=='minecraft:water'for s in names])
            water_edits+=int(np.sum(ids[f['before']]|ids[f['after']]))
    if water_edits:raise ValueError('Coast candidate rewrote water')
    fs=json.load(gzip.open(a.geography/'features.world.geojson.gz','rt',encoding='utf8'))['features']
    bypass=unary_union([shape(f['geometry'])for f in fs if f['properties']['source_layer']=='RdCL'and f['properties'].get('vt_tollsect')=='有料'])
    updated={r['id']:r for r in json.loads((C/'plan/buildings.json').read_text('utf8'))}
    counts=0;minimum=float('inf')
    for row in json.loads((a.authority/'catalog.json').read_text('utf8')):
        if not row['id'].startswith('odawara-core/'):continue
        bounds=updated[row['id']]['new_payload_bounds']if row['id']in updated else row['occupied_bounds']
        distance=box(bounds[0],bounds[2],bounds[3],bounds[5]).distance(bypass)
        if distance<6:raise ValueError(('Building occupies coastal road reserve',row['id'],distance))
        minimum=min(minimum,distance);counts+=1
    if counts!=47:raise ValueError('Incomplete retained city building audit')
    kept=json.loads((C/'retained-public-check.json').read_text('utf8'))
    with np.load(a.authority/'network.npz')as f:
        ax,az,_,_=map(int,f['bounds']);x,z,X,Z=map(int,d['bounds']);old=f['walk'][z-az:Z-az+1,x-ax:X-ax+1]
    with np.load(C/'plan/retained-public.npz')as f:
        if np.any(old&~f['walk']):raise ValueError('Original public surface missing from preservation proof')
    if kept['errors']or int(old.sum())!=14123:raise ValueError('Prior downtown public surfaces changed')
    if check['reachable_columns']!=check['full_width_columns']:raise ValueError('Unreachable coastal public surface')
    if check['parcel_payload_cells_exact']!=check['parcel_payload_cells_checked']or not all(r['connected']for r in check['parcel_goals']):raise ValueError('Moved building or its entrance changed')
    detail=json.loads((C/'coastal-details.json').read_text('utf8'))
    summary=json.loads((a.design/'coastal-summary.json').read_text('utf8'))
    report=dict(candidate=str(C),status='verified candidate; installation separate',full_chunks=capture['chunk_statuses']['full'],
        promenade_length=summary['promenade_length'],city_access_ramps=len(summary['access']),
        public_columns=check['full_width_columns'],new_public_columns=check['full_width_columns']-int(old.sum()),
        all_public_columns_reachable=True,retained_public_cells_exact=kept['cells'],relocated_buildings=len(updated),
        complete_parcel_cells_exact=check['parcel_payload_cells_exact'],relocated_device_tags_exact=check['complete_device_tags_exact'],
        retained_device_tags_exact=check['retained_device_tags_unchanged'],retained_room_volume_cells_exact=check['native_room_volume_cells_unchanged'],
        city_buildings_retained=counts,minimum_building_coastal_road_distance=minimum,
        dry_beach_surface_columns=detail['dry_beach_surface_columns'],rest_points=len(detail['rest_points']),
        water_cells_changed=water_edits,water_public_conflicts=0,definite_floating_after=0,unknown_components_after=0,
        remaining_civil_interfaces=summary['access'],native_game_ui_verified=False,world_written=False,
        phase_1_complete=False,un_relocation_allowed=False)
    (C/'coastal-release-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k!='remaining_civil_interfaces'},ensure_ascii=False),flush=True)

def require_verified(candidate):
    p=candidate/'plan/authored-design.json'
    if not p.exists()or json.loads(p.read_text('utf8')).get('name')!=NAME:return
    r=json.loads((candidate/'coastal-release-check.json').read_text('utf8'))
    if Path(r['candidate']).resolve()!=candidate.resolve()or not r['all_public_columns_reachable']:raise ValueError('Unverified coastal candidate')
    if any(r[k]for k in ('water_cells_changed','water_public_conflicts','definite_floating_after','unknown_components_after')):raise ValueError('Unresolved coastal conflict')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('candidate','design','authority','geography','before-components','after-components'):p.add_argument('--'+n,type=Path,required=True)
    verify(p.parse_args())
