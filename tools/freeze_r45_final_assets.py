"""Explicit selected asset overlay. Default plan; no Java, world, package, or source writes."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,shutil,sys

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def relative(name):
 if not isinstance(name,str) or not name.startswith(('assets/','data/')) or '\\' in name or ':' in name or any(p in ('','.','..') for p in name.split('/')):raise ValueError('Unsafe asset target '+str(name))
 return name
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def build_plan(recipe):
 m=read(recipe);selected={};inputs=[]
 if m.get('schema')!='projectseele.final-asset-selection.r45.v1':raise ValueError('Explicit final asset selection recipe required')
 # Current source resources always enter first. Private replacement is file-explicit.
 source=ROOT/'src/main/resources'
 for rootname in ('assets','data'):
  for p in (source/rootname).rglob('*'):
   if p.is_file():selected[p.relative_to(source).as_posix()]={'source':str(p.resolve()),'sha256':sha(p),'role':'CURRENT_SOURCE'}
 for row in m.get('private_base_files',[]):
  name=relative(row['target']);p=Path(row['source']);digest=sha(p)
  if digest!=row['sha256']:raise ValueError('Selected private asset changed '+name)
  if name.startswith(('assets/projectseele/lang/','assets/projectseele/lore/','data/')):
   if name.endswith('.json') and '/lang/' in name:
    old=read(p);new=read(source/name) if (source/name).is_file() else {};merged={**old,**new}
    selected[name]={'merged_json':merged,'role':'PRIVATE_LANGUAGE_PLUS_CURRENT_SOURCE_KEYS'}
   else:raise ValueError('Private pack cannot replace current lore/data '+name)
  else:
   if name in selected and not row.get('replace_current_source'):raise ValueError('Explicit replacement authorization missing '+name)
   selected[name]={'source':str(p.resolve()),'sha256':digest,'role':'EXPLICIT_PRIVATE_BASE'}
  inputs.append(row)
 for manifest in m.get('selected_overlays',[]):
  path=Path(manifest['source']);digest=sha(path)
  if digest!=manifest['sha256']:raise ValueError('Selected overlay manifest changed')
  for row in read(path)['files']:
   name=relative(row['target']);p=path.parent/name
   # Root-frozen portable contracts live at manifest/target; original author paths are provenance only.
   if not p.is_file():p=Path(row['source'])
   if sha(p)!=row['sha256']:raise ValueError('Frozen selected overlay bytes differ '+name)
   selected[name]={'source':str(p.resolve()),'sha256':row['sha256'],'role':'ROOT_SELECTED_OVERLAY'}
  inputs.append(manifest)
 if len(selected)!=len({p.lower() for p in selected}):raise ValueError('Case-colliding selected assets')
 return m,selected,inputs
def freeze(recipe,output):
 m,selected,inputs=build_plan(recipe);output=Path(output).resolve()
 allowed=(ROOT/'artifacts/rebuild_r45').resolve()
 if not output.is_relative_to(allowed) or output==allowed or output.exists():raise ValueError('Use a new explicit artifact output; no overwrite')
 output.mkdir(parents=True);files={}
 for name,row in selected.items():
  p=output/name;p.parent.mkdir(parents=True,exist_ok=True)
  if 'merged_json' in row:p.write_bytes((json.dumps(row['merged_json'],ensure_ascii=False,indent=2)+'\n').encode())
  else:shutil.copyfile(row['source'],p)
  files[name]=sha(p)
 receipt={'schema':'projectseele.final-assets-frozen.r45.v1','recipe_sha256':sha(recipe),'files':files,'source_inputs':inputs,'user_art_accepted':False,'Java_or_native_run':False,'world_written':False}
 (output/'ASSET_FROZEN.json').write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
 return receipt
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('plan','freeze'),nargs='?',default='plan');p.add_argument('--selection',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args()
 if a.action=='freeze':
  if not a.output:raise ValueError('Explicit new output required')
  result=freeze(a.selection,a.output)
 else:
  m,selected,inputs=build_plan(a.selection);result={'selected_assets':len(selected),'explicit_input_manifests':inputs,'state':'PLAN_NOT_FROZEN_NOT_BUILT','sources_untouched':True}
 print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
