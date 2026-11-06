"""Root-only exact metadata installation with a byte precondition and inverse."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,msvcrt
import extend_world_depth_r52 as extension
from apply_s20_approved_semantic_repairs import atomic_replace

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--stage',required=True);ap.add_argument('--apply',action='store_true')
    a=ap.parse_args();base=a.base.resolve();world=base/'WORLD';plan=json.loads(a.manifest.read_text('utf-8-sig'))
    assert world==Path('D:/eva/artifacts/map_complete_20261013/WORLD').resolve()
    assert Path(plan['world']).resolve()==world and a.stage.replace('_','').isalnum()
    out=base/'metadata_completion'/a.stage;assert not (out/'APPLIED.json').exists()
    rows=plan['files'];assert rows and len({r['relative'] for r in rows})==len(rows)
    selected=[]
    for row in rows:
        name=row['relative'];p=PurePosixPath(name)
        assert not p.is_absolute() and ':' not in name and '\\' not in name and all(q not in ('','.','..') for q in name.split('/'))
        assert (name.endswith('.json') or name.endswith('.json.gz')) and p.parts[0] not in ('playerdata','entities','region','dimensions','mtr')
        target=world/name;assert target.resolve().is_relative_to(world) and not target.is_symlink()
        source=Path(row['candidate']).resolve();assert not source.is_relative_to(world) and sha(source)==row['candidate_sha256']
        before=target.read_bytes() if target.exists() else None
        assert (None if before is None else hashlib.sha256(before).hexdigest())==row['before_sha256'],('Metadata precondition differs',name)
        selected.append((row,target,source.read_bytes(),before))
    out.mkdir(parents=True,exist_ok=True);(out/'EXACT_MANIFEST.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n','utf-8')
    if not a.apply:print(json.dumps(dict(files=len(rows),conflicts=0,world_written=False)));return
    extension.WORLD=world;lock=extension.acquire_world_lock();written=[]
    try:
        for row,target,after,before in selected:
            assert (target.read_bytes() if target.exists() else None)==before
            if before is not None:
                backup=out/'inverse'/row['relative'];backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(before)
        for row,target,after,before in selected:
            target.parent.mkdir(parents=True,exist_ok=True);atomic_replace(target,after);written.append((target,before));assert target.read_bytes()==after
        report=dict(world=str(world),world_written=True,files=rows,full_byte_readback=True,native_game_verified=False)
        (out/'APPLIED.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
        print(json.dumps(dict(files=len(rows),full_byte_readback=True,world_written=True)))
    except BaseException:
        for target,before in reversed(written):
            if before is None:target.unlink()
            else:atomic_replace(target,before)
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
