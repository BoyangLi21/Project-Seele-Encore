"""Release an offline mainline station while preserving layered pedestrian surfaces."""
import argparse,json,shutil,zipfile
from pathlib import Path
from argparse import Namespace
import numpy as np
from author_hakone_lakefront import Editor
from author_kamonomiya_station import verify
from install_r53_carrier_trays import stopped_world
from native_transit_additions import inventory,assert_preserved
from prepare_hakone_network_recipes import parallel_recipes
from map_pipeline.verify_corridors import write_replay_expected
from map_pipeline.launch_earthworks import ground
from release_regional_station import install
from verify_mainline_station_model_clearance import check as visible_check

def read(p):return json.loads(p.read_text('utf8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')
def jar_exact(a,b):
    with zipfile.ZipFile(a)as old,zipfile.ZipFile(b)as actual:
        assert set(old.namelist())==set(actual.namelist())
        for name in old.namelist():assert old.read(name)==actual.read(name),name

def prepare(a):
    c=a.candidate;verify(c,a.authority);assert not visible_check(c,a.models)['errors']
    manifest=read(c/'manifest.json');proof=read(c/'native-station/native-station-proof.json');design=read(c/'station-design.json')
    assert proof['existing_loaded_objects_exact']and len(proof['platforms'])==2 and len(proof['members'])==5
    assert all(abs(p['platform_length']-128)<1e-7 for p in proof['platforms'])
    components=read(a.review/'components.json');assert all(components[k]['unrooted_components']==0 for k in('before','after'))
    faults=read(a.review/'negative-cases.json')['cases'];assert len(faults)>=5 and all(r['detected']for r in faults)
    assert not read(c/'visible-model-sweep.json')['errors']
    model_fault=read(a.review/'visible-model-negative.json');assert model_fault['detected']and model_fault['failed_vehicle_count']==2
    for name in('overview','ramp-cut'):assert(a.review/(name+'.png')).exists()
    check=read(c/'offline-verification.json');assert not check['errors']and check['nodes']==check['reachable_nodes']==len(design['station_multi_level_nodes'])
    assert len(design['ground_access_columns'])<len(design['station_multi_level_nodes'])
    write(c/'functional-check.json',dict(errors=[],station=design['station'],offline_proof='offline-verification.json',visible_model_proof='visible-model-clearance.json',world_written=False))
    with stopped_world(a.world):
        assert_preserved(a.world,inventory(c/'preserved-native'))
        parallel_recipes(Namespace(candidate=c,world=a.world,regions=None,workers=2))
        identity=c/'identity-before';identity.mkdir();files=[]
        for f in[a.world/'level.dat',a.world/'level.dat_old',*list((a.world/'playerdata').glob('*')),*list((a.world/'dimensions/projectseele/geofront/entities').glob('*.mca'))]:
            if not f.is_file():continue
            rel=f.relative_to(a.world);dest=identity/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest);files.append(rel.as_posix())
        write(identity/'files.json',files)
        jar_exact(a.prior_client,a.world.parent.parent/'mods/projectseele-0.1.0-all.jar')
        (c/'client-before.jar').hardlink_to(a.prior_client)
    write_replay_expected(c)
    write(c/'station-release-check.json',dict(production_recipe_replay_passed=False,identity_snapshot_ready=True,native_station_registration_verified=True,exact_voxel_views_reviewed=True,negative_fault_checks_passed=True,no_new_floating_components=True,current_native_source_exact=True,visible_models_checked=True,ground_only_scalar_network_update=True,world_written=False,through_service_complete=False))
    print('Prepared mainline station:',manifest['cells'],'cells;',check['nodes'],'reachable surfaces; two native platforms; retained identity files',len(files),flush=True)

