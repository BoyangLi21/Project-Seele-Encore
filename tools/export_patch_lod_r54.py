"""Refresh exact saved DH columns touched by installed map patches.

Uses export_r53_lod_source.export_tile unchanged; SavedColumnLodImporterR53
accepts the resulting columns/ directory without a new native API or format.
No world/SQLite/player/entity/traffic data is written. --plan-only reads patches
only; actual export holds a read lock on the stopped world's session.lock.
"""
from __future__ import annotations
import argparse,contextlib,gzip,json,os,sys,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')


def patch_tiles(paths):
    tiles=set();inputs=[]
    for path in paths:
        path=Path(path).resolve();opener=gzip.open if path.suffix=='.gz' else open
        cells=0;unchanged=0;local=set()
        with opener(path,'rt',encoding='utf-8-sig') as stream:
            for number,line in enumerate(stream,1):
                if not line.strip():continue
                row=json.loads(line)
                pos=row.get('pos')
                if not isinstance(pos,list) or len(pos)!=3 or any(not isinstance(v,int) or isinstance(v,bool) for v in pos):
                    raise ValueError(f'{path}:{number}: exact integer [x,y,z] required')
                if row.get('before')==row.get('after'):
                    unchanged+=1;continue
                local.add((pos[0]//64,pos[2]//64));cells+=1
        tiles.update(local);inputs.append(dict(path=str(path),changed_cells=cells,unchanged_or_nbt_only=unchanged,tiles=len(local)))
    return sorted(tiles),inputs


@contextlib.contextmanager
def stopped_world(world):
    lock_path=world/'session.lock'
    if not lock_path.is_file():raise ValueError('Expected existing saved-world session.lock: '+str(lock_path))
    with lock_path.open('rb') as handle:
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBRLCK,1)
            except OSError as error:raise RuntimeError('Minecraft still owns this world. Save and close it before exporting LOD columns.') from error
            try:yield
            finally:
                handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            try:fcntl.lockf(handle,fcntl.LOCK_SH|fcntl.LOCK_NB,1,0)
            except OSError as error:raise RuntimeError('Minecraft still owns this world. Save and close it before exporting LOD columns.') from error
            try:yield
            finally:fcntl.lockf(handle,fcntl.LOCK_UN,1,0)


def write_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    os.replace(temporary,path)


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('world',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('patches',type=Path,nargs='*')
    parser.add_argument('--patch-list',type=Path,help='UTF-8 text, one installed forward.jsonl[.gz] per line')
    parser.add_argument('--installation',type=Path,help='Successful array installation receipt containing changed tiles')
    parser.add_argument('--workers',type=int,choices=range(1,5),default=2)
    parser.add_argument('--allow-partial',action='store_true',help='R54 importer keeps absent columns unknown; never invent source blocks')
    parser.add_argument('--resume-failed',action='store_true',help='Retry only unavailable tiles from this exact completed export attempt')
    parser.add_argument('--plan-only',action='store_true',help='List affected tiles without opening the world')
    parser.add_argument('--deps',type=Path,help='Optional directory containing nbtlib; appended after installed runtime packages')
    args=parser.parse_args();paths=list(args.patches)
    if args.patch_list:
        for line in args.patch_list.read_text(encoding='utf-8-sig').splitlines():
            line=line.strip()
            if line and not line.startswith('#'):paths.append(Path(line))
    paths=list(dict.fromkeys(path.resolve() for path in paths))
    if not paths and not args.installation:parser.error('Provide installed forward patches, --patch-list or --installation')
    world=args.world.resolve();out=args.output.resolve();tiles,inputs=patch_tiles(paths)
    if args.installation:
        installed=json.loads(args.installation.read_text(encoding='utf8'))
        if installed.get('status')!='installed' or Path(installed['world']).resolve()!=world:
            raise ValueError('Expected a completed installation for this exact world')
        if any(len(p)!=2 or any(type(v)is not int for v in p) for p in installed['tiles']):
            raise ValueError('Invalid installed tile coordinates')
        tiles=sorted(set(tiles)|{tuple(p)for p in installed['tiles']})
        inputs.append(dict(installation=str(args.installation),changed_cells=installed['cells'],tiles=len(installed['tiles'])))
    out.mkdir(parents=True,exist_ok=True)
    report=dict(world=str(world),dimension='projectseele:geofront',tile_size=64,tiles=tiles,
                total=len(tiles),inputs=inputs,format='SavedColumnLodImporterR53 unchanged',
                import_directory=str(out/'columns'),world_written=False,sqlite_written=False,allow_partial=args.allow_partial)
    write_json(out/'tile-plan.json',report)
    if args.plan_only:
        print(f'Planned {len(tiles)} changed tiles from {len(paths)} patches; world not opened.')
        return
    if not tiles:
        write_json(out/'export.json',dict(report,done=True,exported=[],missing=[]));print('No block-state changes; existing cache retained.');return
    if args.deps:sys.path.append(str(args.deps.resolve()))
    from export_r53_lod_source import export_tile
    columns=out/'columns';staging=out/'staging';columns.mkdir(exist_ok=True);staging.mkdir(exist_ok=True)
    expected={f'{x}_{z}.columns.gz'for x,z in tiles}
    extra=[f.name for f in columns.glob('*.columns.gz')if f.name not in expected]
    if extra:raise ValueError('Output contains other tile exports; use a new output directory: '+str(extra[:8]))
    start=time.monotonic();rows=[];missing=[];unbuilt=[];requested=tiles
    if args.resume_failed:
        previous=json.loads((out/'export.json').read_text('utf8'))
        if previous['world']!=str(world)or previous['tiles']!=[list(p)for p in tiles]:raise ValueError('Resume requires the exact original world and tile set')
        rows=previous['exported'];requested=[tuple(r['tile'])for r in previous['missing']]
        unbuilt=previous.get('unbuilt_tiles',[])
        if not requested:raise ValueError('Export is already complete')
    def export(tile):
        row=export_tile(world,tile,staging,allow_partial=args.allow_partial)
        name=f'{tile[0]}_{tile[1]}.columns.gz'
        os.replace(staging/name,columns/name)
        return row
    with stopped_world(world):
        with ThreadPoolExecutor(max_workers=args.workers,thread_name_prefix='seele-column-export')as pool:
            jobs={pool.submit(export,tile):tile for tile in requested}
            for future in as_completed(jobs):
                try:rows.append(future.result())
                except Exception as error:
                    if args.allow_partial and str(error).startswith('No saved source chunks in tile '):
                        # A repaired protochunk is deliberately still not a
                        # FULL world column. Do not invent an all-air LOD.
                        unbuilt.append(dict(tile=jobs[future],reason='No FULL saved columns; native generation will provide the distant terrain'))
                    else:missing.append(dict(tile=jobs[future],error=str(error)))
                progress=dict(completed=len(rows),failed=len(missing),unbuilt=len(unbuilt),total=len(tiles),seconds=round(time.monotonic()-start))
                write_json(out/'progress.json',progress)
                if (len(rows)+len(missing))%10==0 or len(rows)+len(missing)==len(tiles):print(progress,flush=True)
    rows.sort(key=lambda row:tuple(row['tile']));missing.sort(key=lambda row:tuple(row['tile']))
    write_json(out/'export.json',dict(report,done=not missing,exported=rows,missing=missing,unbuilt_tiles=unbuilt,seconds=round(time.monotonic()-start)))
    if missing:raise SystemExit(f'{len(missing)} tiles unavailable; do not import a partial set. Details: {out / "export.json"}')
    print(f'Export complete: {len(rows)} tiles. Native importer directory: {columns}',flush=True)

if __name__=='__main__':main()
