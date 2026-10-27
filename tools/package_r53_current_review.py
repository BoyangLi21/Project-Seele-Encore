"""Build the established R53 server/PCL formats from the current singleplayer save."""
from pathlib import Path
from collections.abc import Mapping
import argparse,json,shutil,zipfile,msvcrt,os,re,tempfile
from prepare_r53_ready_sync import CLIENT_TREES, NAVIGATION
from patch_zip_entries import replace_entries

class Payloads(Mapping):
    def __init__(self, entries): self.entries=entries
    def __iter__(self): return iter(self.entries)
    def __len__(self): return len(self.entries)
    def __getitem__(self,key):
        value=self.entries[key]
        return value.read_bytes() if isinstance(value,Path) else value


def payload_files(root, world=False):
    """Prune derived caches before walking; never prune saved gameplay/generation data."""
    if not root.exists():
        return
    for directory, children, files in os.walk(root, followlinks=False):
        current=Path(directory)
        for name in children:
            if (current/name).is_symlink():
                raise ValueError('Linked delivery directory: '+str(current/name))
        children[:]=[name for name in children if not private_archive_entry(name)]
        children.sort()
        for name in sorted(files):
            path=current/name
            if path.is_symlink():raise ValueError('Linked delivery file: '+str(path))
            if name=='session.lock' or '.tmp' in path.suffixes or private_archive_entry(name):
                continue
            if world and (name.startswith('DistantHorizons.sqlite') or name.startswith('Distant_Horizons.sqlite')):
                continue
            yield path


def require_normal_save(client):
    log=client/'logs/latest.log'
    text=log.read_text('utf-8',errors='replace')
    saved=text.rfind('All dimensions are saved')
    started=max(text.rfind('Starting integrated minecraft server'),
                text.rfind('Starting minecraft server version'))
    if saved<0 or saved<started:
        raise RuntimeError('Latest session has no completed normal Save and Quit; do not package a crashed session')


def checked_copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
    with source.open('rb') as a,target.open('rb') as b:
        while True:
            left=a.read(1024*1024);right=b.read(1024*1024)
            if left!=right:raise RuntimeError('Ready copy readback differs: '+str(target))
            if not left:break


def sync_ready(base,world,overrides,report,date,build):
    # The caller holds this same world's session.lock through ZIP and ready readback.
    stage=Path(tempfile.mkdtemp(prefix='ready-stage-',dir=base))
    ready_client=stage/'ready-client';ready_world=stage/'ready-world'
    ready_client.mkdir();ready_world.mkdir()
    for name,source in overrides.items():checked_copy(source,ready_client/name)
    client=base/'client'
    # Preserve the established flat installer inputs, sourced from current files only.
    flat={'projectseele-0.1.0-all.jar':client/'mods/projectseele-0.1.0-all.jar',
          'SEELE_Local_Cavern_R53_Private_v1.zip':client/'shaderpacks/SEELE_Local_Cavern_R53_Private_v1.zip',
          'starlight-1.1.2+forge.1cda73c.jar':client/'mods/starlight-1.1.2+forge.1cda73c.jar'}
    flat.update({name:client/'licenses'/name for name in
                 ('Starlight-1cda73c-source.zip','Starlight-LGPL-3.0.txt','Starlight-NOTICE.txt')})
    for name,source in flat.items():
        if source.is_file():checked_copy(source,ready_client/name)
    for name in (*NAVIGATION,'surface_angel_assault_r52.json'):
        if (world/name).is_file():checked_copy(world/name,ready_world/name)
    index={**report,'build':build,'ready_world_is_standalone_save':False,
           'ready_world_scope':'Navigation/metadata convenience copies only. The Server ZIP contains the complete original cold world, generation library and player/entity/task progress.',
           'launch':'Use the actual-client launcher directly; never install old ready over actual client.'}
    encoded=json.dumps(index,ensure_ascii=False,indent=2)+'\n'
    for folder in (ready_client,ready_world):
        (folder/'CURRENT_DELIVERY.json').write_text(encoded,'utf-8')
        if json.loads((folder/'CURRENT_DELIVERY.json').read_text('utf-8'))!=index:
            raise RuntimeError('Ready index readback differs')
    moves=[]
    for name in ('ready-client','ready-world'):
        target=base/name;backup=base/(name+'.before-'+date+'-build'+str(build))
        if target.is_symlink() or target.resolve().parent!=base or backup.resolve().parent!=base or backup.exists():
            raise ValueError('Ready destination/backup is not a fresh direct child: '+str(target))
        moves.append((stage/name,target,backup))
    # Keep prior ready directories recoverable; never merge stale state into the new tree.
    promoted=[]
    try:
        for source,target,backup in moves:
            if target.exists():target.rename(backup)
            try:source.rename(target)
            except BaseException:
                if backup.exists():backup.rename(target)
                raise
            promoted.append((source,target,backup))
    except BaseException:
        for source,target,backup in reversed(promoted):
            target.rename(source)
            if backup.exists():backup.rename(target)
        raise
    stage.rmdir()
    return {'client':str(base/'ready-client'),'world_index':str(base/'ready-world/CURRENT_DELIVERY.json'),
            'client_files_read_back':len(overrides),'previous_ready_preserved':True}


