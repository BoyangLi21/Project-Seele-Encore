"""Cold publication of a finite station road, with exact frozen source and QC.

No station or service is counted complete by this road-only delivery. New roads
must join an installed public surface and preserve all existing public grades.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import nbtlib
import numpy as np

from author_hakone_lakefront import Editor
from install_r53_carrier_trays import stopped_world
from map_pipeline.corridors import publish_plan
from map_pipeline.delivery_check import read, write, capture_identity, verify_delivery
from map_pipeline.delta_geometry import checked_indices
from map_pipeline.verify_corridors import main as verify_corridor, write_replay_expected
from native_transit_additions import inventory, assert_preserved
from prepare_hakone_network_recipes import parallel_recipes
from release_access_patch import require, metadata_scope, package_file

CONTROL='corridor-release-check.json'
FREEZE='corridor-release-freeze'
REQUIRED=('source_devices_preserved','source_actors_preserved','vehicle_sweep_passed',
          'full_width_walk_passed','future_water_clearance_passed','supports_grounded')


def validate_offline(a):
    c=a.candidate;spec=read(a.config);m=read(c/'manifest.json')
    require(spec.get('schema')=='station-access-corridor-release-v1','Unknown corridor release scope')
    require(re.fullmatch(r'[a-z0-9][a-z0-9_-]*',spec['id'])is not None,'Invalid corridor identity')
    require(m.get('schema')=='bounded-station-access-corridor-v1','Candidate is not a bounded station road')
    require(Path(m['world']).resolve()==a.world.resolve(),'Wrong candidate world')
    for key in ('native_additions','native_changes','actor_changes','entity_moves','native_geometry_migrations','json_metadata'):
        require(not m.get(key),'Road release cannot change '+key)
    require(m.get('vertical_extent')==[-128,319],'Unexpected surface delta vertical extent')
    cap=read(c/'capture.json')
    require(not cap['unavailable_chunks'] and set(cap['chunk_statuses'])=={'full'},'Road source contains unknown chunks')
    require(len(nbtlib.load(c/'block-entities.dat')['Changes'])==m['device_changes']==0,'Road cannot change device payloads')
    source=Path(m['source'])
    require(nbtlib.load(c/'captured-devices.dat')==nbtlib.load(source/'captured-devices.dat'),'Device snapshot differs')
    e=Editor(c);changes=read(c/'exact-edits.json');bypos={tuple(q['pos']):q for q in changes}
    require(len(bypos)==len(changes)==m['cells']>0,'Repeated or inconsistent exact edits')
    observed={}
    for path in sorted((c/'delta').glob('*.npz')):
        with np.load(path)as f:
            y0,height,at=checked_indices(f)
            require((y0,height)==(-128,448),'Unexpected delta height')
            for i,(cx,cz)in enumerate(f['coordinates']):
                lo,hi=map(int,f['ranges'][i:i+2])
                for ix in range(lo,hi):
                    v=int(at[ix]);p=(int(cx)*16+v%16,y0+v//256,int(cz)*16+(v//16)%16)
                    require(p not in observed,'Duplicate delta cell')
                    observed[p]=(str(f['palette'][f['before'][ix]]),str(f['palette'][f['after'][ix]]))
    require(observed=={p:(q['before'],q['after'])for p,q in bypos.items()},'Exact edit list differs from arrays')
    devices={tuple(int(q[k])for k in ('x','y','z'))for q in nbtlib.load(c/'captured-devices.dat')['Devices']}
    require(not devices.intersection(observed),'Road edits an original device cell')
    for p,(before,after)in observed.items():
        require(before!=after and e.state(*p,True)==before and e.state(*p)==after,'Source or candidate state differs')
    for name,reverse in [('forward-patch.json',False),('inverse-patch.json',True)]:
        patch=read(c/name);require(patch.get('requires_exact_before')is True,'Patch lacks exact precondition')
        values={tuple(q['pos']):(q['before'],q['after'])for q in patch['edits']}
        wanted={p:pair[::-1]if reverse else pair for p,pair in observed.items()}
        require(len(values)==len(patch['edits']) and values==wanted,'Reversible patch differs')
    require({'functional-check.json','independent-check.json','access-independent-check.json'}.issubset(spec['error_reports']),'Required road reports omitted')
    for name in spec['error_reports']:
        require(read(package_file(c,name)).get('errors')==[],'Failed or missing report: '+name)
    expected={p.stem for p in(c/'earthworks').glob('*.npz')}
    declared={p['id']:p['walk_columns']for p in m.get('streets',[])if p['status']=='prepared'}
    verified={p['id']:p['full_width_columns']for p in read(c/'independent-check.json')['streets']}
    require(set(declared)==expected and declared==verified,'Shared corridor verification scope differs')
    report=read(c/'access-independent-check.json')
    require(all(report.get(k)is True for k in REQUIRED),'Independent 3D road evidence incomplete')
    negatives=report.get('negative_cases',[])
    require(len(negatives)>=5 and all(q.get('rejected')is True for q in negatives),'Fault rejection incomplete')
    for name in spec['reviewed_views']:package_file(c,name)
    require(spec.get('views_reviewed_by_root')is True,'Root exact voxel view review pending')
    validate_plan(c,a.authority)
    metadata_scope(c)
    return spec,m,report


def validate_plan(candidate,authority):
    """No silent retirement, grade change, or out-of-scope metadata updates."""
    with np.load(authority/'network.npz')as f:old={k:f[k]for k in f.files}
    with np.load(candidate/'plan/network.npz')as f:new={k:f[k]for k in f.files}
    require(set(old)==set(new)and np.array_equal(old['bounds'],new['bounds']),'Authority extent or fields differ')
    ax,az,_,_=map(int,old['bounds']);active=np.zeros(old['walk'].shape,bool);public=active.copy()
    for path in (candidate/'earthworks').glob('*.npz'):
        with np.load(path)as f:
            x,z,X,Z=map(int,f['bounds']);area=np.s_[z-az:Z-az+1,x-ax:X-ax+1]
            require(active[area].shape==f['active'].shape,'Corridor lies outside authority')
            active[area]|=f['active'];public[area]|=f['walk']
            require(not f.get('retired_walk',np.zeros(f['walk'].shape,bool)).any(),'Station road may not retire existing routes')
    retained=old['walk']|old['road']
    require(np.any(retained&public),'Road never reaches an installed public surface')
    for key in ('walk','road','grade2','tunnel'):
        require(np.array_equal(old[key][retained],new[key][retained]),'Existing public route changed: '+key)
    for key in old:
        if old[key].shape!=active.shape:
            require(np.array_equal(old[key],new[key]),'Non-spatial authority field differs: '+key)
        else:
            allowed=active if key=='ground'else public if key in ('walk','road','grade2','tunnel','marking')else np.zeros(active.shape,bool)
            require(np.array_equal(old[key][~allowed],new[key][~allowed]),'Authority changed outside finite mask: '+key)
    require(np.all(new['walk'][public]),'Declared road contains omitted public columns')
    for name in ('catalog.json','station-volumes.json'):
        require((candidate/'plan'/name).read_bytes()==(authority/name).read_bytes(),'Existing catalogue differs')
    return dict(public_columns=int(public.sum()),active_columns=int(active.sum()))


def current_state(a,spec):
    s=read(a.continuation)
    require(s['latest_installed_batch']==spec['previous_batch']==a.batch-1,'Stale release batch')
    require(Path(s['planning_authority']).resolve()==a.authority.resolve()==Path(spec['source_authority']).resolve(),'Stale authority')
    require(not a.next_authority.exists()and not a.delivery.exists(),'Published output already exists')
    require(a.authority.resolve()!=a.next_authority.resolve(),'Next authority must be distinct')
    return s


def replay_scope(a):
    return dict(candidate=str(a.candidate.resolve()),world=str(a.world.resolve()),batch=a.batch,
                expected=str((a.candidate/'recipe-replay-expected').resolve()))


def freeze(a,save=False):
    sources={'config':a.config};dest=a.candidate/FREEZE
    for name in ('release_station_access_corridor.py','map_pipeline/verify_corridors.py',
                 'map_pipeline/corridors.py','map_pipeline/delta_geometry.py','map_pipeline/delivery_check.py',
                 'plan_station_access_corridor.py','author_hakone_lakefront.py'):
        sources['tools/'+name]=Path(__file__).parent/name
    for prefix,root in [('candidate',a.candidate),('authority',a.authority)]:
        for path in root.rglob('*'):
            if not path.is_file():continue
            rel=path.relative_to(root)
            if prefix=='candidate'and(rel.parts[0]==FREEZE or rel.as_posix()in (CONTROL,'delivery-check.json')):continue
            sources[prefix+'/'+rel.as_posix()]=path
    entries={name:f'{i:06d}.bin'for i,name in enumerate(sorted(sources))}
    if save:
        dest.mkdir(exist_ok=False)
        for name,path in sources.items():shutil.copy2(path,dest/entries[name])
        write(dest/'inventory.json',entries)
    else:
        require(read(dest/'inventory.json')==entries,'Frozen file set changed')
        for name,path in sources.items():require(path.read_bytes()==(dest/entries[name]).read_bytes(),'Frozen evidence changed: '+name)
    return len(entries)


def prepare(a):
    spec=read(a.config);current_state(a,spec)
    publish_plan(a.candidate,a.authority)
    verify_corridor(argparse.Namespace(candidate=a.candidate,plan=a.authority))
    spec,m,report=validate_offline(a)
    baseline=inventory(Path(spec['native_snapshot']))
    require(not Path(spec['native_snapshot']).resolve().is_relative_to(a.world.resolve()),'Use an offline native snapshot')
    require(len(baseline)==spec['expected_native_members'],'Native snapshot count differs')
    require(not(a.candidate/'preserved-native').exists(),'Candidate already prepared')
    with stopped_world(a.world):
        assert_preserved(a.world,baseline)
        shutil.copytree(Path(spec['native_snapshot']),a.candidate/'preserved-native')
        m['preserve_native_members']=True;write(a.candidate/'manifest.json',m)
        parallel_recipes(argparse.Namespace(candidate=a.candidate,world=a.world,regions=None,workers=2))
        identity=capture_identity(a.world,a.candidate,a.prior_client)
    write_replay_expected(a.candidate);validate_offline(a)
    count=freeze(a,True)
    write(a.candidate/CONTROL,dict(schema='station-access-road-prepared-v1',prepared_time_ns=time.time_ns(),
        replay_scope=replay_scope(a),identity_files=len(identity),native_members=len(baseline),
        frozen_files=count,exact_voxel_views_reviewed=True,world_written=False))
    print('Prepared bounded station road:',m['cells'],'cells;',count,'frozen files.')


def require_prepared(a):
    spec,m,report=validate_offline(a);current_state(a,spec);freeze(a)
    p=read(a.candidate/CONTROL)
    require(p.get('schema')=='station-access-road-prepared-v1'and p['replay_scope']==replay_scope(a),'Wrong preparation')
    require(a.production_log.stat().st_mtime_ns>=p['prepared_time_ns'],'Replay predates preparation')
    log=a.production_log.read_text('utf-8-sig');marker='CORRIDOR_PATCH_REPLAY_SCOPE '
    scopes=[json.loads(line[len(marker):])for line in log.splitlines()if line.startswith(marker)]
    require(scopes==[replay_scope(a)],'Production replay scope differs')
    matches=re.findall(r'Production surface replay: (\d+) chunks, ([\d,]+) changed cells',log)
    require('BUILD SUCCESSFUL'in log and len(matches)==1,'Production replay failed or ambiguous')
    chunks,cells=[int(v.replace(',',''))for v in matches[0]]
    require((chunks,cells)==(len(metadata_scope(a.candidate)),m['cells']),'Replay count differs')
    return spec,m,report


def install(a):
    require_prepared(a)
    subprocess.run([sys.executable,str(Path(__file__).with_name('install_hakone_array_patch.py')),
        '--world',str(a.world),'--candidate',str(a.candidate),'--backup',str(a.installation.parent),'--workers','2'],check=True)


def record(a):
    spec,m,report=require_prepared(a);before=a.continuation.read_bytes();state=current_state(a,spec)
    prior_worklist=Path(state['station_construction_worklist']);work=read(prior_worklist)
    require(work['latest_installed_batch']==a.batch-1 and Path(work['planning_authority']).resolve()==a.authority.resolve(),'Station worklist is stale')
    workdir=a.delivery.parent/f'all-stations-construction-worklist-batch{a.batch}-road-v1'
    require(not workdir.exists(),'Road worklist already exists')
    require(a.candidate.resolve()in[Path(q).resolve()for q in read(a.installation)['candidates']],'Receipt candidate differs')
    with stopped_world(a.world):check=verify_delivery(a.world,a.candidate,a.installation,a.production_log)
    require(check['new_native_members_exact']==0 and check['old_native_members_exact']==spec['expected_native_members'],'Transport scope differs')
    write(a.candidate/'delivery-check.json',check)
    require(a.continuation.read_bytes()==before,'Continuation changed during verification')
    shutil.copytree(a.authority,a.next_authority)
    shutil.copy2(a.candidate/'plan/network.npz',a.next_authority/'network.npz')
    metrics=validate_plan(a.candidate,a.authority)
    write(a.next_authority/(spec['id']+'-installed-access.json'),dict(candidate=str(a.candidate),
        installation=str(a.installation),previous=str(a.authority),**metrics,world_written=True))
    delivery=dict(batch=a.batch,station=spec['label'],candidate=str(a.candidate),installation=str(a.installation),
        authority=str(a.next_authority),terrain_field=str(a.terrain),**check,**metrics,
        new_native_members=0,world_written=True,client_jar_written=False,station_structure_count_unchanged=True,
        station_complete=False,through_service_complete=False,minimap_refreshed=False,distant_cache_refreshed=False)
    write(a.delivery,delivery)
    work.update(latest_installed_batch=a.batch,planning_authority=str(a.next_authority),previous_worklist=str(prior_worklist))
    work.setdefault('station_access_corridor_deliveries',[]).append(str(a.delivery))
    workdir.mkdir();write(workdir/'worklist.json',work)
    state['station_construction_worklist']=str(workdir/'worklist.json')
    if 'station_worklist'in state:state['station_worklist']=state['station_construction_worklist']
    state.update(latest_installed_batch=a.batch,planning_authority=str(a.next_authority),current_work=spec['continuation_work'])
    state.setdefault('pending_map_cache_releases',[]).append(str(a.installation.parent))
    temporary=a.continuation.with_name('.corridor-continuation.json');write(temporary,state)
    require(a.continuation.read_bytes()==before,'Continuation changed before record')
    os.replace(temporary,a.continuation)
    print('Installed and recorded station road:',a.batch,check['changed_cells'],'cells; station completion unchanged.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('mode',choices=('prepare','install','record'))
    parser.add_argument('--batch',type=int,required=True)
    for key in ('config','candidate','world','authority','next-authority','installation','production-log',
                'delivery','continuation','terrain','prior-client'):parser.add_argument('--'+key,type=Path,required=True)
    a=parser.parse_args();globals()[a.mode](a)
