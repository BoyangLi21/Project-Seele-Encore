"""Root-only atomic exact file installer for the reviewed pyramid metadata epoch."""
from pathlib import Path
import argparse, hashlib, json, msvcrt
import extend_world_depth_r52 as extension
from apply_s20_approved_semantic_repairs import atomic_replace


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    base, candidate = a.base.resolve(), a.candidate.resolve()
    world = base / 'WORLD'
    plan = json.loads((candidate / 'PLAN.json').read_text('utf8'))
    assert plan['schema'] == 'projectseele.r53.pyramid-exact-files.v1'
    assert Path(plan['world']).resolve() == world and not plan['world_written']
    out = base / 'pyramid_completion' / plan['stage']
    assert not (out / 'APPLIED.json').exists()
    extension.WORLD = world
    lock = extension.acquire_world_lock()
    targets, written = [], []
    try:
        for item in plan['files']:
            path = Path(item['target']).resolve()
            assert path.is_relative_to(world) or path == base / 'runtime_directory/staff/ROOT_STAFF.json'
            before = (candidate / item['before_file']).read_bytes() if item['before_exists'] else None
            assert (path.read_bytes() if path.exists() else None) == before, ('Exact metadata/entity precondition changed', path)
            after = (candidate / item['after_file']).read_bytes()
            assert sha(after) == item['after_sha256'] and (before is None or sha(before) == item['before_sha256'])
            targets.append((path, before, after))
        for item in plan.get('unchanged_files', []):
            assert sha((world / item['relative']).read_bytes()) == item['sha256'], ('Preserved identity/state changed', item['relative'])
        out.mkdir(parents=True, exist_ok=True)
        (out / 'PREFLIGHT.json').write_text(json.dumps(dict(plan=plan, exact_before_verified=True, world_written=False), ensure_ascii=False, indent=2), 'utf8')
        if not a.apply:
            print(json.dumps(dict(files=len(targets), exact_before_verified=True, world_written=False)))
            return
        backup = out / 'before'
        backup.mkdir()
        for i, (path, before, after) in enumerate(targets):
            if before is not None:
                (backup / f'{i}.bin').write_bytes(before)
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_replace(path, after)
            written.append((path, before))
            assert path.read_bytes() == after
        for item in plan.get('unchanged_files', []):
            assert sha((world / item['relative']).read_bytes()) == item['sha256']
        report = dict(world_written=True, stage=plan['stage'], files=plan['files'], complete_inverse_in_candidate=True, exact_files_readback=len(targets), evidence=plan.get('evidence'), native_game_verified=False)
        (out / 'APPLIED.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
        print(json.dumps(dict(world_written=True, exact_files_readback=len(targets), native_game_verified=False)))
    except BaseException:
        for path, before in reversed(written):
            if before is None:
                path.unlink()
            else:
                atomic_replace(path, before)
        raise
    finally:
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


if __name__ == '__main__':
    main()
