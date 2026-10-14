"""Read both delivered actual Worlds, selected Jar/runtime and every World byte.

This runs only after packaging. It never extracts/imports progress, rewrites
acceptance, starts Minecraft, publishes or claims unperformed gameplay checks.
"""
from pathlib import Path
import argparse,hashlib,json,zipfile
from package_release_r52 import selection,world_files,sha,safe,need


def stream_sha(archive,name):
    with archive.open(name) as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def category(name):
    parts=Path(name).parts
    if 'entities' in parts:return 'entity_progress'
    if parts[0] in ('playerdata','stats','advancements') or name in ('level.dat','level.dat_old'):
        return 'player_and_world_progress'
    if any('mtr' in part.lower() for part in parts):return 'transport_progress'
    if 'region' in parts and name.endswith('.mca'):return 'static_regions'
    if 'data' in parts and name.endswith('.dat'):return 'task_and_saved_state'
    if name in ('nerv_routes_r24.json.gz','nearest_lift_paths_r44.json.gz','r53_personnel_walking_graph.json.gz') or name.startswith('r52/travel'):
        return 'derived_navigation_and_travel'
    return 'declarations_and_other_preserved_files'


def verify_world_members(archive,prefix,expected):
    names=archive.namelist();need(len(names)==len(set(names)),'Duplicate delivered archive members')
    actual_names={name.removeprefix(prefix) for name in names if name.startswith(prefix) and not name.endswith('/')}
    need(actual_names==set(expected),'Delivered actualWorld member inventory differs')
    actual={name:stream_sha(archive,prefix+safe(name)) for name in sorted(actual_names)}
    need(actual==expected,'Delivered actualWorld differs from current tested World bytes')
    return actual


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--selection',type=Path,required=True)
    ap.add_argument('--execution-receipt',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();config,jar,runtime=selection(a.selection)
    need(config.get('feature_scope')=='124','Explicit current scope124 release required')
    authority=config['root_world_authority'];world=Path(authority['world']).resolve()
    out=a.out.resolve();need(not out.exists() and not out.is_relative_to(world),'Fresh final receipt outside actual World required')
    execution=json.loads(a.execution_receipt.read_text('utf-8-sig'))
    need(execution.get('feature_scope')=='124' and execution.get('client_server_same_world') is True
         and execution.get('client_server_same_jar') is True,'Actual dual package execution receipt required')
    need(execution.get('acceptance_record',execution.get('native_acceptance'))==config['acceptance'],'Execution acceptance differs from current selection')
    rows=execution['archives'];need(len(rows)==2 and {r['side'] for r in rows}=={'server','client'},'Exact server/client archives required')
    files=world_files(world,'124',authority);pins={name:sha(path) for name,path in files.items()}
    need(execution['world_files']==pins,'World changed after actual packaging')
    actual_worlds=[]
    for row in rows:
        archive_path=Path(row['path']).resolve()
        need(sha(archive_path)==row['sha256'] and archive_path.stat().st_size==row['bytes'],
             'Actual delivered archive changed: '+row['side'])
        prefix='SEELE_R52_WORLD/' if row['side']=='server' else 'overrides/saves/SEELE_R52_WORLD/'
        payload='' if row['side']=='server' else 'overrides/'
        with zipfile.ZipFile(archive_path) as archive:
            actual=verify_world_members(archive,prefix,pins)
            need(stream_sha(archive,payload+'mods/projectseele-0.1.0-all.jar')==config['jar']['sha256'],
                 'Actual delivered Jar differs: '+row['side'])
            for name,path in runtime.items():
                need(stream_sha(archive,payload+'projectseele-local-maps/'+safe(name))==sha(path),
                     'Actual delivered runtime differs: '+row['side']+'/'+name)
        actual_worlds.append(dict(side=row['side'],archive=archive_path.as_posix(),archive_sha256=row['sha256'],
                                 world_prefix=prefix,actualWorld=actual,all_world_members_readback=True))
    final_files=world_files(world,'124',authority)
    need({name:sha(path) for name,path in final_files.items()}==pins,'Current World changed during actual archive readback')
    baseline=json.loads(Path(authority['baseline_file']).read_text('utf-8-sig'))
    original={safe(row['path']):row['sha256'] for row in baseline['files'] if row['path']!='session.lock'}
    lists={}
    for name,digest in pins.items():
        state='unchanged' if original.get(name)==digest else 'changed' if name in original else 'added'
        lists.setdefault(category(name),[]).append(dict(path=name,sha256=digest,baseline_sha256=original.get(name),change=state))
    removed=sorted(set(original)-set(pins))
    result=dict(schema='projectseele.r53.final-actual-world-delivery-readback.v1',passed=True,
                source_world=world.as_posix(),root_world_authority=authority,jar_sha256=config['jar']['sha256'],
                directory_fingerprint=config['world_metadata_pins']['directory_fingerprint'],
                selection=dict(path=a.selection.resolve().as_posix(),sha256=sha(a.selection)),
                execution_receipt=dict(path=a.execution_receipt.resolve().as_posix(),sha256=sha(a.execution_receipt)),
                acceptance_record=config['acceptance'],native_acceptance=None if config.get('release_type')=='code_reviewed_runtime_unverified' else config['acceptance'],qualification=config.get('qualification'),actualWorld=actual_worlds,
                client_server_same_world=True,client_server_same_jar=True,world_file_count=len(pins),
                delivered_file_lists=lists,removed_baseline_files=removed,
                identity_and_progress_validation='Selected identity and progress evidence plus exact delivered bytes; runtime status follows qualification, never inferred from byte equality',
                gameplay_or_visual_validation_performed_by_this_tool=False,world_written=False,packages_written=False)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf8',newline='\n') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(receipt=out.as_posix(),passed=True,world_files=len(pins),actual_archives=2,world_written=False)))


if __name__=='__main__':main()
