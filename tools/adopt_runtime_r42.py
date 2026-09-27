"""Install only the candidate hashes covered by the recorded R42 native reviews."""
from pathlib import Path
import datetime,hashlib,json,shutil
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r42'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    guard();proof=json.loads((ART/'native_acceptance.json').read_text('utf8'));assert proof['passed']
    local=ROOT/'run/projectseele-local-maps';prior=json.loads((local/'revision_r41.json').read_text('utf8'))
    for name,digest in prior['runtime_sha256'].items():assert sha(local/name)==digest,('Inherited runtime changed',name)
    changed={}
    for name,item in proof['runtime_inputs'].items():
        source=Path(item['path']);assert sha(source)==item['sha256'],('Candidate changed after review',name)
        target=local/name;assert not target.exists() or sha(target)==sha(source),('Already adopted different runtime',name)
        shutil.copy2(source,target);changed[name]=sha(target)
    marker=dict(revision=42,protocol=45,adopted=datetime.datetime.now().astimezone().isoformat(),preferred_body='eva_body_r42.json',
                preferred_gameplay='eva_gameplay_r42_<rig>.json',preferred_first_battle='first_battle_r42.json',
                runtime_sha256={**prior['runtime_sha256'],**changed},evidence_sha256=sha(ART/'native_acceptance.json'),
                previous_files_retained=True)
    (local/'revision_r42.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),'utf8')
    (ART/'runtime_adopted.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),'utf8');print('Adopted',len(changed),'reviewed R42 runtime files')


if __name__=='__main__':main()
