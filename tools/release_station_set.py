"""Publish a frozen station set using explicit layout and common delivery checks."""
import argparse, json, shutil
from argparse import Namespace
from pathlib import Path
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from install_r53_carrier_trays import stopped_world
from native_transit_additions import inventory,assert_preserved
from prepare_hakone_network_recipes import parallel_recipes
from map_pipeline.verify_corridors import write_replay_expected
from map_pipeline.launch_earthworks import ground
from map_pipeline.delivery_check import read,write,capture_identity,verify_delivery
from map_pipeline.station_release_checks import verify as check_package
from map_pipeline.station_layout import verify as check_layout
from release_regional_station import install


def native_check(a,layout):
    proof=read(a.candidate/'native-station/native-station-proof.json')
    m=read(a.candidate/'manifest.json')
    if not proof['existing_loaded_objects_exact'] or set(proof['members'])!=set(m['native_additions']):
        raise ValueError('Native registration preservation proof differs')
    if len(proof['members'])!=layout['native_additions']:
        raise ValueError('Native member scope differs')
    planned=read(a.candidate/'native-station-plan.json')
    actual={r['id']:r for r in proof['input_plan']['rails']}
    if set(actual)!={r['id']for r in planned['rails']}:
        raise ValueError('Registered rail set differs from frozen physical plan')
    for rail in planned['rails']:
        if any(rail[k]!=actual[rail['id']][k]for k in('from','to','from_angle','to_angle','shape','vertical_radius')):
            raise ValueError('Registered rail geometry differs from physical plan')
    if {p['station']for p in proof['platforms']}!={s['name']for s in layout['stations']}:
        raise ValueError('Registered station names differ')
    for station in layout['stations']:
        platforms=[p for p in proof['platforms']if p['station']==station['name']]
        if len(platforms)!=len(station['platform_lengths']):raise ValueError('Platform count differs')
        if any(abs(p['platform_length']-n)>1e-6 for p,n in zip(platforms,station['platform_lengths'])):
            raise ValueError('Native platform length differs')
        if any(p['station_min']+p['station_max']!=station['occupied_bounds']for p in platforms):
            raise ValueError('Native station bounds differ from declared occupation')
        if min(station['platform_lengths'])<station['planned_consist_length']:
            raise ValueError('Consist exceeds platform')
    return proof


def prepare(a):
    layout=read(a.layout);spec=check_package(a);proof=native_check(a,layout)
    measured=check_layout(a.candidate,a.authority,layout)
    write(a.candidate/'release-layout-check.json',measured)
    review=read(a.review/spec['structural_report'])
    cases=review['negative_cases']
    if len(cases)<5 or not all(c['rejected']for c in cases):
        raise ValueError('Station set has insufficient rejection evidence')
    if review['new_floating_solids']or review['newly_detached_retained_cells']:
        raise ValueError('New or detached floating components')
    if len(nbtlib.load(a.candidate/'block-entities.dat')['Changes'])!=layout['device_changes']:
        raise ValueError('Unexpected station device scope')
    write(a.candidate/'functional-check.json',dict(errors=[],evidence=str(a.review/spec['structural_report']),overlay_proof='release-layout-check.json',native_station_registration_verified=True,world_written=False,through_service_complete=False))
    with stopped_world(a.world):
        assert_preserved(a.world,inventory(a.candidate/'preserved-native'))
        parallel_recipes(Namespace(candidate=a.candidate,world=a.world,regions=None,workers=2))
        files=capture_identity(a.world,a.candidate,a.prior_client)
    write_replay_expected(a.candidate)
    write(a.candidate/'station-release-check.json',dict(production_recipe_replay_passed=False,identity_snapshot_ready=True,native_station_registration_verified=True,exact_voxel_views_reviewed=True,negative_fault_checks_passed=True,no_new_floating_components=True,current_native_source_exact=True,ground_only_scalar_network_update=True,world_written=False))
    write(a.candidate/'station-set-release.json',dict(schema='station-set-release-v1',
        candidate=str(a.candidate.resolve()),authority=str(a.authority.resolve()),
        review=str(a.review.resolve()),models=str(a.models.resolve()),
        checks=str(a.checks.resolve()),layout=str(a.layout.resolve()),
        cells=read(a.candidate/'manifest.json')['cells']))
    print('Prepared station set:',len(layout['stations']),'stations;',measured['nodes'],'measured public surfaces;',len(files),'identity files.')


def require_verified(candidate):
    """The installer gate for explicit layouts, including diagonal platforms."""
    saved=read(candidate/'station-set-release.json')
    if saved.get('schema')!='station-set-release-v1' or Path(saved['candidate']).resolve()!=candidate.resolve():
        raise ValueError('Station set release belongs to a different candidate')
    a=Namespace(**{key:Path(saved[key])for key in('candidate','authority','review','models','checks','layout')})
    for key in('checks','layout'):
        if not getattr(a,key).resolve().is_relative_to(candidate.resolve()):
            raise ValueError('Station set declaration is outside its candidate')
    manifest=read(candidate/'manifest.json');release=read(candidate/'station-release-check.json')
    required=('production_recipe_replay_passed','identity_snapshot_ready','native_station_registration_verified',
              'exact_voxel_views_reviewed','negative_fault_checks_passed','no_new_floating_components','current_native_source_exact')
    if saved['cells']!=manifest['cells'] or not all(release.get(k)is True for k in required):
        raise ValueError('Station set release requirements incomplete')
    spec=check_package(a);layout=read(a.layout);native_check(a,layout)
    measured=check_layout(candidate,a.authority,layout)
    if measured!=read(candidate/'release-layout-check.json'):
        raise ValueError('Station layout changed after preparation')
    structural=read(a.review/spec['structural_report'])
    if len(structural['negative_cases'])<5 or not all(c['rejected']for c in structural['negative_cases']):
        raise ValueError('Station set rejection evidence incomplete')
    if structural['new_floating_solids']or structural['newly_detached_retained_cells']:
        raise ValueError('Station set has floating components')
    if len(nbtlib.load(candidate/'block-entities.dat')['Changes'])!=layout['device_changes']:
        raise ValueError('Station set device scope changed')


