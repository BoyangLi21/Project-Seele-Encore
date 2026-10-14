"""One exact isolated R52 validation save. No launch or gameplay import back.

Refresh is permitted only before that clone has ever been opened, and only
while every cloned byte still equals its recorded source. A used QA save is
never silently reset to make a later test look like a continuous run.
"""
import argparse,hashlib,json,msvcrt,shutil,os
from pathlib import Path
from r52_spatial_plan import BASE
from extend_world_depth_r52 import acquire_world_lock

SOURCE=BASE/'WORLD_R52'
TARGET=Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game/saves/SEELE_R52_REVIEW')
RECEIPT=BASE/'native_r52_validation/CLONE_RECEIPT.json'


def sha(path):
    with path.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()


def inventory(folder):
    result={}
    for p in folder.rglob('*'):
        assert not p.is_symlink()and not p.is_junction(),('No linked world member',p)
        if p.is_file()and p.name!='session.lock':result[p.relative_to(folder).as_posix()]=sha(p)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--refresh-before-first-use',action='store_true');args=parser.parse_args()
    assert SOURCE.resolve()!=TARGET.resolve()and TARGET.name=='SEELE_R52_REVIEW'
    if args.refresh_before_first_use:
        old=json.loads(RECEIPT.read_text('utf8'));assert not old['ever_launched']
        assert inventory(TARGET)==old['target_files'],'QA save changed; preserve actual run, never overwrite gameplay'
    else:assert not TARGET.exists()and not RECEIPT.exists(),'Preserve the single existing validation copy'
    lock=acquire_world_lock()
    try:
        before=inventory(SOURCE);TARGET.mkdir(parents=True,exist_ok=True);copied=0
        if args.refresh_before_first_use:assert set(old['target_files'])<=set(before),'Source retirement requires an explicit QA refresh review'
        for name,digest in before.items():
            target=TARGET/name
            if target.is_file()and sha(target)==digest:continue
            target.parent.mkdir(parents=True,exist_ok=True);pending=target.with_name(target.name+'.r52-copy-tmp')
            assert not pending.exists();shutil.copyfile(SOURCE/name,pending);assert sha(pending)==digest;os.replace(pending,target);copied+=1
        actual=inventory(TARGET);assert actual==before and inventory(SOURCE)==before
        result=dict(source_world=str(SOURCE),target_world=str(TARGET),source_world_written=False,ever_launched=False,
            files_copied_this_step=copied,bytes=sum((SOURCE/name).stat().st_size for name in before),target_files=actual,
            status='Exact pre-installation map snapshot; final assembly bundle and new physical deltas must be refreshed before first native use',native_verified=False)
        RECEIPT.parent.mkdir(exist_ok=True);RECEIPT.write_text(json.dumps(result,indent=2),'utf8')
        print(json.dumps({k:v for k,v in result.items()if k!='target_files'}),flush=True)
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
