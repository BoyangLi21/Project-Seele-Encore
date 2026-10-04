"""Freeze the installed R44 local world for authorized R45 construction."""
from pathlib import Path
import hashlib, json, shutil, subprocess
from datetime import datetime, timezone
from release_combat_r36 import guard

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts/rebuild_r45'
INSTANCE = Path.home() / 'AppData/Roaming/.minecraft/versions/Project SEELE R44 Stage'
SOURCE = INSTANCE / 'saves/SEELE_R44_STAGE_WORLD'
BACKUP = ART / 'source_world_backup'
REVIEW = ROOT / 'run/saves/SEELE_FIELD_R45_REVIEW'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    guard()
    assert SOURCE.is_dir() and not BACKUP.exists() and not REVIEW.exists()
    release = json.loads((ROOT / 'artifacts/server-ready-r44-stage/RELEASE.json').read_text('utf8'))
    jars = list((INSTANCE / 'mods').glob('projectseele-*.jar'))
    assert len(jars) == 1 and sha(jars[0]) == release['mod_sha256']
    before = {p.relative_to(SOURCE).as_posix(): sha(p) for p in SOURCE.rglob('*') if p.is_file() and p.name != 'session.lock'}
    old = json.loads((ROOT / 'artifacts/facility_r31/baseline.json').read_text('utf8'))['original_user_files']
    originals = {name: sha(ROOT / name) for name in old}
    assert originals == old, 'Inspect pre-existing owner changes before freezing'
    ART.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, BACKUP, ignore=shutil.ignore_patterns('session.lock'))
    shutil.copytree(BACKUP, REVIEW)
    (REVIEW / 'session.lock').write_bytes(bytes.fromhex('e29883'))
    after = {p.relative_to(SOURCE).as_posix(): sha(p) for p in SOURCE.rglob('*') if p.is_file() and p.name != 'session.lock'}
    assert before == after
    assert all(sha(BACKUP / name) == digest and sha(REVIEW / name) == digest for name, digest in before.items())
    record = dict(created_utc=datetime.now(timezone.utc).isoformat(), source=str(SOURCE),
        source_mod=str(jars[0]), source_mod_sha256=release['mod_sha256'], backup=str(BACKUP), review=str(REVIEW),
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        files=before, original_user_files=originals, original_file_count=len(before),
        scope='Local R44 world authorized by owner; latest client session connected to a remote server, not a newer local integrated save',
        source_unchanged=True, model_and_motion_owner='root only', un_model_work_paused=True)
    (ART / 'baseline.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), 'utf8')
    print('R45 baseline frozen:', len(before), 'files; source and both copies match')

if __name__ == '__main__':
    main()
