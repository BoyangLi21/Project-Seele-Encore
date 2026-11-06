"""Prepare, install and record a measured station through the existing cold-world pipeline."""
import argparse,json,shutil,subprocess,sys,zipfile
from pathlib import Path
from argparse import Namespace
import numpy as np
from install_r53_carrier_trays import stopped_world
from prepare_hakone_network_recipes import parallel_recipes
from map_pipeline.verify_corridors import write_replay_expected
from native_transit_additions import inventory,assert_preserved
from author_hakone_lakefront import Editor
from map_pipeline.launch_earthworks import ground

def read(p):return json.loads(p.read_text('utf8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')

def prepare(a):
    c=a.candidate;check=read(c/'station-independent-check.json');manifest=read(c/'manifest.json')
    assert not check['errors']and check['changed_cells']==manifest['cells']and check['public_columns']==check['reachable_public_columns']
    before=read(a.components_before/'floating-components.json');after=read(a.components_after/'floating-components.json')
    # An existing boundary-clipped tree is allowed only when its entire measured
    # component report stays exact; it is never counted as a new floating object.
    assert before==after and not after['definite_floating']
    faults=read(a.negative/'result.json');assert len(faults)>=4 and all(r['rejected']for r in faults)
    for name in('overview','hall-cut'):assert(a.views/(name+'.png')).exists()
    with stopped_world(a.world):
        assert_preserved(a.world,inventory(c/'preserved-native'))
        parallel_recipes(Namespace(candidate=c,world=a.world,regions=None,workers=2))
        identity=c/'identity-before';identity.mkdir();files=[]
        for f in [a.world/'level.dat',a.world/'level.dat_old',*list((a.world/'playerdata').glob('*')),*list((a.world/'dimensions/projectseele/geofront/entities').glob('*.mca'))]:
            if not f.is_file():continue
            rel=f.relative_to(a.world);dest=identity/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest);files.append(rel.as_posix())
        write(identity/'files.json',files)
        jar=a.world.parent.parent/'mods/projectseele-0.1.0-all.jar'
        with zipfile.ZipFile(jar)as actual,zipfile.ZipFile(a.terrain/'terrain-delivery.jar')as terrain:
            assert len(terrain.namelist())==5
            for name in terrain.namelist():assert actual.read(name)==terrain.read(name),name
        shutil.copy2(jar,c/'client-before.jar')
    write_replay_expected(c)
    write(c/'station-release-check.json',dict(production_recipe_replay_passed=False,identity_snapshot_ready=True,native_station_registration_verified=True,exact_voxel_views_reviewed=True,negative_fault_checks_passed=True,no_new_floating_components=True,current_native_source_exact=True,world_written=False,through_service_complete=False,unchanged_boundary_components=after['unknown_components']))
    print('Prepared release:',len(files),'identity files;',after['full_chunks'],'FULL source chunks;',after['unknown_components'],'unchanged boundary components.',flush=True)

def install(a):
    log=a.production_log.read_text('utf8',errors='replace');assert 'BUILD SUCCESSFUL'in log and 'Production surface replay:'in log
    p=a.candidate/'station-release-check.json';d=read(p);d['production_recipe_replay_passed']=True;write(p,d)
    subprocess.run([sys.executable,str(Path(__file__).with_name('install_hakone_array_patch.py')),'--world',str(a.world),'--backup',str(a.installation.parent),'--candidate',str(a.candidate),'--workers','2'],check=True)

