"""Read-only hash check of the installed R42 profiles and preserved private rigs."""
from pathlib import Path
import hashlib,json
from check_runtime_r37 import check as foundation
ROOT=Path(__file__).resolve().parents[1]


def check():
    foundation();local=ROOT/'run/projectseele-local-maps';marker=json.loads((local/'revision_r42.json').read_text())
    assert marker['revision']==42 and marker['protocol']==45
    required=['eva_body_r42.json','first_battle_r42.json']+[f'eva_gameplay_r42_{i}.json' for i in range(5)]
    assert all(name in marker['runtime_sha256'] for name in required)
    for name,digest in marker['runtime_sha256'].items():assert hashlib.sha256((local/name).read_bytes()).hexdigest()==digest,name
    shader=json.loads((local/'revision_r39.json').read_text())['shader']
    assert hashlib.sha256((ROOT/'run/shaderpacks'/shader['filename']).read_bytes()).hexdigest()==shader['sha256']
    print('R42 private runtime and pinned shader ready; protocol 45.')


if __name__=='__main__':check()
