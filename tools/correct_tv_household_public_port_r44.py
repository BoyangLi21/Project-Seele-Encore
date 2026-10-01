"""Retire an uninstalled legacy scan endpoint inside the named private unit."""
from pathlib import Path
import argparse,json,shutil,hashlib
def main():
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists();a.output.mkdir()
 names=['forward.jsonl.gz','inverse.jsonl.gz','audit.json','architecture_components.json','road_authority.json','ecology_reservations.json','tv_landmark_components.json','new_district.json']
 for name in names:shutil.copy2(a.source/name,a.output/name)
 cases=json.loads((a.source/'native_cases.json').read_text('utf8'));revisions=[]
 for c in cases:
  if c['id'] not in ['r44/tv_misato/comfort17/stairs2','r44/tv_misato/comfort17/stairs2/return']:continue
  old=c['path'];path=old[::-1] if c['id'].endswith('/return') else list(old);assert path[-1]==[196.5,91,539.5];path[-1]=[191.5,91,539.5]
  c['path']=path[::-1] if c['id'].endswith('/return') else path;c['retired_before_path']=old;c['revision_reason']='Same whole stair/floor3 destination; correct common landing endpoint stays outside the private TV household genkan';c['native_passed']=False
  revisions.append(dict(id=c['id'],before=old,after=c['path']))
 assert len(revisions)==2
 (a.output/'native_cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),'utf8')
 (a.output/'case_geometry_revisions.json').write_text(json.dumps(dict(source=str(a.source.resolve()),geometry_unchanged=True,forward_sha256=hashlib.sha256((a.output/'forward.jsonl.gz').read_bytes()).hexdigest(),inverse_sha256=hashlib.sha256((a.output/'inverse.jsonl.gz').read_bytes()).hexdigest(),public_floor3_landing=[191.5,91,539.5],cases=revisions,interior_reviews=str((a.source/'actual_household_full_ceiling_nearclip_v3').resolve()),world_written=False),indent=2),'utf8')
 print('Two public landing ports corrected; exact geometry unchanged')
if __name__=='__main__':main()