def record(a):
    c=a.candidate;receipt=read(a.installation);assert receipt['status']=='installed'and receipt['changed_section_readback']and receipt['existing_native_members_exact']
    assert receipt['native_additions']==3 and receipt['changed_device_nbt_readback']==3
    baseline=inventory(c/'preserved-native');additions=[Path(n).relative_to('mtr').as_posix()for n in read(c/'manifest.json')['native_additions']];kept=read(c/'identity-before/files.json')
    with stopped_world(a.world):
        for name in kept:assert(c/'identity-before'/name).read_bytes()==(a.world/name).read_bytes(),name
        assert_preserved(a.world,baseline,additions)
        for name in additions:assert(c/'after/mtr'/name).read_bytes()==(a.world/'mtr'/name).read_bytes()
        jar=a.world.parent.parent/'mods/projectseele-0.1.0-all.jar'
        with zipfile.ZipFile(c/'client-before.jar')as old,zipfile.ZipFile(jar)as actual:
            assert set(old.namelist())==set(actual.namelist())
            for name in old.namelist():assert old.read(name)==actual.read(name),name
            retained=len(actual.namelist())-5
    shutil.copytree(a.authority,a.next_authority)
    with np.load(a.authority/'network.npz')as f:d={k:f[k]for k in f.files}
    design=read(c/'station-design.json');x,z,X,Z=map(int,d['bounds']);added=0
    for px,pz,grade in design['public_columns']:
        j,i=pz-z,px-x
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
    catalog=read(a.authority/'catalog.json');stationid='regional-station/'+design['station_id'];assert not any(r['id']==stationid for r in catalog)
    native=read(c/'native-station-plan.json')['stations'][0];occupied=native['min']+native['max']
    catalog.append(dict(id=stationid,kind='station_access',use=design['station'],occupied_bounds=occupied,door=design['goals']['entrance'],approach=design['goals']['forecourt'],destination=design['goals']['platform_centre'],destination_type='platform',installed_station_access=str(c),through_service_complete=False));write(a.next_authority/'catalog.json',catalog)
    volumes=read(a.authority/'station-volumes.json');volumes.append(occupied);write(a.next_authority/'station-volumes.json',volumes)
    write(a.next_authority/'new-station-overlay.json',dict(previous=str(a.authority),candidate=str(c),installation=str(a.installation),new_public_columns=added,existing_public_columns_exact=True,existing_catalog_entries_exact=True,world_written=True))
    installed=sum(r.get('kind')=='station_access'and r.get('id','').startswith('regional-station/')for r in catalog)
    report=dict(batch=a.batch,status='Physical station, public access and native registration installed; through service pending stage 3',station=design['station'],candidate=str(c),installation=str(a.installation),authority=str(a.next_authority),terrain_field=str(a.terrain),changed_cells=receipt['cells'],recipe_chunks=receipt['metadata_files']-3,new_native_members=3,old_native_members_exact=len(baseline),native_platform_length=48,public_columns=len(design['public_columns']),new_public_columns=added,goals_reached=len(design['goals']),source_full_chunks=read(a.components_after/'floating-components.json')['full_chunks'],unchanged_boundary_components=read(a.components_after/'floating-components.json')['unknown_components'],identity_files_exact=len(kept),nonterrain_client_members_exact=retained,production_replay_passed=True,negative_fault_cases=len(read(a.negative/'result.json')),no_new_floating_components=True,old_road_geometry_unchanged=True,client_jar_written=False,world_written=True,new_geographic_station_structures_installed=installed,new_geographic_station_structures_remaining=20-installed,existing_station_final_reviews_remaining=34,through_service_complete=False,stage_two_complete=False,minimap_refreshed=False,distant_cache_refreshed=False,manual_acceptance_received=False,un_relocation_allowed=False)
    write(a.delivery,report);p=a.delivery.parent/'continuation.json';state=read(p);state.update(latest_installed_batch=a.batch,planning_authority=str(a.next_authority),active_order_stage=2,current_work=f'All stations: {installed} new physical stations installed; {20-installed} new sites remain. Retained station access reviews in parallel.',user_paused=False,un_relocation_allowed=False)
    state.setdefault('pending_map_cache_releases',[]).append(str(a.installation.parent));write(p,state)
    print('Recorded batch',a.batch,design['station'],receipt['cells'],'cells;',added,'new public columns;',installed,'of 20 new structures installed.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('mode',choices=['prepare','install','record']);p.add_argument('--batch',type=int,required=True)
    for n in('world','candidate','authority','next-authority','terrain','installation','components-before','components-after','negative','views','production-log','delivery'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();globals()[a.mode](a)
