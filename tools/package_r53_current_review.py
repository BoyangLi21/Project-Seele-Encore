"""Build the established R53 server/PCL formats from the current singleplayer save."""
from pathlib import Path
from collections.abc import Mapping
import argparse,json,shutil,zipfile,msvcrt,hashlib
from patch_zip_entries import replace_entries

class Payloads(Mapping):
    def __init__(self, entries): self.entries=entries
    def __iter__(self): return iter(self.entries)
    def __len__(self): return len(self.entries)
    def __getitem__(self,key):
        value=self.entries[key]
        return value.read_bytes() if isinstance(value,Path) else value

def main():
    ap=argparse.ArgumentParser(__doc__)
    ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--delivery',type=Path,required=True)
    ap.add_argument('--date',required=True)
    ap.add_argument('--side',choices=('both','Server','Client_PCL'),default='both')
    ap.add_argument('--build',type=int,default=209)
    ap.add_argument('--refresh',action='store_true')
    a=ap.parse_args();base=a.base.resolve();delivery=a.delivery.resolve()
    world=base/'client/saves/SEELE_R53_WORLD';jar=base/'ready-client/projectseele-0.1.0-all.jar'
    if not world.joinpath('level.dat').is_file() or not jar.is_file():raise ValueError('Actual save and ready mod required')
    lock=None
    if a.side!='Client_PCL':
        lock=world.joinpath('session.lock').open('r+b');msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        world_files={} if a.side=='Client_PCL' else {p.relative_to(world).as_posix():p for p in world.rglob('*') if p.is_file() and p.name not in {'session.lock'} and '.tmp' not in p.suffixes}
        runtime={p.relative_to(base/'client/projectseele-local-maps').as_posix():p for p in (base/'client/projectseele-local-maps').rglob('*') if p.is_file()}
        review=Path(__file__).resolve().parents[1]/'docs/R53_LOCAL_REVIEW.zh.md'
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
                starlight=base/'ready-client/starlight-1.1.2+forge.1cda73c.jar'
                if starlight.is_file():
                    expected='cc89c6b2dd0db709586028c7732a57a3e6184f19cc2b98b25964c720c3ab434031e62de23e0dab022575d637b5e4a34b5813164d32ec356d56588da400e7d026'
                    if hashlib.sha512(starlight.read_bytes()).hexdigest()!=expected:raise ValueError('Pinned Starlight artifact differs')
                    entries[prefix+'mods/'+starlight.name]=starlight
                    entries[prefix+'licenses/Starlight-LGPL-3.0.txt']=review.parent/'licenses/Starlight-LGPL-3.0.txt'
                    entries[prefix+'licenses/Starlight-NOTICE.txt']=review.parent/'licenses/Starlight-NOTICE.txt'
                    entries[prefix+'licenses/Starlight-1cda73c-source.zip']=base/'ready-client/Starlight-1cda73c-source.zip'
                    remove_starlight={n for n in old if n.startswith(prefix+'mods/starlight-') and n!=prefix+'mods/'+starlight.name}
                else:remove_starlight=set()
                entries[prefix+'HAKONE_LONG_RANGE_PLAN_R53.zh.md']=review.parent/'HAKONE_LONG_RANGE_PLAN_R53.zh.md'
                entries.update({prefix+'projectseele-local-maps/'+n:p for n,p in runtime.items()})
                remove={n for n in old if n.startswith(prefix+'projectseele-local-maps/') and n not in entries}
                remove.update(remove_starlight)
                remove.update(n for n in old if n.endswith(('R52_ROLLBACK_BATCH.json','MAP_TODO.zh.md')))
                if side=='Server':
                    remove.update(n for n in old if n.startswith(('SEELE_R52_WORLD/','SEELE_R53_WORLD/')))
                    entries.update({'SEELE_R53_WORLD/'+n:p for n,p in world_files.items()})
                    props=z.read('server.properties').decode('utf8')
                    lines=['level-name=SEELE_R53_WORLD' if x.startswith('level-name=') else x for x in props.splitlines()]
                    entries['server.properties']=('\n'.join(lines)+'\n').encode('utf8')
                else:
                    remove.update(n for n in old if n.startswith('overrides/saves/'))
                    manifest=json.loads(z.read('manifest.json'));manifest['name']='EVANGELION:Encore R53';manifest['version']='R53-'+a.date+'-PCL';entries['manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf8')
                    shader=base/'client/shaderpacks/SEELE_Local_Cavern_R53_Private_v1.zip'
                    if shader.is_file():entries[prefix+'shaderpacks/'+shader.name]=shader
                    shader_settings=shader.with_suffix(shader.suffix+'.txt')
                    if shader_settings.is_file():entries[prefix+'shaderpacks/'+shader_settings.name]=shader_settings
                    dh=base/'client/mods/DistantHorizons-2.3.4-b-1.20.1-fabric-forge.jar'
                    if dh.is_file():
                        entries[prefix+'mods/'+dh.name]=dh
                        entries[prefix+'config/DistantHorizons.toml']=base/'client/config/DistantHorizons.toml'
                        remove.update(n for n in old if n.startswith(prefix+'mods/DistantHorizons-') and n!=prefix+'mods/'+dh.name)
                    settings=base/'client/config/oculus.properties'
                    if settings.is_file():entries[prefix+'config/oculus.properties']=settings
                remove.difference_update(entries)
            if source!=target:shutil.copyfile(source,target)
            replace_entries(target,Payloads(entries),remove)
            with zipfile.ZipFile(target) as z:
                names=set(z.namelist())
                if side=='Client_PCL':assert not any(n.startswith('overrides/saves/') for n in names)
                else:assert {n.removeprefix('SEELE_R53_WORLD/') for n in names if n.startswith('SEELE_R53_WORLD/')}==set(world_files)
            results=[r for r in results if r['side']!=side]
            results.append({'side':side,'file':str(target),'bytes':target.stat().st_size,'changed_entries_read_back':len(entries),'world_files':len(world_files) if side=='Server' else 0,'build':a.build})
        report={'version':'R53','actual_save':str(world),'all_changed_entries_compared_byte_for_byte':True,'packages':results,'acceptance':'Human gameplay/art confirmation still required'}
        (delivery/f'R53_{a.date}_DELIVERY_RECEIPT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
        (delivery/f'R53_交付与验收清单_{a.date}.txt').write_text(review.read_text('utf8'),'utf8')
        print(json.dumps(report,ensure_ascii=False))
    finally:
        if lock is not None:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':main()
