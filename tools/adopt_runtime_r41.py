"""Adopt the exact verified R41 body, retaining the previous motion source."""
from pathlib import Path
import hashlib,json,shutil,datetime
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    guard();proof=json.loads((ART/'native_acceptance.json').read_text('utf8'));assert proof['passed']
    local=ROOT/'run/projectseele-local-maps';prior=json.loads((local/'revision_r40.json').read_text('utf8'))
    for name,digest in prior['runtime_sha256'].items():assert sha(local/name)==digest,('Previously accepted runtime changed',name)
    source=ART/'stance_candidate/eva_body_r41.json';assert sha(source)==proof['body_sha256']
    target=local/source.name
    assert not target.exists() or sha(target)==sha(source),'Do not overwrite another adopted candidate'
    shutil.copy2(source,target)
    marker=dict(revision=41,protocol=44,adopted=datetime.datetime.now().astimezone().isoformat(),preferred_body=target.name,
                runtime_sha256={**prior['runtime_sha256'],target.name:sha(target)},prior_body_retained='eva_body_r25.json',
                evidence_sha256=sha(ART/'native_acceptance.json'),source='Exact source used by the accepted native R41 checks')
    (local/'revision_r41.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),'utf8')
    (ART/'runtime_adopted.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),'utf8')
    from check_runtime_r41 import check
    check();print('Adopted exact R41 body; R25 file unchanged',flush=True)


if __name__=='__main__':main()
