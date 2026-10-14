"""Classify current full-stroke mesh cells against Root's proposed final pits.

Read-only WORLD through query_blocks; proposed cells are evidence, not an
excavation/apply mask. No old notch coordinates or stale source SHA are used.
"""
from pathlib import Path
import collections,gzip,hashlib,json,math
import numpy as np
from query_blocks import read_box,iter_block_entities,AIR

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.Codex/map_complete_20261013/route_audit/lower_current'
WORLD=Path('D:/eva/artifacts/map_complete_20261013/WORLD')
DIM='projectseele:geofront'
STRUCT='projectseele:nerv_structural_panel';SHAFT='projectseele:nerv_shaft_panel'
LO=(-35,-1136,307);HI=(96,-1062,350)

def write(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8')
def cells(lo,hi):
 for y in range(lo[1],hi[1]+1):
  for z in range(lo[2],hi[2]+1):
   for x in range(lo[0],hi[0]+1):yield(x,y,z)

def main():
 contract=json.loads((OUT/'CURRENT_FACTORY_CONTRACT.json').read_text('utf8'))
 resource=ROOT/'src/main/resources/assets/projectseele/mesh/cage_lower_telescopes_r52.json'
 assert hashlib.sha256(resource.read_bytes()).hexdigest()==contract['source_sha']=='90c7cccabb080367a130aa9155d1b922375dca7a3aa6b9dac87b67729aea82ac'
 before=read_box(WORLD,DIM,LO,HI);assert len(before)==(HI[0]-LO[0]+1)*(HI[1]-LO[1]+1)*(HI[2]-LO[2]+1)
 tags={p:t.snbt()for p,t in iter_block_entities(WORLD,DIM,LO,HI)}
 after=dict(before);owners={};wet=set();variants=(72,30,-12)
 def fill(lo,hi,value,owner):
  for p in cells(lo,hi):
   assert p in before,p
   after[p]=value;owners.setdefault(p,set()).add(owner)
 for v,cx in enumerate(variants):
  fill((cx-18,-1135,310),(cx+18,-1064,346),SHAFT,f'bay{v}/outer_pit')
  fill((cx-16,-1132,312),(cx+16,-1064,344),'minecraft:air',f'bay{v}/dry_inner')
  fill((cx-21,-1069,310),(cx+21,-1064,346),'minecraft:air',f'bay{v}/upper_flare')
  for z,Z in((309,311),(345,347)):
   fill((cx-21,-1071,z),(cx+21,-1070,Z),STRUCT,f'bay{v}/hatch_bearing_crossbeam')
   fill((cx-21,-1065,z),(cx+21,-1064,Z),'minecraft:air',f'bay{v}/hatch_outer_work_band')
  for row in contract['contacts']:
   if row['variant']!=v or row['owner']!='hatch_fixed_bearing':continue
   p=row['world'];x,z=math.floor(p[0]),math.floor(p[2]);assert abs(p[1]+1065)<1e-8
   fill((x,-1069,z),(x,-1066,z),STRUCT,f'bay{v}/hatch_original_8_bearing_columns')
  wet.update(cells((cx-16,-1063,312),(cx+16,-1063,344)))
 assert all(after[p]==before[p]for p in before if p[1]>=-1063),'Original wet floor must remain unchanged until native draining'
 shapes=json.loads((WORLD/'native_collision_shapes.json').read_text('utf8'))
 unknown=[];noncube=[];hits=[];contacts=[]
 lower=json.loads((OUT/'LOWER_FULL_STROKE_CUBE_OCCUPANCY.json').read_text('utf8'))
 hatch=json.loads((OUT/'HATCH_YAW0_FULL_STROKE_CUBE_OCCUPANCY.json').read_text('utf8'))
 for source,rows in [('lower',lower),('hatch_yaw0_before_column_port_fix',hatch)]:
  for v,cx in enumerate(variants):
   for row in rows:
    x,y,z=row['canonical_cell'];p=(x+cx,y,z)
    if p not in before:unknown.append(dict(source=source,variant=v,pos=p,reason='outside explicit read envelope'));continue
    s=after[p]
    if s in AIR:continue
    b=shapes.get(s)
    if b is None:unknown.append(dict(source=source,variant=v,pos=p,state=s,reason='missing actual native shape'));continue
    if not b:continue
    if b!=[[0.0,0.0,0.0,1.0,1.0,1.0]]:
     noncube.append(dict(source=source,variant=v,pos=p,state=s,native_boxes=b,potential_parts=row['hits']));continue
    actual=[r for r in row['hits']if r['penetrates_cell_deflated_2e_7']]
    record=dict(source=source,variant=v,position=p,before=before[p],proposed=s,pit_owners=sorted(owners.get(p,set())),
     actual_parts=actual,rounding_contact_only=[r for r in row['hits']if not r['penetrates_cell_deflated_2e_7']],
     has_BE=p in tags,block_entity=tags.get(p),wet_floor_interlock=p in wet)
    if not actual:contacts.append(record);continue
    record['classification']='wet_floor_native_drain_and_hatch_state_required'if p in wet else'outside_original_pit_mask_requires_Root_owned_recess'if p not in owners else'pit_solid_requires_measured_recess'
    if y>=-1063 and p not in wet:record['classification']='permanent_wet_floor_or_outer_bearing_conflict_do_not_blindly_cut'
    hits.append(record)
 support=[]
 for r in contract['contacts']:
  p=r['world'];cell=(math.floor(p[0]),round(p[1])-1,math.floor(p[2]));s=after.get(cell);actual=shapes.get(s,[]);margins=[]
  for b in actual:
   margins.append(dict(x_min=p[0]-cell[0]-b[0],x_max=cell[0]+b[3]-p[0],z_min=p[2]-cell[2]-b[2],z_max=cell[2]+b[5]-p[2],top_error=cell[1]+b[4]-p[1]))
  threshold=.15 if r['owner']=='lower_permanent_column_pad'else 0
  passed=any(min(m[k]for k in('x_min','x_max','z_min','z_max'))>=threshold and abs(m['top_error'])<.002 for m in margins)
  below=(cell[0],cell[1]-1,cell[2]);neighbours=[(cell[0]+dx,cell[1],cell[2]+dz)for dx,dz in((1,0),(-1,0),(0,1),(0,-1))]
  support.append(dict(**r,cell=cell,actual_before=before.get(cell),proposed=s,actual_native_box_margins=margins,
   point_bearing_pass=passed,required_horizontal_margin=threshold,permanent_not_native_open_floor=cell not in wet,
   below_state=after.get(below),adjacent_static_cells=[dict(position=q,state=after.get(q))for q in neighbours if after.get(q)not in AIR and q not in wet],
   contact_is_not_full_structural_load_certification=True))
 source_holes={tuple(r['position'])for r in hits if r['source']=='lower'and r['position'][1]<=-1064}
 duplicate_models=collections.Counter(tuple(r['position'])for r in hits)
 write('CURRENT_PIT_FULL_STROKE_HITS.json',dict(world_written=False,source_sha=contract['source_sha'],hatch_source_sha=contract['hatch_source_sha'],
  authorization='Measured conflict cells only; Root decides exact excavation and support redesign',proposed_layout_source='Root final -384 shift of prepare_complete_carrier_pits finite dimensions, no old144 notches',
  records=hits,rounding_only_contacts=contacts,unknown_native_shapes=unknown,non_full_cube_native_shapes=noncube))
 write('CURRENT_36_BEARING_CONTACTS.json',dict(world_written=False,contacts=support,all_point_checks=all(r['point_bearing_pass']for r in support),
  all_bearing_cells_outside_open_floor=all(r['permanent_not_native_open_floor']for r in support)))
 write('LOWER_RECESS_INTERFACE.json',dict(world_written=False,source_sha=contract['source_sha'],canonical_machine_root=dict(position=[.5,-1062.96,328.5],quaternion=[0,1,0,0]),
  variants=[dict(variant=v,root=[cx+.5,-1062.96,328.5],cells=[r for r in hits if r['source']=='lower'and r['variant']==v and r['position'][1]<=-1064])for v,cx in enumerate(variants)],
  unique_required_lower_cells=len(source_holes),already_open_cells_are_not_written=True,old144_source_not_used=True))
 palette=sorted(set(before.values())|set(after.values()));idx={s:i for i,s in enumerate(palette)};shape=(HI[1]-LO[1]+1,HI[2]-LO[2]+1,HI[0]-LO[0]+1);old=np.zeros(shape,np.uint16);new=np.zeros(shape,np.uint16);mask=np.zeros(shape,bool)
 for(x,y,z),s in before.items():old[y-LO[1],z-LO[2],x-LO[0]]=idx[s];new[y-LO[1],z-LO[2],x-LO[0]]=idx[after[x,y,z]];mask[y-LO[1],z-LO[2],x-LO[0]]=(x,y,z)in owners
 np.savez_compressed(OUT/'CURRENT_AND_PROPOSED_PIT_NO_NOTCHES.npz',origin=LO,palette=palette,before=old,proposed=new,root_proposed_owned=mask)
 report=dict(world_written=False,game_started=False,scope_y=contract['voxel_y_band'],current_before_cells=len(before),proposed_owned=len(owners),
  measured_lower_hits=len([r for r in hits if r['source']=='lower']),unique_lower_recess_cells=len(source_holes),
  classifications=dict(collections.Counter(r['source']+'/'+r['classification']for r in hits)),unknown_shapes=len(unknown),partial_native_boxes=len(noncube),
  actual_bearing_points=len(support),all_point_bearings=all(r['point_bearing_pass']for r in support),source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
  source_resource_sha256=contract['source_sha'],no_notch_or_bearing_applied=True)
 write('PIT_MEASUREMENT_REPORT.json',report);print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
