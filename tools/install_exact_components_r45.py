"""Root-only reversible installer for individually measured complete components."""
from pathlib import Path
import argparse,copy,gzip,hashlib,json
import nbtlib
import regional_voxels as v
from query_blocks import iter_block_entities
from measure_world_r40 import MeasuredWorld
from release_combat_r36 import guard
ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'
def main():
 a=argparse.ArgumentParser();a.add_argument('--candidate',type=Path,required=True);a.add_argument('--name',required=True);a.add_argument('--apply',action='store_true');args=a.parse_args();guard()
 candidate=args.candidate.resolve();allowed=(ROOT/'artifacts/rebuild_r45').resolve();assert allowed in candidate.parents
 out=allowed/'component_installations'/args.name;assert not list(out.glob('applied_*/receipt.json')),'Applied epoch is immutable'
 with gzip.open(candidate/'forward.jsonl.gz','rt',encoding='utf8')as f:rows=[json.loads(x)for x in f]
 with gzip.open(candidate/'inverse.jsonl.gz','rt',encoding='utf8')as f:inverse=[json.loads(x)for x in f]
 assert len(rows)==len(inverse)>0
 inv={tuple(r['pos']):r for r in inverse};assert len(inv)==len(rows)
 w=MeasuredWorld(WORLD)
 for r in rows:w.around(r['pos'],0)
 w.load();chunks={(r['pos'][0]//16,r['pos'][2]//16)for r in rows};lo=tuple(min(r['pos'][i]for r in rows)for i in range(3));hi=tuple(max(r['pos'][i]for r in rows)for i in range(3))
 tags=dict(iter_block_entities(WORLD,v.DIM,lo,hi,selected_chunks=chunks));conflicts=[]
 for r in rows:
  q=tuple(r['pos']);back=inv[q];assert back['before']==r['after']and back['after']==r['before']and back.get('before_nbt')==r.get('after_nbt')and back.get('after_nbt')==r.get('before_nbt')
  actual=tags.get(q);snbt=None if actual is None else actual.snbt();expected=r.get('before_nbt');match=snbt==expected or actual is not None and expected is not None and actual==nbtlib.parse_nbt(expected)
  if w.block(q)!=r['before']or not match:conflicts.append(dict(pos=q,expected_state=r['before'],state=w.block(q),nbt_equal=match))
 out.mkdir(parents=True,exist_ok=True);report=dict(candidate=str(candidate),world=str(WORLD),cells=len(rows),conflicts=conflicts,installed=False,native_verified=False,visual_reviewed=False)
 (out/'preflight.json').write_text(json.dumps(report,indent=2),'utf8');assert not conflicts,('Fresh candidate conflicts',conflicts[:8])
 if args.apply:
  progress={p.relative_to(WORLD).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in WORLD.rglob('*')if p.is_file()and any(k in p.relative_to(WORLD).parts for k in ['data','playerdata','entities','stats','advancements','mtr'])}
  v.WORLD=WORLD;v.OUT=out;p=v.Painter()
  for r in rows:
   q=tuple(r['pos']);after=r.get('after_nbt');tag=nbtlib.parse_nbt(after)if after else None
   if r['before']==r['after']:
    assert tag is not None and q in tags;p.update_block_entity(q,r['before'],tags[q],tag,r['owner'])
   else:
    p.match((*q,*q),r['before'],r['after'],r['owner'])
    if tag is not None:p.block_entities[q]=tag
  report['receipt']=p.apply('component')
  assert all(hashlib.sha256((WORLD/name).read_bytes()).hexdigest()==sha for name,sha in progress.items()),'Runtime identities/progress files modified'
  after=dict(iter_block_entities(WORLD,v.DIM,lo,hi,selected_chunks=chunks));changed={tuple(r['pos'])for r in rows};assert all(q in after and after[q]==t for q,t in tags.items()if q not in changed),'Unrelated complete block entity data changed'
  report.update(installed=True,progress_files_unchanged=len(progress),unrelated_full_block_entities_preserved=sum(q not in changed for q in tags))
 (out/'installation.json').write_text(json.dumps(report,indent=2),'utf8');print(args.name,'installed',report['installed'],'cells',len(rows),'native/visual pending')
if __name__=='__main__':main()
