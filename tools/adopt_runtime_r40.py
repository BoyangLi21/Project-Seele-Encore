"""Adopt tested private R40 motion files; preserve originals and source world."""
from pathlib import Path
import json,hashlib,shutil,datetime
from release_combat_r36 import guard
from check_runtime_r37 import check

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/world_combat_r40'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    guard();local=ROOT/'run/projectseele-local-maps';candidates=ART/'phrase_candidate'
    for key in range(5):
        label='candidate' if key==1 else f'candidate_v{key}'
        report=json.loads((candidates/(label+'_result.json')).read_text());assert report['passed'] and len(report['cases'])==7,label
    finale=ART/'envelopment_native_final';result=json.loads((finale/'result.json').read_text());assert result['passed']
    run=json.loads((finale/'run.json').read_text());movie=ART/'envelopment_arap/first_battle_r24.json';surface=ART/'envelopment_arap/sachiel_wrap_r14.bin'
    assert sha(movie)==run['movie_sha256'] and sha(surface)==run['surface_sha256']
    native=list((ART/'native_surface_audit').glob('surface_*.json'));assert native
    audit=json.loads(max(native,key=lambda p:p.stat().st_mtime).read_text());assert audit['passed'],audit
    sources={f'eva_gameplay_r32_{key}.json':candidates/f'eva_gameplay_r32_{key}.json' for key in range(5)}
    sources.update({'sachiel_gameplay_r32.json':candidates/'sachiel_gameplay_r32.json','first_battle_r24.json':movie,'sachiel_wrap_r14.bin':surface})
    backup=ART/'runtime_before_adoption'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S');backup.mkdir(parents=True)
    for name in sources:
        p=local/name
        if p.exists():shutil.copy2(p,backup/name)
    if (local/'revision_r40.json').exists():shutil.copy2(local/'revision_r40.json',backup/'revision_r40.json')
    for name,path in sources.items():shutil.copy2(path,local/name)
    try:check(local)
    except BaseException:
        for name in sources:
            if (backup/name).exists():shutil.copy2(backup/name,local/name)
        raise
    marker=dict(revision=40,protocol=44,created=datetime.datetime.now().astimezone().isoformat(),backup=str(backup),
                runtime_sha256={name:sha(local/name) for name in sources},base_combat_foundation=36,ordinary_sequence=['jab','cross'],
                adopted='Anatomical two-foot support, captured recovery, source-based paired surface performance',
                native_normal_cases=35,native_surface=audit,world_composition=str(ART/'world_composition/composed.json'))
    (local/'revision_r40.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),'utf8');(ART/'runtime_adopted.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),'utf8')
    print('R40 private runtime adopted; original world untouched',flush=True)


if __name__=='__main__':main()
