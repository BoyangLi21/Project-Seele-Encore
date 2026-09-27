"""Capture and archive only native photos whose actual camera and scene were verified."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,time
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R42_REVIEW';ART=ROOT/'artifacts/rebuild_r42/photos'


def collect(group,shaders,began):
    itinerary=json.loads((ART/f'{group}_itinerary.json').read_text('utf8'))
    proof=json.loads((WORLD/'verified_photo_positions_r42.json').read_text('utf8'))
    expected={r['file'] for r in itinerary};assert expected=={r['file'] for r in proof},('Incomplete photo run',group,len(proof),len(expected))
    folder=ART/f'verified_{group}_{"shader" if shaders else "clear"}';folder.mkdir(exist_ok=True)
    for row in proof:
        assert row['position_error_metres']<.1 and row['dimension']=='projectseele:geofront'
        p=ROOT/'run/screenshots'/row['file'];assert p.stat().st_mtime>=began,('Stale screenshot',p)
        shutil.copy2(p,folder/p.name);row['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    (folder/'positions.json').write_text(json.dumps(proof,indent=2),'utf8')
    (folder/'itinerary.json').write_text(json.dumps(itinerary,indent=2),'utf8')
    (folder/'render_configuration.json').write_text(json.dumps(dict(shaders=shaders,camera_position_verified=True,required_visible_sections_compiled=True,files=len(proof)),indent=2),'utf8')
    print('Archived',len(proof),'verified native photos',folder,flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--group',choices=['all','interiors','stations','entrances'],default='interiors')
    p.add_argument('--shaders',action='store_true');p.add_argument('--collect-since',type=float);args=p.parse_args()
    if args.collect_since is not None:collect(args.group,args.shaders,args.collect_since);return
    guard();subprocess.run([sys.executable,'tools/prepare_photos_r42.py','--group',args.group],cwd=ROOT,check=True)
    cfg=ROOT/'run/config/oculus.properties';original=cfg.read_bytes();began=time.time()
    text=original.decode('utf8');text=text.replace('enableShaders=false','enableShaders=true') if args.shaders else text.replace('enableShaders=true','enableShaders=false')
    cfg.write_text(text,'utf8')
    try:
        with (ART/f'{args.group}_{"shader" if args.shaders else "clear"}.log').open('w',encoding='utf8') as f:
            subprocess.run([sys.executable,'tools/launch_rendered_client_r17.py','--prepared-file',f'.Codex/client-r42-{args.group}-photos.json'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
        collect(args.group,args.shaders,began)
    finally:cfg.write_bytes(original)


if __name__=='__main__':main()
