"""Install only completed, derived DH data from the isolated cache server."""
import argparse,json,lzma,sqlite3,struct
from pathlib import Path
from install_r53_carrier_trays import stopped_world

REL=Path('dimensions/projectseele/geofront/data/DistantHorizons.sqlite')


def install(a):
    exported=json.loads((a.export/'export.json').read_text('utf8'))
    imported=json.loads((a.export/'columns/native-import.json').read_text('utf8'))
    stopped=json.loads((a.export/'cache-stop.json').read_text('utf8'))
    if stopped['state']!='ORDINARY_CONSOLE_STOP_SUBMITTED' or Path(stopped['actual_server_world']).resolve()!=a.cache.resolve():
        raise ValueError('An ordinary stop receipt for this exact cache server is required')
    if Path(exported['world']).resolve()!=a.world.resolve() or not exported['done'] or exported['missing']:
        raise ValueError('A complete export of the actual world is required')
    if not imported['done'] or imported['completed']!=len(exported['exported']):
        raise ValueError('The native importer has not completed this exact tile set')
    incomplete=a.export/'invalidate-incomplete.json'
    if incomplete.exists():
        invalidated=json.loads((a.export/'incomplete-invalidation.json').read_text('utf8'))
        partial=json.loads((a.export/'partial-columns/native-import.json').read_text('utf8'))
        plan=json.loads(incomplete.read_text('utf8'))
        if not invalidated['done'] or not partial['done'] or partial['completed']!=len(plan['partial_tiles']):
            raise ValueError('Incomplete-source cache invalidation and partial reimport must finish')
    with stopped_world(a.world),stopped_world(a.cache):
        with sqlite3.connect((a.cache/REL).resolve().as_uri()+'?mode=ro',uri=True)as src:
            pending=src.execute('select count(*) from FullData where ApplyToParent=1').fetchone()[0]
            if pending:raise ValueError(f'Distant parent updates are still pending: {pending}')
            if incomplete.exists():
                for row in exported['unbuilt_tiles']:
                    if src.execute('select 1 from FullData where DetailLevel=0 and PosX=? and PosZ=?',row['tile']).fetchone():
                        raise ValueError('Stale LOD remains for an unfinished tile: '+str(row['tile']))
                # These exact missing columns previously retained old terrain.
                # Check only absence, not every correctly imported geometry span.
                for row in exported['exported']:
                    missing={tuple(p)for p in row.get('missing_chunks',[])}
                    if not missing:continue
                    tx,tz=row['tile'];data=src.execute('select Data from FullData where DetailLevel=0 and PosX=? and PosZ=?',(tx,tz)).fetchone()
                    if data is None:raise ValueError('Partial source tile was not reimported')
                    raw=lzma.LZMADecompressor().decompress(data[0]);offset=0
                    for column in range(4096):
                        count=struct.unpack_from('>H',raw,offset)[0];offset+=2+count*8
                        if (tx*4+column//1024,tz*4+(column%64)//16)in missing and count:
                            raise ValueError(f'Stale unfinished column remains: {(tx,tz,column)}')
            a.out.mkdir(exist_ok=False)
            with sqlite3.connect((a.world/REL).resolve().as_uri()+'?mode=ro',uri=True)as actual,sqlite3.connect(a.out/'DistantHorizons.before.sqlite')as backup:
                actual.backup(backup)
            # SQLite backup includes committed WAL pages and handles the target
            # journal correctly; copying a main file over an old WAL does not.
            try:
                with sqlite3.connect(a.world/REL)as target:src.backup(target)
            except BaseException:
                with sqlite3.connect(a.out/'DistantHorizons.before.sqlite')as backup,sqlite3.connect(a.world/REL)as target:backup.backup(target)
                raise
    receipt=dict(status='installed',world=str(a.world),cache=str(a.cache),tiles=imported['completed'],
        unbuilt_tiles_kept_unknown=len(exported.get('unbuilt_tiles',[])),pending_parent_updates=0,
        cache_server_stopped_normally=True,only_distant_cache_copied_back=True,export=str(a.export),backup=str(a.out/'DistantHorizons.before.sqlite'))
    receipt['unfinished_columns_checked_absent']=incomplete.exists()
    (a.out/'installation.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('world','cache','export','out'):p.add_argument('--'+name,type=Path,required=True)
    install(p.parse_args())
