"""Uninstalled whole school genkan revision on the measured whole-parcel ghost."""
from pathlib import Path
import argparse,json,gzip,shutil
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR
from regional_voxels import canonical_state
from tv_landmark_architecture_r44 import school_entrance
ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
def main():
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists()
 d=json.loads((a.source/'new_district.json').read_text('utf8'));b=next(b for b in d['buildings'] if b['kind']=='tv_school');rows=[json.loads(r) for r in gzip.open(a.source/'forward.jsonl.gz','rt',encoding='utf8')];target={tuple(r['pos']):r for r in rows};w=MeasuredWorld(WORLD);x,z,X,Z=b['bounds'];w.box((x-8,b['floor']-8,z-8),(X+8,b['roof']+8,Z+20));w.load();held=[]
 def state(q):return target[q]['after'] if q in target else w.block(q)
 def put(q,s,owner,reason):
  q=tuple(q);before=w.block(q);s=canonical_state(s)
  if before is None or (q not in target and before.split('[')[0] not in AIR|{'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:grass','minecraft:tall_grass','minecraft:smooth_stone'}):held.append(dict(pos=q,before=before,reason=reason));return
  if s==before:target.pop(q,None)
  else:target[q]=dict(pos=q,before=before,after=s,before_nbt=None,after_nbt=None,owner=owner,reason=reason)
 c=school_entrance(b,state,put);d['rooms'].extend(c['rooms']);a.output.mkdir(parents=True)
 for name,inverse in [('forward',False),('inverse',True)]:
  with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as out:
   for q in sorted(target):
    r=dict(target[q])
    if inverse:r['before'],r['after']=r['after'],r['before'];r['before_nbt'],r['after_nbt']=r.get('after_nbt'),r.get('before_nbt')
    out.write(json.dumps(r,ensure_ascii=False)+'\n')
 cases=json.loads((a.source/'native_cases.json').read_text('utf8'));retired=[]
 for case in cases:
  if case['id'].startswith(b['id']+'/public_entry'):
   old=case['path'];path=[[b['door'][0]+.5,b['floor']+1,b['actual_street_handoff'][2]+.5],[b['door'][0]+.5,b['floor']+1,b['bounds'][3]-1.5]]
   case['path']=path[::-1] if case['id'].endswith('/return') else path;case['door']=b['door'];retired.append(dict(id=case['id'],before=old,after=case['path']))
 cases.extend(c['cases']);(a.output/'native_cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),'utf8');(a.output/'new_district.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')
 for name in ['road_authority.json','architecture_components.json','source_shape_candidates.json']:shutil.copy2(a.source/name,a.output/name)
 parcels=json.loads((a.source/'parcel_components.json').read_text('utf8'));kept=[];fixture_retirements=[]
 for col in parcels['full_court_columns']:
  xx,zz=col['pos'];st=state((xx,b['floor']+1,zz))
  if col['owner']==b['id'] and b['school_genkan_bounds'][0]<=xx<=b['school_genkan_bounds'][3] and b['bounds'][3]<zz<=b['school_genkan_bounds'][5] and st not in AIR and '_door[' not in st:
   fixture_retirements.append(dict(column=col,classification='Former exterior court replaced by explicit full school vestibule wall / shoe rack; occupied fixture is not a walkable floor goal',state=st))
  else:kept.append(col)
 parcels['full_court_columns']=kept;parcels['new_entrance_fixture_retirements']=fixture_retirements;(a.output/'parcel_components.json').write_text(json.dumps(parcels,indent=2),'utf8')
 protection=json.loads((a.source/'ecology_reservations.json').read_text('utf8'));protection['reservations'].append(c['protection']);(a.output/'ecology_reservations.json').write_text(json.dumps(protection,indent=2),'utf8')
 audit=json.loads((a.source/'audit.json').read_text('utf8'));audit.update(changed_cells=len(target),held=held,ready=False,native_passed=False,visual_passed=False);(a.output/'audit.json').write_text(json.dumps(audit,indent=2),'utf8')
 (a.output/'school_entry_revision.json').write_text(json.dumps(dict(source=str(a.source.resolve()),producer=str(Path(__file__).resolve()),component=c,retired_paths=retired,fixture_retirements=fixture_retirements,world_written=False),indent=2),'utf8');print('Whole school formal genkan',len(target),'cells','held',len(held),'double-door cases',len(c['cases']))
if __name__=='__main__':main()