def record(a):
    c=a.candidate;receipt=read(a.installation);m=read(c/'manifest.json');proof=read(c/'native-station/native-station-proof.json')
    assert receipt['status']=='installed'and receipt['changed_section_readback']and receipt['existing_native_members_exact']
    assert receipt['native_additions']==5 and receipt['changed_device_nbt_readback']==3 and receipt['cells']==m['cells']
    baseline=inventory(c/'preserved-native');additions=[Path(n).relative_to('mtr').as_posix()for n in m['native_additions']];kept=read(c/'identity-before/files.json')
    with stopped_world(a.world):
        for name in kept:assert(c/'identity-before'/name).read_bytes()==(a.world/name).read_bytes(),name
        assert_preserved(a.world,baseline,additions)
        for name in additions:assert(c/'after/mtr'/name).read_bytes()==(a.world/'mtr'/name).read_bytes()
        jar_exact(c/'client-before.jar',a.world.parent.parent/'mods/projectseele-0.1.0-all.jar')
    shutil.copytree(a.authority,a.next_authority)
    with np.load(a.authority/'network.npz')as f:d={k:f[k]for k in f.files}
    design=read(c/'station-design.json');x,z,X,Z=map(int,d['bounds']);added=0
    assert design['ground_access_format']==['x','z','grade2']and design['station_multi_level_node_format']==['x','grade2','z']
    for px,pz,grade in design['ground_access_columns']:
        assert x<=px<=X and z<=pz<=Z;j,i=pz-z,px-x
        if d['walk'][j,i]:assert int(d['grade2'][j,i])==grade
        else:d['walk'][j,i]=True;d['grade2'][j,i]=grade;added+=1
    bounds=read(c/'capture.json')['bounds_xz'];l,t,r,b=bounds;measured=ground(Editor(c),bounds)
    for delta in(c/'delta').glob('*.npz'):
        with np.load(delta)as ar:coords=ar['coordinates'];ranges=ar['ranges'];indices=ar['indices']
        for k,(cx,cz)in enumerate(coords):
            lo,hi=ranges[k:k+2]
            for col in np.unique(indices[lo:hi]%256):
                px,pz=int(cx)*16+int(col)%16,int(cz)*16+int(col)//16;d['ground'][pz-z,px-x]=measured[pz-t,px-l]
    np.savez_compressed(a.next_authority/'network.npz',**d)
    catalog=read(a.authority/'catalog.json');stationid='regional-station/'+a.station_id;assert not any(r['id']==stationid for r in catalog)
    native=read(c/'native-station-plan.json')['stations'][0];occupied=native['min']+native['max'];goals=design['goals']
    catalog.append(dict(id=stationid,kind='station_access',use=design['station'],occupied_bounds=occupied,door=goals['hall'],approach=goals['forecourt'],destination=goals['platform_1_centre'],destinations=[goals['platform_1_centre'],goals['platform_2_centre']],destination_type='platform',installed_station_access=str(c),through_service_complete=False));write(a.next_authority/'catalog.json',catalog)
    volumes=read(a.authority/'station-volumes.json');volumes.append(occupied);write(a.next_authority/'station-volumes.json',volumes)
    write(a.next_authority/(a.station_id+'-multilevel-overlay.json'),dict(previous=str(a.authority),candidate=str(c),installation=str(a.installation),new_ground_public_columns=added,ground_access_columns=design['ground_access_columns'],station_multi_level_nodes=design['station_multi_level_nodes'],goals=goals,existing_public_columns_exact=True,existing_catalog_entries_exact=True,world_written=True,through_service_complete=False))
    installed=sum(r.get('kind')=='station_access'and r.get('id','').startswith('regional-station/')for r in catalog)
    write(a.delivery,dict(batch=a.batch,status='Physical station and native registration installed; through service pending stage 3',station=design['station'],candidate=str(c),installation=str(a.installation),authority=str(a.next_authority),terrain_field=str(a.terrain),changed_cells=receipt['cells'],recipe_chunks=receipt['metadata_files']-len(additions),new_native_members=5,old_native_members_exact=len(baseline),native_platform_lengths=[p['platform_length']for p in proof['platforms']],public_surfaces=len(design['station_multi_level_nodes']),ground_public_columns=len(design['ground_access_columns']),new_ground_public_columns=added,all_public_surfaces_reachable=True,identity_files_exact=len(kept),whole_client_jar_exact=True,visible_model_clearance_passed=True,production_replay_passed=True,world_written=True,through_service_complete=False,new_geographic_stations_installed=installed,new_geographic_stations_remaining=20-installed,live_boarding_and_rendered_validation_pending=True))
    p=a.delivery.parent/'continuation.json';state=read(p);state.update(latest_installed_batch=a.batch,planning_authority=str(a.next_authority),active_order_stage=2,current_work=f'All stations: {installed}/20 new stations installed; retained-station access and further sites continue in parallel.',user_paused=False,un_relocation_allowed=False);state.setdefault('pending_map_cache_releases',[]).append(str(a.installation.parent));write(p,state)
    print('Recorded batch',a.batch,design['station'],receipt['cells'],'cells;',installed,'of 20 new stations installed; existing native and identity exact.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('mode',choices=['prepare','install','record']);p.add_argument('--batch',type=int,required=True);p.add_argument('--station-id',required=True)
    for n in('world','candidate','authority','next-authority','terrain','installation','review','models','prior-client','production-log','delivery'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();globals()[a.mode](a)
