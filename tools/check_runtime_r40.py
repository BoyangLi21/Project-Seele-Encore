"""Read-only hash and rig-contract check for the installed R40 private runtime."""
from pathlib import Path
import hashlib,json
from check_runtime_r37 import check as foundation
ROOT=Path(__file__).resolve().parents[1]


def check():
    foundation();local=ROOT/'run/projectseele-local-maps';marker=json.loads((local/'revision_r40.json').read_text())
    assert marker['revision']==40 and marker['protocol']==44
    for name,digest in marker['runtime_sha256'].items():assert hashlib.sha256((local/name).read_bytes()).hexdigest()==digest,name
    shader=json.loads((local/'revision_r39.json').read_text())['shader'];assert hashlib.sha256((ROOT/'run/shaderpacks'/shader['filename']).read_bytes()).hexdigest()==shader['sha256']
    print('R40 private runtime and pinned shader ready; protocol 44.')


if __name__=='__main__':check()
