"""Exact school delta after Tokyo install; preserve every installed Tokyo cell."""
from pathlib import Path
import argparse,gzip,json,shutil,math
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
def main():
 p=argparse.ArgumentParser();p.add_argument('school',type=Path);p.add_argument('tokyo',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists()
 rows=[json.loads(r) for r in gzip.open(a.school/'forward.jsonl.gz','rt',encoding='utf8')];tokyo={tuple(r['pos']):r for r in map(json.loads,gzip.open(a.tokyo/'forward.jsonl.gz','rt',encoding='utf8'))};w=MeasuredWorld(WORLD)
 lo=tuple(min(r['pos'][k] for r in rows)-3 for k in range(3));hi=tuple(max(r['pos'][k] for r in rows)+3 for k in range(3));w.box(lo,hi);w.load();tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)));final=[];preserved=[];held=[]
 for r in rows:
  q=tuple(r['pos']);before=w.block(q);tag=tags[q].snbt() if q in tags else None
  if q in tokyo:
   t=tokyo[q]
   if before!=t['after'] or tag!=t.get('after_nbt'):held.append(dict(pos=q,reason='Installed Tokyo cell changed since its full authoritative receipt',expected=t['after'],actual=before));continue
   preserved.append(dict(pos=q,actual=before,retired_school_after=r['after'],classification='Preserve exact installed Tokyo body/road/fullNBT; school shared interface adopts its real half-height footprint'));continue
  if before!=r['before'] or tag!=r.get('before_nbt'):
   held.append(dict(pos=q,reason='Non-Tokyo old state/fullNBT changed; no permission inferred',expected=r['before'],actual=before));continue
  if before!=r['after'] or tag!=r.get('after_nbt'):final.append(dict(r,before=before,before_nbt=tag,owner=r['owner'].replace('r44/tokyo_north/complete_new_streets','r44/tv_school_north/complete_new_streets')))
 a.output.mkdir(parents=True)
 for name,inverse in [('forward',False),('inverse',True)]:
  with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as out:
   for row in final:
    r=dict(row)
    if inverse:r['before'],r['after']=row['after'],row['before'];r['before_nbt'],r['after_nbt']=row['after_nbt'],row['before_nbt']
    out.write(json.dumps(r,ensure_ascii=False)+'\n')
 for name in ['new_district.json','native_cases.json','ecology_reservations.json','architecture_components.json','parcel_components.json','source_shape_candidates.json','school_entry_revision.json']:
  if (a.school/name).exists():shutil.copy2(a.school/name,a.output/name)
 authority=json.loads((a.school/'road_authority.json').read_text('utf8'));tcols={tuple(c['pos']):c for c in json.loads((a.tokyo/'road_authority.json').read_text('utf8'))['columns']};adopted=[]
 for c in authority['columns']:
  q=tuple(c['pos'])
  if q in tcols:
   old=c['native_feet'];c['native_feet']=tcols[q]['native_feet'];c['height2']=round(c['native_feet']*2);c['source_id']='retained installed Tokyo exact half-height street';adopted.append(dict(pos=q,old_school_feet=old,installed_feet=c['native_feet']))
 (a.output/'road_authority.json').write_text(json.dumps(authority,indent=2),'utf8')
 audit=json.loads((a.school/'audit.json').read_text('utf8'));audit.update(changed_cells=len(final),held=held,ready=False,native_passed=False,visual_passed=False);(a.output/'audit.json').write_text(json.dumps(audit,indent=2),'utf8')
 (a.output/'installed_tokyo_interface.json').write_text(json.dumps(dict(installed_tokyo=str(a.tokyo.resolve()),original_school=str(a.school.resolve()),producer=str(Path(__file__).resolve()),preserved_exact_cells=preserved,adopted_half_height_road_columns=adopted,held=held,world_written=False),indent=2),'utf8');print('School rebase',len(final),'cells','preserved installed Tokyo',len(preserved),'roadcolumns',len(adopted),'held',len(held))
if __name__=='__main__':main()
