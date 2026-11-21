"""Install reviewed cell deltas into the actual closed singleplayer save."""
from pathlib import Path
import argparse,copy,gzip,json,msvcrt
import nbtlib
import regional_voxels as vox
import survey_r52_original_complex as survey
from query_blocks import iter_block_entities
from restore_r53_original_personnel_lifts import run as restore_lifts

DIM='projectseele:geofront'
STAGES=('oct16-static-repair','oct16-shell-repair','oct16-interface-repair')
def run(base,world):
 assert world.resolve()==(base/'client/saves/SEELE_R53_WORLD').resolve()
 # No region write is allowed while the actual save is open in Minecraft.
 lock=(world/'session.lock').open('r+b');msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);lock.close()
 manifest=json.loads((world/'personnel_lifts_r52.json').read_text('utf8'))
 if not any('horizontal_transfer'in l for l in manifest['lifts']):restore_lifts(base,world,True)
 proposed=json.loads(gzip.decompress((base/'personnel-access-proposal/EXACT_BLOCK_PROPOSAL.json.gz').read_bytes()))
 retired={tuple(r['pos']):r for r in proposed if r['pos'][1]>=-566 and r['owner'].startswith(('s20-command-rear-x12-z253-v4/','r25-east-command-gallery/'))}
 reports=[]
 for stage in STAGES:
  rows=json.loads(gzip.decompress((base/stage/'CANDIDATE/EXACT_DELTA.json.gz').read_bytes()))
  lo=tuple(min(r['pos'][k]for r in rows)for k in range(3));hi=tuple(max(r['pos'][k]for r in rows)for k in range(3))
  survey.WORLD=world;survey.DIM=DIM;a,palette=survey.measure(lo,hi)
  def state(p):return palette[int(a[p[1]-lo[1],p[2]-lo[2],p[0]-lo[0]])]
  tags=dict(iter_block_entities(world,DIM,lo,hi));pending=[];already=0;restored=0
  if stage=='oct16-shell-repair':
   for r in rows:
    p=tuple(r['pos']);t=tags.get(p)
    if p==(30,-384,327)and r['after']=='minecraft:air'and t is not None:
     assert state(p)=='minecraft:beacon'and str(t['id'])=='minecraft:beacon'
     r['before_nbt']=t.snbt()
  if stage=='oct16-interface-repair':
   bypos={tuple(r['pos']):r for r in rows}
   for source,destination in (((87,-552,370),(86,-552,365)),((87,-552,372),(86,-552,378))):
    t=tags.get(source)
    if t is not None:
     assert str(t['id'])=='projectseele:station_departure_board'
     bypos[source]['before_nbt']=t.snbt();moved=copy.deepcopy(t)
     for k,v in zip(('x','y','z'),destination):moved[k]=nbtlib.Int(v)
     bypos[destination]['after_nbt']=moved.snbt()
  for r in rows:
   p=tuple(r['pos']);s=state(p);t=tags.get(p);ts=t.snbt()if t is not None else None
   bt=r.get('before_nbt');at=r.get('after_nbt')
   if s==r['after']and ts==at:already+=1;continue
   original=retired.get(p)
   if original and s==original['before']and ts==original['before_nbt']:
    # An original upper hallway supersedes a removed NEW lobby decoration.
    if s!=r['before']or ts!=bt:restored+=1;continue
   assert s==r['before']and ts==bt,('Actual source changed',stage,p,s,ts)
   pending.append(r)
  vox.WORLD=world;vox.DIM=DIM;vox.OUT=base/'actual-oct16-install';painter=vox.Painter(vertical_bounds=(-1440,320))
  for r in pending:
   p=tuple(r['pos']);before=r.get('before_nbt');after=r.get('after_nbt')
   if r['before']==r['after']and before and after:painter.update_block_entity(p,r['before'],nbtlib.parse_nbt(before),nbtlib.parse_nbt(after),r.get('reason',stage))
   else:
    painter.exact((*p,*p),r['before'],r['after'],r.get('reason',stage))
    if after:painter.block_entities[p]=nbtlib.parse_nbt(after)
  if pending:painter.apply(stage)
  # Read the installed region bytes and complete typed device data.
  a,palette=survey.measure(lo,hi);tags=dict(iter_block_entities(world,DIM,lo,hi))
  for r in pending:
   p=tuple(r['pos']);assert state(p)==r['after'],p;t=tags.get(p);assert(t.snbt()if t is not None else None)==r.get('after_nbt'),p
  reports.append(dict(stage=stage,installed=len(pending),already_present=already,removed_new_lobby_superseded=restored,actual_readback=True))
 out=base/'actual-oct16-install';out.mkdir(exist_ok=True)
 (out/'INSTALLED.json').write_text(json.dumps(dict(world=str(world),stages=reports,players_entities_missions_traffic_files_written=False),ensure_ascii=False,indent=2),'utf8')
 print(json.dumps(reports,ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);a=p.parse_args();run(a.base,a.base/'client/saves/SEELE_R53_WORLD')
