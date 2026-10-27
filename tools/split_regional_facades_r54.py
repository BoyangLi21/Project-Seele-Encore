"""Exclude already-installed facade samples and emit the shared exact installer packet.
No world reads/writes; the installer rechecks live block states after normal shutdown.
"""
from pathlib import Path
import argparse,gzip,json,collections

def rows(file):
 if file.suffix=='.json':return json.loads(file.read_text('utf8'))
 with gzip.open(file,'rt',encoding='utf8')as f:return [json.loads(line)for line in f if line.strip()]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--sample',type=Path,action='append',required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--preserve-installed',type=Path,action='append',default=[]);a=ap.parse_args()
 full=rows(a.source/'forward.jsonl.gz');source={tuple(r['pos']):r for r in full};assert len(source)==len(full)
 samples={};sample_counts=[]
 for file in a.sample:
  rs=rows(file)
  for row in rs:
   q=tuple(row['pos']);assert q in source and all(row.get(k)==source[q].get(k)for k in('before','after','before_nbt','after_nbt')),('Sample differs from approved candidate',q)
   if q in samples:assert samples[q]==row
   samples[q]=row
  sample_counts.append(dict(path=str(file.resolve()),cells=len(rs)))
 protected=set(samples);preserved=[]
 for file in a.preserve_installed:
  installed={tuple(r['pos'])for r in rows(file)}
  overlap=set(source)&installed;additional=overlap-protected;protected.update(overlap)
  preserved.append(dict(path=str(file.resolve()),overlap_cells=len(overlap),additional_excluded_cells=len(additional),policy='Specific installed station/street art takes precedence; original candidate before states are never rewritten'))
 remaining=[dict(row,purpose=row['reason'])for q,row in source.items()if q not in protected];inverse=[]
 for row in remaining:
  r=row.copy();r['before'],r['after']=r['after'],r['before'];r['before_nbt'],r['after_nbt']=r.get('after_nbt'),r.get('before_nbt');inverse.append(r)
 a.out.mkdir(parents=True,exist_ok=True);meta=json.loads((a.source/'manifest.json').read_text('utf8'))
 manifest=dict(schema='projectseele.r54.regional-facades-remainder.v1',world=meta['world'],dimension=meta['dimension'],static_cells=len(remaining),source_cells=len(full),installed_sample_cells=len(samples),installed_samples=sample_counts,preserved_installed_art=preserved,buildings=len(set(r['owner']for r in remaining)),metadata_preconditions=[],world_tables=[],progress_files_written=[],world_written=False)
 for name,value in [('forwardPatch.json',remaining),('inversePatch.json',inverse),('positiveEditMask.json',[r['pos']for r in remaining]),('installation_manifest.json',manifest)]:
  (a.out/name).write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf8')
 for name,rs in [('forward',remaining),('inverse',inverse)]:
  with gzip.open(a.out/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
   for r in rs:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 print(json.dumps({k:manifest[k]for k in('source_cells','installed_sample_cells','static_cells','buildings')}))
if __name__=='__main__':main()
