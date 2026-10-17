"""Restore the two original upper shafts and extend their SAME native cars.

The recorded pre-edit blocks define the restoration. Native saved car location,
captured cage, floor availability and controller references come from the world
being installed, never from a second world's progress.
"""
from pathlib import Path
import argparse,copy,gzip,hashlib,io,json,math,msvcrt
import nbtlib
import regional_voxels as vox
import survey_r52_original_complex as survey
from query_blocks import iter_block_entities,read_box
from prepare_r53_personnel_access import new_floor
from apply_s20_approved_semantic_repairs import atomic_replace
from rebind_r53_personnel_installation import rebind

DIM='projectseele:geofront';CUT=-566;AIR='minecraft:air'
MAIN='s20-command-rear-x12-z253-v4';EAST='r25-east-command-gallery'
AXES={MAIN:((9,253),(-42,253)),EAST:((66,302),(58,366))}
def encoded(v):return (json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8')
def box(lo,hi):
 for y in range(lo[1],hi[1]+1):
  for z in range(lo[2],hi[2]+1):
   for x in range(lo[0],hi[0]+1):yield x,y,z
def tagpos(tag,at):
 tag=copy.deepcopy(tag)
 for k,v in zip(('x','y','z'),at):tag[k]=nbtlib.Int(v)
 return tag
def remap(tag,refs):
 tag=copy.deepcopy(tag)
 def visit(v):
  if isinstance(v,nbtlib.Compound):
   if 'controllerX' in v:
    keys=('controllerX','controllerY','controllerZ');old=tuple(int(v[k])for k in keys)
    if old in refs:
     for k,n in zip(keys,refs[old]):v[k]=type(v[k])(n)
   for child in v.values():visit(child)
  elif isinstance(v,nbtlib.List):
   for child in v:visit(child)
 visit(tag);return tag

def run(base,world,apply=False):
 manifest_path=world/'personnel_lifts_r52.json';bundle_path=world/'ROOT_ASSEMBLY_BUNDLE.json'
 cap_path=world/'dimensions/projectseele/geofront/data/capabilities.dat'
 manifest=json.loads(manifest_path.read_text('utf8'))
 assert not any('horizontal_transfer'in l for l in manifest['lifts']),'Already migrated'
 original=json.loads((base/'personnel-access-proposal/personnel_lifts_BEFORE.json').read_text('utf8'))
 proposal=json.loads(gzip.decompress((base/'personnel-access-proposal/EXACT_BLOCK_PROPOSAL.json.gz').read_bytes()))
 inverse=[r for r in proposal if r['pos'][1]>=CUT and r['owner'].startswith((MAIN+'/',EAST+'/'))]
 before_bypos={tuple(r['pos']):r for r in proposal}
 # All bounds derive from these two declared shafts and their recorded edits.
 points=[tuple(r['pos'])for r in inverse]+[(-48,-569,247),(96,-450,392)]
 lo=tuple(min(p[k]for p in points)for k in range(3));hi=tuple(max(p[k]for p in points)for k in range(3))
 survey.WORLD=world;survey.DIM=DIM;cells,names=survey.measure(lo,hi)
 def state(p):return names[int(cells[p[1]-lo[1],p[2]-lo[2],p[0]-lo[0]])]
 tags=dict(iter_block_entities(world,DIM,lo,hi));desired={};target_tags={};reasons={}
 def put(p,s,reason,tag=None):
  p=tuple(p);assert all(lo[k]<=p[k]<=hi[k]for k in range(3)),p
  desired[p]=s;target_tags[p]=tag;reasons[p]=reason
 skipped=0
 for r in inverse:
  p=tuple(r['pos']);s=state(p)
  if s not in (r['after'],r['before']) and not(s==AIR and 'door'in r['owner']):skipped+=1;continue
  put(p,r['before'],'restore_original_upper_shaft_and_original_approaches',None if r['before_nbt']is None else nbtlib.parse_nbt(r['before_nbt']))
 caps=nbtlib.load(cap_path);groups=caps['data']['movingelevators:elevator_groups'];car_report=[]
 for identity,(upper,lower)in AXES.items():
  lift=next(l for l in manifest['lifts']if l['id']==identity)
  old=next(l for l in original['lifts']if l['id']==identity)
  old_floors={f['cabin'][1]:copy.deepcopy(f)for f in old['floors']if f['cabin'][1]>CUT}
  if identity==MAIN:old_floors[-554]=new_floor(old_floors[-541],-554,'B1 交通接驳层')
  previous=copy.deepcopy(lift['floors']);lift['floors']=[copy.deepcopy(f)for f in previous if f['cabin'][1]<CUT]+list(old_floors.values());lift['floors'].sort(key=lambda f:f['cabin'][1])
  transfer=dict(upper_controller_axis=[upper[0]-3,upper[1]],lower_controller_axis=[lower[0]-3,lower[1]],transfer_y=CUT)
  lift['horizontal_transfer']=transfer
  role=next(v for v in manifest['main_lifts'].values()if v['lift_id']==identity)
  role['upper_axis']=dict(cabin=list(upper),controller=transfer['upper_controller_axis']);role['lower_axis']=dict(cabin=list(lower),controller=transfer['lower_controller_axis']);role['transfer_y']=CUT
  if identity==MAIN and -554 not in role['headquarters_floors']:role['headquarters_floors'].insert(0,-554)
  refs={tuple(f['controller']):tuple(next(n for n in lift['floors']if n['cabin'][1]==f['cabin'][1])['controller'])for f in previous}
  key=f'{lower[0]-3};{lower[1]}';g=groups[key]['group'];moving=bool(g['isMoving'])
  available=[int(y)for y,f in zip(g['floors'],g['floorData'])if bool(f['isCageAvailable'])]
  assert not available if moving else len(available)==1,(identity,available)
  saved_y=float(g['currentY'])if moving else available[0]
  # The old initial east car was part of the recorded architecture. Remove its
  # restoration before placing the world's actual car at its current stop.
  if identity==EAST:
   for p in box((upper[0]-2,-555,upper[1]-2),(upper[0]+2,-550,upper[1]+2)):put(p,AIR,'remove_initial_car_copy_before_current_car_migration')
  if not moving and saved_y>CUT:
   y=int(saved_y);dx,dz=upper[0]-lower[0],upper[1]-lower[1]
   source=list(box((lower[0]-2,y-1,lower[1]-2),(lower[0]+2,y+4,lower[1]+2)))
   assert any(str(tags.get(p,{}).get('id',''))=='movingelevators:display_tile'for p in source),'Actual stationary car missing'
   capture={p:(state(p),copy.deepcopy(tags.get(p)))for p in source}
   for p in source:
    prior=before_bypos.get(p);s=prior['before']if prior else AIR;t=None if prior is None or prior['before_nbt']is None else nbtlib.parse_nbt(prior['before_nbt'])
    put(p,s,'remove_actual_car_from_retired_upper_axis',t)
   for p,(s,t)in capture.items():
    q=p[0]+dx,p[1],p[2]+dz
    put(q,s,'same_native_stationary_car_at_original_upper_axis',None if t is None else remap(tagpos(t,q),refs))
  if moving:g['cage']=remap(g['cage'],refs)
  data={int(y):copy.deepcopy(f)for y,f in zip(g['floors'],g['floorData'])}
  if identity==MAIN:
   data[-554]=copy.deepcopy(data[-541]);data[-554]['name']=nbtlib.String('B1 交通接驳层');data[-554]['isCageAvailable']=nbtlib.Byte(0)
  ys=[f['cabin'][1]for f in lift['floors']];g['floors']=nbtlib.IntArray(ys);g['floorData']=nbtlib.List[nbtlib.Compound]([data[y]for y in ys])
  g['SeeleHorizontalTransferR53']=nbtlib.Compound({'Id':nbtlib.String(identity),'UpperX':nbtlib.Int(upper[0]-3),'UpperZ':nbtlib.Int(upper[1]),'LowerX':nbtlib.Int(lower[0]-3),'LowerZ':nbtlib.Int(lower[1]),'TransferY':nbtlib.Int(CUT),'Active':nbtlib.Byte(0),'Descending':nbtlib.Byte(0),'Started':nbtlib.Long(-1),'Duration':nbtlib.Int(1),'Fraction':nbtlib.Double(1 if saved_y<CUT else 0)})
  car_report.append(dict(lift=identity,moving=moving,saved_y=saved_y,same_car_preserved=True,upper_axis=upper,lower_axis=lower))
  # Extend only the retained old shaft beneath its lowest landing.
  for p in box((upper[0]-3,CUT-2,upper[1]-3),(upper[0]+3,-556,upper[1]+3)):
   inner=abs(p[0]-upper[0])<=2 and abs(p[2]-upper[1])<=2 and p[1]>=CUT-1
   put(p,AIR if inner else'projectseele:nerv_structural_panel','retained_original_shaft_lower_extension')
  # Axis-aligned native cabin sweeps a measured horizontal connector, with a
  # continuous floor and ceiling outside its captured 5x6x5 volume.
  distance=math.hypot(upper[0]-lower[0],upper[1]-lower[1]);inner=set();outer=set()
  for i in range(math.ceil(distance*4)+1):
   t=i/max(1,math.ceil(distance*4));x=round(upper[0]+(lower[0]-upper[0])*t);z=round(upper[1]+(lower[1]-upper[1])*t)
   for dx in range(-4,5):
    for dz in range(-4,5):
     outer.add((x+dx,z+dz))
     if abs(dx)<=3 and abs(dz)<=3:inner.add((x+dx,z+dz))
  for x,z in outer:
   for y in range(CUT-2,CUT+6):put((x,y,z),AIR if (x,z)in inner and CUT-1<=y<=CUT+4 else'projectseele:nerv_structural_panel','same_car_horizontal_transfer_enclosure')
  for x,z in inner:
   if (x+z)%8==0:put((x,CUT+5,z),'minecraft:sea_lantern','transfer_ceiling_continuous_lighting')
  # Join each vertical shaft through the horizontal roof/floor.
  for axis,top in ((upper,-556),(lower,CUT+4)):
   for p in box((axis[0]-2,CUT-1,axis[1]-2),(axis[0]+2,top,axis[1]+2)):put(p,AIR,'open_native_car_sweep_at_transfer_joint')
  for p in box((lower[0]-2,CUT-2,lower[1]-2),(lower[0]+2,CUT-2,lower[1]+2)):put(p,AIR,'lower_shaft_remains_open_below_transfer')
  # Actual original upper controllers, door cells and call keys are metadata
  # authority. Restore them even when the recorded retirement used no-op cells.
  for f in old_floors.values():
   y=f['cabin'][1];source=next(o for o in old['floors']if o['cabin'][1]==(-541 if identity==MAIN and y==-554 else y))
   source_tag=next(r['before_nbt']for r in proposal if tuple(r['pos'])==tuple(source['controller'])and r['before_nbt'])
   t=tagpos(nbtlib.parse_nbt(source_tag),f['controller']);t['data']['name']=nbtlib.String(f['label'])
   source_state=next(r['before']for r in proposal if tuple(r['pos'])==tuple(source['controller']))
   put(f['controller'],source_state,'original_floor_controller',t)
   for d in f['landing_doors']:put(d['pos'],d['closed_state'],'original_floor_landing_doors')
   for call in f['calls']:
    if call['kind']=='vanilla_button':put(call['position'],call['state'],'original_floor_call_key')
  if identity==MAIN:
   for p in box((7,-555,256),(13,-551,261)):
    put(p,'projectseele:nerv_floor_panel'if p[1]==-555 else AIR,'original_main_lift_B1_connection_to_11_554_260')
   f=old_floors[-554]
   for d in f['landing_doors']:put(d['pos'],d['closed_state'],'B1_native_landing_doors')
   for call in f['calls']:
    if call['kind']=='vanilla_button':put(call['position'],call['state'],'B1_native_call_key')
 rows=[];vox.WORLD=world;vox.DIM=DIM;vox.OUT=base/'original-lifts-transfer'/world.name;painter=vox.Painter(vertical_bounds=(-1440,320))
 for p,s in sorted(desired.items()):
  before=state(p);bt=tags.get(p);at=target_tags[p]
  bs=bt.snbt()if bt is not None else None;ats=at.snbt()if at is not None else None
  if before==s and bs==ats:continue
  if before==s and bt is not None and at is not None:painter.update_block_entity(p,s,bt,at,reasons[p])
  else:
   painter.exact((*p,*p),before,s,reasons[p])
   if at is not None:painter.block_entities[p]=at
  rows.append(dict(pos=p,before=before,after=s,before_nbt=bs,after_nbt=ats,reason=reasons[p]))
 out=vox.OUT;out.mkdir(parents=True,exist_ok=True)
 (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(encoded(rows),mtime=0));(out/'personnel_lifts_PROPOSAL.json').write_bytes(encoded(manifest))
 report=dict(world=str(world),changed_cells=len(rows),cars=car_report,unrelated_changed_cells_left_alone=skipped,native_gameplay_pending=True)
 if apply:
  lock=(world/'session.lock').open('r+b');msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  try:
   before_bundle=bundle_path.read_bytes();bundle=json.loads(before_bundle);bundle['personnel_lifts']['sha256']=hashlib.sha256(encoded(manifest)).hexdigest();bundle_raw=encoded(bundle)
   runtime_path,runtime_raw,_=rebind(world,before_bundle,bundle_raw)
   stream=io.BytesIO();caps.write(stream);cap_raw=gzip.compress(stream.getvalue(),mtime=0)
   painter.apply('original_upper_shafts_same_car_horizontal_extension',session_lock=lock)
   for path,raw in ((cap_path,cap_raw),(manifest_path,encoded(manifest)),(bundle_path,bundle_raw),(runtime_path,runtime_raw)):atomic_replace(path,raw);assert path.read_bytes()==raw
   for chunk in sorted({(r['pos'][0]//16,r['pos'][2]//16)for r in rows}):
    selected=[r for r in rows if (r['pos'][0]//16,r['pos'][2]//16)==chunk];a=(chunk[0]*16,lo[1],chunk[1]*16);b=(a[0]+15,hi[1],a[2]+15);back=read_box(world,DIM,a,b);btags=dict(iter_block_entities(world,DIM,a,b))
    for r in selected:
     pos=tuple(r['pos']);assert back[pos]==r['after'],pos;tag=btags.get(pos);assert (tag.snbt()if tag is not None else None)==r['after_nbt'],pos
   report['actual_readback']=True
  finally:lock.close()
  # Apply the same measured full-width landing repair when this migration
  # is used on another original save, not only on the current review world.
  from repair_r53_lift_entrances import run as repair_entrances
  repair_entrances(world,out/'fixed_entrances',apply=True)
 (out/('INSTALLED.json'if apply else'PLAN.json')).write_bytes(encoded(report));print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--world',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args();run(a.base,a.world,a.apply)
