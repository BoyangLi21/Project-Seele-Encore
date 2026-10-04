"""Current 38 interfaces, public gate starts and whole native diagram data.

Only query_blocks/MeasuredWorld reads actual save blocks. No apply entrypoint.
"""
from pathlib import Path
from collections import Counter
import argparse
import copy
import gzip
import hashlib
import json
import math

import nbtlib
from measure_world_r40 import MeasuredWorld,properties
from query_blocks import iter_block_entities
from audit_facility_transit_r44 import Geometry
from school_hakone_patch_r45 import canonical_state

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/rebuild_r45/transport_controls_agent'
WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'


def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,default=WORLD);ap.add_argument('--out',type=Path,default=ART/'current_audit_v1');a=ap.parse_args()
    assert ART.resolve() in a.out.resolve().parents and not a.out.exists();a.out.mkdir(parents=True)
    native=read(ART/'current_native_snapshot.json');platforms={str(p['id']):p for p in native['platforms']}
    source=ROOT/'artifacts/rebuild_r44/facility_transit_r44/native_transit_cases/cases.json'
    cases=read(source)['cases'];assert len(cases)==38 and {c['source_platform'] for c in cases}==set(platforms)
    quality=read(a.world/'quality_walk_cases.json');gates=read(a.world/'r44_public_station_gates.json')['gates'];by_gate={tuple(g['position']):g for g in gates}
    w=MeasuredWorld(a.world)
    for case in cases:
        for side in ['source','destination']:
            profile=case[side];w.around(profile['staging'],4)
            for point in profile.get('all_actual_door_approaches',[]):w.around(point,2)
            if profile.get('air_stairs'):
                for key in ['head','entry','landing']:w.around(profile['air_stairs'][key],7)
    for gate in gates:w.around(gate['position'],5)
    for p in [(-398,82,698),(-396,82,698),(135,-441,-54),(123,-441,-26)]:w.around(p,5)
    for c in quality:
        if 'map_approach' in c['id']:
            for q in c['path']:w.around(q,1)
    w.load();geom=Geometry(w)
    report_cases=[]
    for case in cases:
        platform=platforms[case['source_platform']];profile=case['source']
        item=dict(id=case['id'],platform_id=case['source_platform'],destination_platform_id=case['destination_platform'],station_id=profile['station_id'],mode=case['mode'],service=case['service'],route_id=case['route_id'],staging=profile['staging'],actual_staging=geom.standing(tuple(math.floor(v) for v in profile['staging'])),native_verification='UNVERIFIED_R45',snapshot_platform=platform,source_profile=profile,destination_profile=case['destination'])
        if case['mode']=='TRAIN':
            points=profile['all_actual_door_approaches'];item['all_approach_points']=len(points)
            item['approach_status']=dict(Counter(geom.standing(tuple(q))['status'] for q in points))
        report_cases.append(item)
    changes=[];after=copy.deepcopy(quality);index={c['id']:i for i,c in enumerate(after)}
    for c in quality:
        if 'map_approach' not in c['id']:continue
        first=c['path'][0];q=tuple(math.floor(v) for v in first)
        if q not in by_gate:continue
        gate=by_gate[q];face=properties(w.block(q))['facing'];dx,dz={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}[face]
        # Entrance facing follows paid-side travel; public start is outside.
        p=[first[0]-2*dx,first[1],first[2]-2*dz]
        start=tuple(math.floor(v) for v in p);check=geom.standing(start)
        assert check['status']=='STATIC_STANDING',('Actual public start has no standing support',c['id'],p,check)
        path=[p]+c['path'][1:]
        statuses=[]
        for first,last in zip(path,path[1:]):
            steps=max(1,math.ceil(math.dist(first,last)*2))
            for i in range(steps+1):
                point=tuple(math.floor(first[k]+(last[k]-first[k])*i/steps) for k in range(3));statuses.append(geom.standing(point)['status'])
        assert all(s=='STATIC_STANDING' for s in statuses),('Public-to-reader route needs complete repair',c['id'],Counter(statuses))
        change=dict(id=c['id'],before=copy.deepcopy(c),after=dict(c,path=path),gate=gate,public_start_proof=check,reason='Restore the first point to the actual public side of the intact closed native MTR fare barrier; keep original reader and all subsequent route members')
        changes.append(change);after[index[c['id']]]=change['after']
    # The moved ground NERV diagram keeps its exact current readable front.
    cid='r25/station_map/-2665385328076896034/1';c=after[index[cid]]
    assert c['readingBoard']==[-398,82,698]
    replacement=dict(c,readingBoard=[-396,82,698],path=[[-395.5,81,696.5],[-395.5,81,696.5]],expectedNativePlatformId='3659484649089170800')
    assert geom.standing((-396,81,696))['status']=='STATIC_STANDING'
    changes.append(dict(id=cid,before=copy.deepcopy(c),after=replacement,reason='Old declared diagram coordinate is air; bind the actual root-migrated S1 whole map and its current north reading side'))
    after[index[cid]]=replacement
    approach='r28/map_approach/'+cid
    if approach in index:
        c=after[index[approach]];path=copy.deepcopy(c['path']);assert path[-1]==[-397.5,81,696.5]
        path.extend([[-396.5,81,696.5],[-395.5,81,696.5]])
        replacement=dict(c,path=path);changes.append(dict(id=approach,before=copy.deepcopy(c),after=replacement,reason='Preserve the real source public approach and extend continuously to the relocated diagram centred reading point'));after[index[approach]]=replacement
    physical=[];be_observations=[]
    for point in [(135,-441,-54),(123,-441,-26)]:
        lower=(point[0],point[1]-1,point[2]);tags=dict(iter_block_entities(a.world,'projectseele:geofront',lower,point))
        assert str(tags[lower]['id'])=='mtr:route_sign_wall_light' and int(tags[lower]['platform_id'])==-4991105154196472855
        current=tags[point];assert str(current['id'])=='projectseele:station_departure_board'
        replacement=nbtlib.Compound({'id':nbtlib.String('mtr:route_sign_wall_light'),'x':nbtlib.Int(point[0]),'y':nbtlib.Int(point[1]),'z':nbtlib.Int(point[2]),'platform_id':nbtlib.Long(-4991105154196472855),'keepPacked':nbtlib.Byte(0)})
        physical.append(dict(pos=list(point),before=w.block(point),after=w.block(point),before_nbt=current.snbt(),after_nbt=replacement.snbt(),owner='r45/transport/native_route_sign_integrity',reason='Native MTR creates this BE for both halves; repair the incompatible upper ProjectSEELE BE while preserving complete original inverse and native lower platform ID'))
        be_observations.append(dict(upper=list(point),lower=list(lower),before_upper=current.snbt(),before_lower=tags[lower].snbt(),native_platform_id='-4991105154196472855',two_halves_preserved=True,properties=properties(w.block(point)),reading_side='Opposite native facing property, with actual legacy point preserved',native_render_verified=False))
        cid='r25/station_map/-4991105154196472855/'+('-1' if point[0]==135 else '1');c=after[index[cid]]
        replacement=dict(c,readingNativeMtrBoard=True,expectedNativePlatformId='-4991105154196472855',expectedChineseStations=['EVA 机库','整备补给中心','NERV 总部'])
        changes.append(dict(id=cid,before=copy.deepcopy(c),after=replacement,reason='Test the actual complete two-high native MTR diagram, platform binding, route topology, Chinese station sequence, front facing and outline ray; do not cast it as a ProjectSEELE-only board'));after[index[cid]]=replacement
    repair=a.out/'native_sign_BE_integrity';repair.mkdir()
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(repair/(name+'.jsonl.gz'),'wt',encoding='utf8') as f:
            for row in physical:
                r=dict(row)
                if inverse:r['before'],r['after'],r['before_nbt'],r['after_nbt']=row['after'],row['before'],row['after_nbt'],row['before_nbt']
                f.write(json.dumps(r,ensure_ascii=False)+'\n')
    (a.out/'quality_walk_cases.before.json').write_bytes((a.world/'quality_walk_cases.json').read_bytes())
    (a.out/'quality_walk_cases.after.json').write_text(json.dumps(after,ensure_ascii=False,indent=2)+'\n','utf8')
    (a.out/'exact_derived_plan.json').write_text(json.dumps(dict(forward=[dict(target=str((a.world/'quality_walk_cases.json').resolve()),expected_sha256=sha(a.out/'quality_walk_cases.before.json'),bytes_from=str((a.out/'quality_walk_cases.after.json').resolve()),after_sha256=sha(a.out/'quality_walk_cases.after.json'))],inverse=[dict(target=str((a.world/'quality_walk_cases.json').resolve()),expected_sha256=sha(a.out/'quality_walk_cases.after.json'),bytes_from=str((a.out/'quality_walk_cases.before.json').resolve()))],changed_cases=changes,world_written=False,unrelated_record_order_and_data_preserved=True),ensure_ascii=False,indent=2),'utf8')
    report=dict(world=str(a.world.resolve()),actual_current_snapshot=str((ART/'current_native_snapshot.json').resolve()),snapshot_sha256=sha(ART/'current_native_snapshot.json'),full_interfaces=38,train_interfaces=34,air_interfaces=4,public_gate_count=len(gates),remaining_closed_gate_starts_repaired=sum('gate' in c for c in changes),diagram_repairs=be_observations,interface_objects=report_cases,unknown_shapes=sorted(geom.unknown),native_passed=False,visual_passed=False,world_written=False)
    (a.out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Actual interfaces38/train34/air4; native gates',len(gates),'closed public starts fixed',sum('gate' in c for c in changes),'diagram upper full-NBT fixes',len(physical),'derived changed',len(changes),flush=True)


if __name__=='__main__':main()
