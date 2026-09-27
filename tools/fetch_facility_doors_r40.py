"""Pinned upstream Macaw's Doors dependency, shared by client and server."""
from pathlib import Path
import hashlib,requests
ROOT=Path(__file__).resolve().parents[1]
NAME='mcw-doors-1.1.5-mc1.20.1forge.jar'
URL='https://cdn.modrinth.com/data/kNxa8z3e/versions/n8BlIUm3/'+NAME
SHA512='dc9180f0cfb049907be62a3d6429b7c469b4d7a44c1c5a8b9617aa673843f880c354febf22a22d4a995ea2ec9e5a75bb4628dc499bfb4a199b2b9e6a9ba39e26'

def ensure():
    target=ROOT/'.Codex/local-mods'/NAME
    if not target.exists():
        response=requests.get(URL,timeout=60);response.raise_for_status()
        if hashlib.sha512(response.content).hexdigest()!=SHA512:raise ValueError('Macaw archive hash mismatch')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(response.content)
    if hashlib.sha512(target.read_bytes()).hexdigest()!=SHA512:raise ValueError('Cached Macaw archive changed')
    return target

if __name__=='__main__':print(ensure())
