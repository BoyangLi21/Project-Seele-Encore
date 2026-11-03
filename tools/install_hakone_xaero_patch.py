"""Publish verified native Xaero pixels after their actual map installation."""
import argparse,json,shutil
from pathlib import Path
from install_r53_carrier_trays import stopped_world
from apply_s20_approved_semantic_repairs import atomic_replace
from xaero_cache_codec import Cache

def install(a):
    m=json.loads((a.stage/'manifest.json').read_text('utf8'));r=json.loads(a.installation.read_text('utf8'))
    if r.get('status')!='installed'or not r.get('changed_section_readback'):raise ValueError('Read-back map installation required')
    if m['errors']or not {Path(c).resolve()for c in m['candidates']}<={Path(c).resolve()for c in r['candidates']}:raise ValueError('Xaero input is not the installed map batch')
    root=Path(m['cache_root']).resolve();client=a.world.resolve().parent.parent
    if not root.is_relative_to(client/'xaero'/'world-map'):raise ValueError('Cache target is outside the actual client')
    a.out.mkdir(parents=True,exist_ok=False);written=[]
    with stopped_world(a.world):
        for name in m['files']:
            rel=Path(name)
            if rel.is_absolute()or'..'in rel.parts:raise ValueError('Unsafe cache path')
            if (root/rel).read_bytes()!=(a.stage/'before'/rel).read_bytes():raise ValueError('Client has updated map cache since staging: '+name)
            cache=Cache.open(a.stage/'after'/rel,leaf=rel.parts[0]=='cache_1')
            if cache.encode()!=cache.original:raise ValueError('Unverified Xaero file')
        try:
            for name in m['files']:
                rel=Path(name);backup=a.out/'original'/rel;backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/rel,backup)
                atomic_replace(root/rel,(a.stage/'after'/rel).read_bytes());written.append(rel)
            for rel in written:
                if (root/rel).read_bytes()!=(a.stage/'after'/rel).read_bytes():raise ValueError('Map cache readback mismatch')
        except BaseException:
            for rel in reversed(written):atomic_replace(root/rel,(a.out/'original'/rel).read_bytes())
            raise
    result=dict(status='installed',world=str(a.world),stage=str(a.stage),map_installation=str(a.installation),files=len(written),surface_pixels=m['pixels'],leaf_tiles=m['leaf_tiles'],all_zoom_tiles=m['all_zoom_tiles'],readback=True,waypoints_untouched=True,manual_reload_required=False,game_ui_verification=False)
    (a.out/'installation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('world','stage','installation','out'):p.add_argument('--'+n,type=Path,required=True)
    install(p.parse_args())