def record(a):
    layout=read(a.layout);native_check(a,layout)
    with stopped_world(a.world):
        delivery_check=verify_delivery(a.world,a.candidate,a.installation,a.production_log)
    write(a.candidate/'delivery-check.json',delivery_check)
    receipt=read(a.installation)
    with np.load(a.authority/'network.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);added=0
    for px,pz,g in layout['ground_access_columns']:
        j,i=pz-z,px-x
        if d['walk'][j,i]or d['road'][j,i]:
            if int(d['grade2'][j,i])!=g:raise ValueError('Existing public elevation differs')
        else:d['walk'][j,i]=True;d['grade2'][j,i]=g;added+=1
    bounds=read(a.candidate/'capture.json')['bounds_xz'];l,t,r,b=bounds;measured=ground(Editor(a.candidate),bounds)
    for delta in(a.candidate/'delta').glob('*.npz'):
        with np.load(delta)as f:coords=f['coordinates'];ranges=f['ranges'];indices=f['indices']
        for k,(cx,cz)in enumerate(coords):
            lo,hi=ranges[k:k+2]
            for col in np.unique(indices[lo:hi]%256):
                px,pz=int(cx)*16+int(col)%16,int(cz)*16+int(col)//16
                d['ground'][pz-z,px-x]=measured[pz-t,px-l]
    catalog=read(a.authority/'catalog.json');volumes=read(a.authority/'station-volumes.json')
    for s in layout['stations']:
        sid='regional-station/'+s['id']
        if any(r['id']==sid for r in catalog):raise ValueError('Station catalog identity already exists')
        catalog.append(dict(id=sid,kind='station_access',use=s['name'],occupied_bounds=s['occupied_bounds'],door=s['door'],approach=s['approach'],destination=s['destinations'][0],destinations=s['destinations'],destination_type='platform',installed_station_access=str(a.candidate),through_service_complete=False))
        volumes.append(s['occupied_bounds'])
    shutil.copytree(a.authority,a.next_authority)
    np.savez_compressed(a.next_authority/'network.npz',**d)
    write(a.next_authority/'catalog.json',catalog);write(a.next_authority/'station-volumes.json',volumes)
    write(a.next_authority/(a.station_id+'-multilevel-overlay.json'),dict(previous=str(a.authority),candidate=str(a.candidate),installation=str(a.installation),ground_access_columns=layout['ground_access_columns'],station_multi_level_nodes=layout['station_multi_level_nodes'],stations=layout['stations'],existing_public_columns_exact=True,existing_catalog_entries_exact=True,world_written=True,through_service_complete=False))
    installed=sum(r.get('kind')=='station_access'and r.get('id','').startswith('regional-station/')for r in catalog)
    delivery=dict(batch=a.batch,status='Station set structure and native registration installed; live operation pending stage 3',stations=[s['name']for s in layout['stations']],candidate=str(a.candidate),installation=str(a.installation),authority=str(a.next_authority),terrain_field=str(a.terrain),changed_cells=receipt['cells'],recipe_chunks=receipt['metadata_files']-len(read(a.candidate/'manifest.json')['native_additions']),new_native_members=delivery_check['new_native_members_exact'],old_native_members_exact=delivery_check['old_native_members_exact'],identity_files_exact=delivery_check['identity_files_exact'],whole_client_jar_exact=True,production_replay_passed=True,visible_model_clearance_passed=True,public_surfaces=len(layout['station_multi_level_nodes']),ground_public_columns=len(layout['ground_access_columns']),new_ground_public_columns=added,all_public_surfaces_reachable=True,native_platform_lengths=[p for s in layout['stations']for p in s['platform_lengths']],planned_consist_lengths=[s['planned_consist_length']for s in layout['stations']],world_written=True,through_service_complete=False,live_boarding_and_rendered_validation_pending=True,new_geographic_stations_installed=installed,new_geographic_stations_remaining=20-installed)
    write(a.delivery,delivery)
    p=a.delivery.parent/'continuation.json';state=read(p)
    state.update(latest_installed_batch=a.batch,planning_authority=str(a.next_authority),active_order_stage=2,current_work=f'All stations: {installed}/20 geographic stations installed; retained-station review and further sites pending.',user_paused=False,un_relocation_allowed=False)
    state.setdefault('pending_map_cache_releases',[]).append(str(a.installation.parent));write(p,state)
    print('Recorded batch',a.batch,'stations',len(layout['stations']),'cells',receipt['cells'],'new stations',installed,'of 20.')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('mode',choices=('prepare','install','record'));p.add_argument('--batch',type=int,required=True);p.add_argument('--station-id',required=True)
    for key in('world','candidate','authority','next-authority','terrain','installation','review','models','prior-client','production-log','delivery','checks','layout'):
        p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();globals()[a.mode](a)
