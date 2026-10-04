"""Exact, reversible archive niche behind the measured highest commander seat."""
from pathlib import Path
import json,hashlib,argparse
import nbtlib
import regional_voxels as v
from query_blocks import read_box,iter_block_entities
from release_combat_r36 import guard
ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW';OUT=ROOT/'artifacts/rebuild_r45/dead_sea_install'
def main(apply,historical=False):
 if apply:
  raise RuntimeError('Current-world niche writes are retired. Historical mode is read-only evidence; Root must use the complete chamber forward/inverse instead.')
 if not historical:
  raise RuntimeError('The chair-back niche installer is retired after the explicit highest-Tree hidden-chamber request. Use prepare_dead_sea_chamber_r45.py for the measured complete chamber proposal; Root alone installs its exact inverse. --historical-niche-r45 is historical evidence only and must not be replayed into the current chamber.')
 guard();OUT.mkdir(parents=True,exist_ok=True)
 b=read_box(WORLD,v.DIM,(28,-330,337),(32,-326,345));tags=dict(iter_block_entities(WORLD,v.DIM,(28,-330,337),(32,-326,345)))
 assert b[30,-329,339]=='projectseele:command_seat_back[facing=north,half=lower]'
 assert b[30,-328,339]=='projectseele:command_seat_back[facing=north,half=upper]'
 assert b[30,-330,343] not in v.AIR
 for y in [-329,-328]:assert b[30,y,340]=='minecraft:white_concrete'and(30,y,340)not in tags and b[30,y,341]in v.AIR
 changes=[dict(position=[30,y,340],before=b[30,y,340],after='projectseele:dead_sea_archive[facing=north]'if y==-329 else'minecraft:air',owner='r45/commander_archive_niche')for y in[-329,-328]]
 changes.extend(dict(position=[30,y,341],before=b[30,y,341],after='minecraft:white_concrete',owner='r45/opaque_archive_recess_backing')for y in[-329,-328])
 (OUT/'operations.json').write_text(json.dumps(changes,indent=2),'utf8');(OUT/'inverse.json').write_text(json.dumps([dict(r,before=r['after'],after=r['before'])for r in changes],indent=2),'utf8')
 report=dict(world=str(WORLD),actual_commander_seat=[30,-329,338],backrest=[30,-329,339],archive=[30,-329,340],niche=[30,-329,340,30,-328,341],original_chair_and_full_NBT_retained=True,owning_room='Highest commander reception; stand recessed behind the seat within original wall, rear wall sealed',operations=len(changes),installed=False,native_visual=False)
 if apply:
  assert not list(OUT.glob('archive/applied_*/receipt.json'))
  protected={p.relative_to(WORLD).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in WORLD.rglob('*')if p.is_file()and any(k in p.relative_to(WORLD).parts for k in['data','playerdata','entities','stats','advancements','mtr'])}
  v.WORLD=WORLD;v.OUT=OUT;p=v.Painter()
  for r in changes:q=tuple(r['position']);p.match((*q,*q),r['before'],r['after'],r['owner'])
  p.block_entities[30,-329,340]=nbtlib.Compound(dict(id=nbtlib.String('projectseele:dead_sea_archive'),x=nbtlib.Int(30),y=nbtlib.Int(-329),z=nbtlib.Int(340)))
  report['receipt']=p.apply('archive');assert all(hashlib.sha256((WORLD/name).read_bytes()).hexdigest()==sha for name,sha in protected.items())
  report.update(installed=True,protected_progress_files=len(protected))
 (OUT/'installation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('Archive candidate:',report['installed'],'cells',len(changes),'visual pending')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--historical-niche-r45',action='store_true');a=p.parse_args();main(a.apply,a.historical_niche_r45)