def private_archive_entry(name):
    parts=Path(name).parts
    return any(part in {'.Codex','logs','crash-reports','debug','pose-captures','screenshots',
                        'Distant_Horizons_server_data','DistantHorizons'} for part in parts) or any(
        part.startswith(('hs_err_pid','replay_pid','DistantHorizons.sqlite','Distant_Horizons.sqlite')) for part in parts)

def main():
    ap=argparse.ArgumentParser(__doc__)
    ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--delivery',type=Path,required=True)
    ap.add_argument('--date',required=True)
    ap.add_argument('--side',choices=('both','Server','Client_PCL'),default='both')
    ap.add_argument('--build',type=int,required=True,help='Explicit final installed build; never infer it from an older archive')
    ap.add_argument('--refresh',action='store_true')
    ap.add_argument('--sync-ready',action='store_true',help='After both ZIPs pass readback, promote current ready trees under the same cold-world lock')
    ap.add_argument('--friends',action='store_true',help='Lean PCL overrides with the current offline terrain caches')
    a=ap.parse_args();base=a.base.resolve();delivery=a.delivery.resolve()
    if not re.fullmatch(r'[0-9]{8}',a.date) or a.build<=0:raise ValueError('Explicit YYYYMMDD date and positive installed build required')
    if a.sync_ready and a.side!='both':raise ValueError('--sync-ready requires both complete delivery packages')
    client=base/'client';world=client/'saves/SEELE_R53_WORLD';jar=client/'mods/projectseele-0.1.0-all.jar'
    if not world.joinpath('level.dat').is_file() or not jar.is_file():raise ValueError('Actual save and actual installed mod required')
    # The same cold boundary covers runtime, client settings and every saved dimension.
    # Do not create a fresh lock file: it must be the actual world's existing lock.
    lock=world.joinpath('session.lock').open('r+b')
    try:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        lock.close()
        raise RuntimeError('Actual world is still open; normal Save and Quit is required') from None
    try:
        require_normal_save(client)
        if a.sync_ready:
            for name in ('ready-client','ready-world'):
                if (base/(name+'.before-'+a.date+'-build'+str(a.build))).exists():raise FileExistsError('Ready backup for this batch already exists')
        world_files={} if a.side=='Client_PCL' else {p.relative_to(world).as_posix():p for p in payload_files(world, world=True)}
        runtime={p.relative_to(client/'projectseele-local-maps').as_posix():p for p in payload_files(client/'projectseele-local-maps')}
        overrides={p.relative_to(client).as_posix():p for tree in CLIENT_TREES for p in payload_files(client/tree)}
        for name in ('options.txt','patchouli_data.json'):
            if (client/name).is_file():overrides[name]=client/name
        review=Path(__file__).resolve().parents[1]/'docs/R53_LOCAL_REVIEW.zh.md'
        lod_entries={}
        if a.friends:
            review=Path(__file__).resolve().parents[1]/'docs/R53_FRIENDS_QUICKSTART.zh.md'
            overrides={n:p for n,p in overrides.items() if n!='patchouli_data.json'
                       and n!='config/projectseele-private-visuals-r46.json'
                       and not any(x.lower().endswith(('.bak','.old','.backup','.log','.tmp')) for x in Path(n).parts)
                       and (not n.startswith('shaderpacks/') or Path(n).name in
                            {'SEELE_Local_Cavern_R53_Private_v1.zip','SEELE_Local_Cavern_R53_Private_v1.zip.txt'})}
            # DH's current server log supplies its existing level identifier.
            # The server has no DH mod; multiplayer clients use seed@dimension.
            log=(client/'logs/latest.log').read_text('utf8',errors='replace')
            seeds=set(re.findall(r'DhClientServerLevel\{SEELE_R53_WORLD_([0-9a-v]{13})@',log))
            if len(seeds)!=1:raise ValueError('Current DH level identifier missing or ambiguous')
            seed=seeds.pop()
            for dimension,relative in {'minecraft:overworld':'data/DistantHorizons.sqlite',
                    'projectseele:geofront':'dimensions/projectseele/geofront/data/DistantHorizons.sqlite'}.items():
                source=world/relative
                if not source.is_file():raise FileNotFoundError(source)
                wal=Path(str(source)+'-wal')
                if wal.exists() and wal.stat().st_size:raise RuntimeError('LOD cache still has live WAL')
                folder=(seed+'@'+dimension).replace(':','@@')
                lod_entries['Distant_Horizons_server_data/SEELE/'+folder+'/DistantHorizons.sqlite']=source
                world_files[relative]=source
            overrides.update(lod_entries)
        batch=json.dumps({'version':'R53','date':a.date,'kind':'manual_acceptance','build':a.build,'client_contains_save':False,'gameplay_and_art_acceptance':'See delivery checklist; pending human confirmation'},ensure_ascii=False,indent=2).encode('utf8')
        receipt=delivery/f'R53_{a.date}_DELIVERY_RECEIPT.json'
        results=json.loads(receipt.read_text('utf8'))['packages'] if receipt.exists() else []
        for side in (('Server','Client_PCL') if a.side=='both' else (a.side,)):
            source=delivery/f'Project_SEELE_Encore_R53_20261014_{side}.zip'
            target=delivery/f'Project_SEELE_Encore_R53_{a.date}_{side}.zip'
            if target.exists():
                if not a.refresh:raise FileExistsError(target)
                source=target
            with zipfile.ZipFile(source) as z:
                old=set(z.namelist());prefix='' if side=='Server' else 'overrides/'
                entries={prefix+'mods/projectseele-0.1.0-all.jar':jar,prefix+'R53_DELIVERY_AND_ACCEPTANCE.zh.txt':review,prefix+'R53_BATCH.json':batch}
                # Actual third-party binaries and notices travel together. No old ready input.
                remove_starlight=set()
                if side=='Server':
                    missing={n for n in old if n.startswith('mods/') and n.endswith('.jar') and n not in overrides}
                    if missing:raise ValueError('Established server mod no longer exists in actual client: '+', '.join(sorted(missing)))
                    for name,path in overrides.items():
                        # Preserve the established server mod selection; refresh its actual files.
                        # Client-only renderer mods are included only in the PCL overrides below.
                        if name.startswith(('licenses/','config/','defaultconfigs/')) or name.startswith('mods/') and name in old:
                            entries[name]=path
                    starlight=client/'mods/starlight-1.1.2+forge.1cda73c.jar'
                    if starlight.is_file():
                        entries['mods/'+starlight.name]=starlight
                        remove_starlight={n for n in old if n.startswith('mods/starlight-') and n!='mods/'+starlight.name}
                if not a.friends:entries[prefix+'HAKONE_LONG_RANGE_PLAN_R53.zh.md']=review.parent/'HAKONE_LONG_RANGE_PLAN_R53.zh.md'
                entries.update({prefix+'projectseele-local-maps/'+n:p for n,p in runtime.items()})
                remove={n for n in old if n.startswith(prefix+'projectseele-local-maps/') and n not in entries}
                remove.update(remove_starlight)
                remove.update(n for n in old if private_archive_entry(n))
                if side=='Server':
                    remove.update(n for n in old if n.startswith(('licenses/','config/','defaultconfigs/')) and n not in entries)
                remove.update(n for n in old if n.endswith(('R52_ROLLBACK_BATCH.json','MAP_TODO.zh.md')))
                if side=='Server':
                    remove.update(n for n in old if n.startswith(('SEELE_R52_WORLD/','SEELE_R53_WORLD/')))
                    entries.update({'SEELE_R53_WORLD/'+n:p for n,p in world_files.items()})
                    props=z.read('server.properties').decode('utf8')
                    lines=['level-name=SEELE_R53_WORLD' if x.startswith('level-name=') else x for x in props.splitlines()]
                    entries['server.properties']=('\n'.join(lines)+'\n').encode('utf8')
                else:
                    remove.update(n for n in old if n.startswith('overrides/saves/'))
                    manifest=json.loads(z.read('manifest.json'))
                    if manifest.get('files'):raise ValueError('Embedded actual mods require the established download-free PCL manifest')
                    manifest['name']='EVANGELION:Encore R53';manifest['version']='R53-'+a.date+'-PCL';entries['manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf8')
                    entries.update({'overrides/'+name:path for name,path in overrides.items()})
                    replaced=tuple('overrides/'+tree+'/' for tree in CLIENT_TREES)
                    remove.update(n for n in old if n.startswith(replaced) and n not in entries)
                    # Missing current optional settings must not resurrect an older archive copy.
                    remove.update('overrides/'+name for name in ('options.txt','patchouli_data.json')
                                  if 'overrides/'+name in old and name not in overrides)
                    if a.friends:
                        allowed=tuple('overrides/'+tree+'/' for tree in CLIENT_TREES)+('overrides/Distant_Horizons_server_data/',)
                        keep={'overrides/options.txt','overrides/COMPLEMENTARY_CREDITS.txt',
                              'overrides/R53_DELIVERY_AND_ACCEPTANCE.zh.txt','overrides/R53_BATCH.json'}
                        remove.update(n for n in old if n.startswith('overrides/') and not n.startswith(allowed) and n not in keep)
                remove.difference_update(entries)
            if source!=target:shutil.copyfile(source,target)
            replace_entries(target,Payloads(entries),remove)
            with zipfile.ZipFile(target) as z:
                names=set(z.namelist())
                if side=='Client_PCL':assert not any(n.startswith('overrides/saves/') for n in names)
                else:assert {n.removeprefix('SEELE_R53_WORLD/') for n in names if n.startswith('SEELE_R53_WORLD/')}==set(world_files)
            results=[r for r in results if r['side']!=side]
            results.append({'side':side,'file':str(target),'bytes':target.stat().st_size,'changed_entries_read_back':len(entries),'world_files':len(world_files) if side=='Server' else 0,'build':a.build})
        report={'version':'R53','actual_save':str(world),'actual_mod':str(jar),'world_source':'single cold actual save; all dimensions and complete generation library; '+('current surface and GeoFront offline terrain caches included' if a.friends else 'derived DH cache excluded'),'all_changed_entries_compared_byte_for_byte':True,'packages':results,'acceptance':'Human gameplay/art confirmation still required'}
        if a.sync_ready:report['ready_sync']=sync_ready(base,world,overrides,report,a.date,a.build)
        (delivery/f'R53_{a.date}_DELIVERY_RECEIPT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
        (delivery/f'R53_交付与验收清单_{a.date}.txt').write_text(review.read_text('utf8'),'utf8')
        print(json.dumps(report,ensure_ascii=False))
    finally:
        if lock is not None:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':main()
