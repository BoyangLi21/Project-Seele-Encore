"""Combine physical traversal, water/rail reservation and whole-volume proofs."""
import argparse
import gzip
import json
from pathlib import Path

import numpy as np
from shapely import contains_xy
from shapely.geometry import shape
from shapely.ops import unary_union


def verify(a):
    C=a.candidate;checks={name:json.loads((C/name).read_text('utf8'))for name in ('functional-check.json','independent-check.json','new-frontages-check.json','carriageway-markings.json')}
    for name in ('functional-check.json','independent-check.json','new-frontages-check.json'):
        if checks[name]['errors']:raise ValueError(('Candidate traversal errors',name))
    with np.load(C/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    spec=json.loads((C/'plan/authored-design.json').read_text('utf8'))
    with np.load(spec['geographic_water_mask'])as f:
        if not np.array_equal(f['bounds'],d['bounds']):raise ValueError('Water survey frame differs')
        wet=f['wet']
    if np.any(wet&(d['walk']|d['plots'])):raise ValueError('Public pavement or building plot occupies a surveyed water body')
    before=json.loads((a.before_components/'floating-components.json').read_text('utf8'))
    after=json.loads((a.after_components/'floating-components.json').read_text('utf8'))
    capture=json.loads((C/'capture.json').read_text('utf8'));full_chunks=capture['chunk_statuses']['full']
    if before['full_chunks']!=full_chunks or after['full_chunks']!=full_chunks:raise ValueError('Incomplete volume scan')
    if any(r['definite_floating']or r['unknown_components']for r in (before,after)):raise ValueError('New district has an unsupported or unmeasured component')
    with gzip.open(a.geography/'features.world.geojson.gz','rt',encoding='utf8')as f:features=json.load(f)['features']
    rail=unary_union([shape(r['geometry'])for r in features if r['properties']['source_layer']=='RailCL']).buffer(3)
    x,z,X,Z=map(int,d['bounds']);zz,xx=np.mgrid[z:Z+1,x:X+1]
    if np.any(contains_xy(rail,xx,zz)&(d['walk']|d['plots'])):raise ValueError('Full public width or building plot enters the future railway corridor')
    detail=json.loads((C/'street-details.json').read_text('utf8'));front=checks['new-frontages-check.json'];profile=checks['independent-check.json']
    if front['reachable_room_and_landing_goals']!=front['room_and_landing_goals']or profile['reachable_columns']!=int(d['walk'].sum()):raise ValueError('Unreachable district destination')
    if len(front['entries'])!=len(json.loads((C/'new-frontages.json').read_text('utf8'))['buildings']):raise ValueError('Incomplete building entrance check')
    ground=d['ground'].astype(int)-d['old_ground'].astype(int)
    report=dict(status='verified candidate; installation separate',candidate=str(C),full_chunks=full_chunks,buildings=len(front['entries']),
        public_columns=int(d['walk'].sum()),all_public_columns_reachable=True,road_columns=int(d['road'].sum()),street_chains=len(profile['streets']),
        street_length=sum(r['length']for r in profile['streets']),maximum_actual_10m_grade=max(r['maximum_actual_10m_grade']or 0 for r in profile['streets']),
        room_and_landing_goals=front['room_and_landing_goals'],reachable_room_and_landing_goals=front['reachable_room_and_landing_goals'],
        stair_columns=front['stair_columns'],new_building_device_tags=front['new_device_tags_checked'],native_frontage_fixtures=len(detail['native_fixtures']),
        lights=len(detail['lights']),trees=len(detail['trees']),centre_dash_cells=checks['carriageway-markings.json']['cells'],
        definite_floating_before=0,definite_floating_after=0,unknown_floating_components=0,water_public_and_parcel_conflicts=0,geographic_rail_corridor_conflicts=0,
        minimum_ground_delta=int(ground.min()),maximum_ground_delta=int(ground.max()),native_game_ui_verified=False,world_written=False,un_relocation_allowed=False,
        remaining='One downtown district only; wider coast/city, stations and the later ordered map phases remain incomplete.')
    (C/'odawara-release-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


def require_verified(candidate):
    spec_path=candidate/'plan/authored-design.json'
    if not spec_path.exists():return
    spec=json.loads(spec_path.read_text('utf8'))
    if spec.get('name')!='Odawara first downtown district':return
    report=json.loads((candidate/'odawara-release-check.json').read_text('utf8'))
    if Path(report['candidate']).resolve()!=candidate.resolve():raise ValueError('Odawara proof belongs to a different candidate')
    if not report['all_public_columns_reachable']or report['room_and_landing_goals']!=report['reachable_room_and_landing_goals']:raise ValueError('Incomplete Odawara access proof')
    for key in ('definite_floating_after','unknown_floating_components','water_public_and_parcel_conflicts','geographic_rail_corridor_conflicts'):
        if report[key]:raise ValueError(('Unresolved Odawara district conflict',key))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('candidate','before-components','after-components','geography'):p.add_argument('--'+name,type=Path,required=True)
    verify(p.parse_args())
