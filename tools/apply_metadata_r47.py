"""Install exact whole-file R47 metadata candidates, with local reversible receipts."""
from pathlib import Path
import argparse,json,shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r47'

def main():
    global BASE
    parser=argparse.ArgumentParser();parser.add_argument('--world',type=Path,required=True)
    parser.add_argument('--patches',type=Path,nargs='+',required=True);parser.add_argument('--batch',required=True)
    parser.add_argument('--native-qa',action='store_true')
    parser.add_argument('--revision',type=int,choices=(47,48),default=47)
    args=parser.parse_args();world=args.world.resolve()
    BASE=ROOT/f'artifacts/rebuild_r{args.revision}'
    native_sources={(BASE/'native_qa/game/saves'/name).resolve() for name in (f'SEELE_R{args.revision}_WORLD',f'SEELE_R{args.revision}_RELEASE')}
    if args.revision==48:
        receipt=BASE/'native_qa/COPY_ONCE.json'
        if receipt.is_file():
            copy_info=json.loads(receipt.read_text('utf-8-sig'));retained=(BASE/'native_qa/worlds/SEELE_R48_QA').resolve()
            if copy_info.get('copied_once') is True and Path(copy_info['qa_world']).resolve()==retained:
                native_sources.add(retained)
    if not(world.is_relative_to((BASE/'construction').resolve()) or args.native_qa and world in native_sources):raise ValueError('Only Root construction or explicit stopped native QA source')
    out=BASE/'applied'/args.batch
    if out.exists():raise ValueError('Do not replay a metadata batch')
    staged={}
    for file in args.patches:
        patch=json.loads(file.read_text(encoding='utf-8'))
        for row in patch.get('operations',patch.get('files',[patch])):
            relative=row.get('relative_target',row.get('path'));target=(world/relative).resolve()
            if not target.is_relative_to(world):raise ValueError('Foreign target')
            current=staged.get(target,(target.read_bytes() if target.exists() else None,None))[0]
            if 'before_file' in row:
                before=None if row['before_file'] is None else Path(row['before_file']).read_bytes()
                after=None if row.get('after_file') is None else Path(row['after_file']).read_bytes()
                if current!=before:raise ValueError(('Exact prior file changed',relative))
            else:
                before=row.get('before');actual=None if current is None else json.loads(current.decode('utf-8-sig'))
                if actual!=before:raise ValueError(('Prior JSON changed',relative))
                after=None if row.get('after') is None else (json.dumps(row['after'],ensure_ascii=False,indent=2)+'\n').encode('utf-8')
            original=staged.get(target,(None,None))[1] if target in staged else (target.read_bytes() if target.exists() else None)
            staged[target]=(after,original)
    out.mkdir(parents=True);records=[]
    for ordinal,(target,(after,before)) in enumerate(staged.items()):
        # Current task only installs/replaces complete files. Retirement stays
        # a separately reviewed component operation, never a path delete here.
        if after is None:raise ValueError('File retirement requires its own explicit component')
        if before is not None:(out/f'{ordinal:03d}.before').write_bytes(before)
        (out/f'{ordinal:03d}.after').write_bytes(after)
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(after)
        if target.read_bytes()!=after:raise IOError(('Actual file readback failed',str(target)))
        records.append(dict(path=target.relative_to(world).as_posix(),before_present=before is not None,before_bytes=0 if before is None else len(before),after_bytes=len(after),backup=f'{ordinal:03d}.before' if before is not None else None))
    (out/'receipt.json').write_text(json.dumps({'world':str(world),'files':records,'progress_files_replaced':False},indent=2))
    print(f'Installed {len(records)} exact complete files with reversible prior bytes')

if __name__=='__main__':main()
