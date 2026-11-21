"""Prepare the two original shaft extensions and moved R53 landing additions.

Reads one current Root world; exports exact single-composed cells and ownership.
No world writer, capability mutation, readiness change or third elevator.
"""
from pathlib import Path
import argparse,collections,gzip,json
import numpy as np
import nbtlib
from query_blocks import AIR,read_box,iter_block_entities
from prepare_complete_main_lift_civil import STRUCT,FLOOR,WALL,NATURAL,points,sha,save,need

ROOT=Path(__file__).resolve().parents[1]
DIM='projectseele:geofront'
BASE=Path('D:/eva/artifacts/map_complete_20261013')
DY=-384
PIECES=[
 ('main_hangar_complete_added_gallery',(6,-604,257),(12,-599,287)),
 ('main_hangar_original_explicit_opening',(9,-603,288),(11,-600,288)),
 ('main_terminal_added_foyer',(6,-847,257),(14,-843,260)),
 ('east_hangar_native_threshold_and_outer_frame',(63,-604,306),(69,-600,306)),
 ('east_hangar_original_call_post',(64,-604,308),(65,-599,308)),
]
MAINSHAFT=((6,-1232,250),(12,-497,256))
EASTSHAFT=((63,-989,299),(69,-452,305))
SOURCE_MAINSHAFT=((6,-848,250),(12,-497,256))
SOURCE_EASTSHAFT=((63,-605,299),(69,-452,305))

def shifted(p,dy=DY):return(p[0],p[1]+dy,p[2])
def inside(p,box):return all(box[0][i]<=p[i]<=box[1][i]for i in range(3))
def natural(p):return'minecraft:deepslate[axis=y]'if p[1]<-672 else'minecraft:stone'

class Plan:
 def __init__(self,world):
  self.world=world;self.before={};self.tags={};self.after={};self.owner={};self.holds=[];self.read_boxes=[]
  m=np.load(BASE/'hangar_component/owner_mask.npz');self.hm=m['move'];self.ho=m['origin']
  self.terminal=tuple(map(tuple,json.loads((BASE/'terminal_move/complete_terminal_translation/PLAN.json').read_text('utf8'))['destination_envelope']))
 def read(self,lo,hi):
  self.before.update(read_box(self.world,DIM,lo,hi));self.tags.update(iter_block_entities(self.world,DIM,lo,hi));self.read_boxes.append([lo,hi])
 def old(self,p):
  p=tuple(p)
  if p not in self.before:self.read(p,p)
  need(p in self.before,'Missing current precondition '+str(p));return self.before[p]
 def core(self,p):
  if inside(p,self.terminal):return'terminal'
  source=(60-p[0],p[1]+236,88-p[2]);i=(source[1]-self.ho[1],source[2]-self.ho[2],source[0]-self.ho[0])
  if all(0<=i[k]<self.hm.shape[k]for k in range(3))and self.hm[i]:return'hangar'
  return None
 def put(self,p,value,owner):self.old(p);self.after[tuple(p)]=value;self.owner[tuple(p)]=owner
 def box(self,lo,hi,value,owner):
  for p in points(lo,hi):self.put(p,value,owner)
 def final(self,p):
  p=tuple(p)
  if p in self.after:return self.after[p]
  source=shifted(p,-DY)
  if self.core(source):return self.old(source)
  if self.core(p):return natural(p)
  return self.old(p)

def main(args):
 out=args.out.resolve();world=args.world.resolve();metadata=args.metadata.resolve()
 need(out.is_relative_to((ROOT/'.Codex').resolve())and not out.exists(),'Fresh .Codex output required');out.mkdir(parents=True)
 m=json.loads((metadata/'personnel_lifts_CANDIDATE_NOT_INSTALLED.json').read_text('utf8'))
 need(m['epoch']==53 and not m['ready'],'Exact depth draft required')
 need(m['main_lifts']['command_rear']['hangar_floor']==-987 and m['main_lifts']['command_rear']['terminal_floor']==-1230,'Final Root depth differs')
 c=Plan(world)
 for box in(MAINSHAFT,EASTSHAFT):c.read(*box)
 for _,lo,hi in PIECES:c.read(lo,hi);c.read(shifted(lo),shifted(hi))
 # Complete endpoint context: original owned floor/columns move with Root.
 for lo,hi in[((6,-605,287),(13,-599,293)),((62,-605,306),(70,-599,311)),((7,-848,259),(15,-842,264))]:c.read(lo,hi)
 be=json.loads((metadata/'NATIVE_BE_PATCH.json').read_text('utf8'))['operations']
 ours=[r for r in be if r['role']=='floor_controller'and r['lift_id']in(m['main_lifts']['command_rear']['lift_id'],m['main_lifts']['east_gallery']['lift_id'])]
 need(len(ours)==3,'Three original main floor controllers required')
 controlled={tuple(r['source'])for r in ours}|{tuple(r['target'])for r in ours}
 # Every unrelated shape in the extension must either be natural foundation
 # or have explicit Root core retirement provenance; no broad block whitelist.
 shaft_changes=[]
 for role,lo,hi,old_bottom in [('main',(6,-1232,250),(12,-848,256),-848),('east',(63,-989,299),(69,-605,305),-605)]:
  for p in points(lo,hi):
   x,y,z=p;boundary=x in(lo[0],hi[0])or z in(lo[2],hi[2])or y==lo[1]
   old=c.old(p)
   retired_bottom_plane=old=='minecraft:bedrock'and y==-960
   if old not in NATURAL and not retired_bottom_plane and not c.core(p)and y!=old_bottom and p not in controlled:
    c.holds.append(dict(kind='foreign_extension_cell',pos=p,state=old))
   c.put(p,STRUCT if boundary else'minecraft:air',role+'_continuous_lower_shaft')
 # Seal the two old main hangar/Terminal south openings inside the retained
 # shaft envelope. Outside halls are separately retired, never left dual.
 for x,z,ys in[(9,253,(-846,-603)),(66,302,(-603,))]:
  for y in ys:
   c.box((x-2,y-1,z+3),(x+2,y+2,z+3),STRUCT,'retire_old_stop_shaft_wall')
   c.put((x-3,y,z),STRUCT,'retire_old_native_floor_controller')
 # Added halls include every unchanged/air cell in their finite volume, not
 # just the 18317 old diff rows. Root and this candidate can deduplicate exact
 # identical source retirement/target placement in shared original ownership.
 transfers=[]
 for name,lo,hi in PIECES:
  for p in points(lo,hi):
   q=shifted(p);s=c.old(p)
   if p in c.tags and p not in controlled:c.holds.append(dict(kind='foreign_BE_in_added_hall',pos=p,nbt=c.tags[p].snbt()))
   c.put(p,natural(p),'retire_'+name);c.put(q,s,'move_'+name)
   transfers.append(dict(piece=name,source=p,target=q,state=s,root_source_component=c.core(p),
    exact_same_transform_overlap=c.core(p)is not None))
 # Install Root-authorized original native thresholds, door jambs and leaves
 # into the new continuous shafts. Cars themselves stay in the HQ floors.
 for b in m['lifts']:
  if b['id']not in(m['main_lifts']['command_rear']['lift_id'],m['main_lifts']['east_gallery']['lift_id']):continue
  for f in b['floors']:
   if f['cabin'][1]not in(-987,-1230):continue
   x,y,z=f['cabin']
   c.box((x-2,y-1,z+3),(x+2,y-1,z+4),FLOOR,'new_native_threshold')
   c.box((x-2,y,z+3),(x+2,y+2,z+3),'minecraft:air','new_native_wall_aperture')
   for X in(x-3,x+3):c.box((X,y,z+4),(X,y+2,z+4),STRUCT,'new_native_landing_jamb')
   c.box((x-3,y+3,z+4),(x+3,y+3,z+4),STRUCT,'new_native_landing_lintel')
   for door in f['landing_doors']:c.put(door['pos'],door['closed_state'],'new_native_closed_landing_leaf')
   for door in f['cabin_doors']:c.put(door['pos'],'minecraft:air','no_fixed_car_leaf_at_empty_floor')
   for call in f['calls']:
    c.put(call['position'],call['state'],'moved_original_call')
    p=call['position'];back=(p[0],p[1],p[2]-1)if call['facing']=='south'else(p[0]-1,p[1],p[2])
    # Backings are copied with the complete original finite hall/post.
    need(c.final(back)not in AIR,'Moved native call has no backing '+str(back))
 for r in ours:
  source,target=tuple(r['source']),tuple(r['target']);tag=c.tags.get(source)
  need(tag is not None and tag.snbt()==r['before_nbt'],'Original controller differs')
  c.put(target,r['state'],'moved_original_floor_controller')
  if target in c.tags:c.holds.append(dict(kind='foreign_BE_at_controller_target',pos=target,nbt=c.tags[target].snbt()))
 # Both old and future service-pipe support contacts remain part of the shaft.
 supports=[(x,y+DY,z)for x,y,z in((6,-666,251),(6,-667,255),(12,-666,251),(12,-667,255))]
 for p in supports:need(c.final(p)==STRUCT,'New fixed pipe support is not full structural panel')
 for p,t in c.tags.items():
  if p in c.after and c.after[p]!=c.old(p)and p not in controlled:
   c.holds.append(dict(kind='other_BE_in_final_write_mask',pos=p,nbt=t.snbt(),root_component=c.core(p)))
 # Shape-based complete corridor widths, endpoint bands and whole car sweep.
 shapes=json.loads((world/'native_collision_shapes.json').read_text('utf8'));failures=[]
 def boxes(p):
  s=c.final(p)
  if s in AIR:return[]
  if s not in shapes:failures.append(dict(kind='unknown_shape',pos=p,state=s));return[[0,0,0,1,1,1]]
  return shapes[s]
 def stand(p):
  x,y,z=p;floor=boxes((x,y-1,z));clear=all(not(b[3]>.205 and b[0]<.795 and b[5]>.205 and b[2]<.795 and b[4]>.01 and b[1]<h)for dy,h in((0,1),(1,.79))for b in boxes((x,y+dy,z)))
  return clear and any(.9<=b[4]<=1.001 and b[0]<=.5<=b[3]and b[2]<=.5<=b[5]for b in floor)
 walks=[]
 for role,xs,zs,y in[('main_hangar_3wide',range(9,12),range(258,294),-987),('east_hangar_3wide',range(65,68),range(307,312),-987),('terminal_3wide_handoff',range(10,13),range(258,265),-1230)]:
  for x in xs:
   for z in zs:
    p=(x,y,z);ok=stand(p);walks.append(dict(role=role,feet=p,passable=ok))
    if not ok:failures.append(dict(kind='walk_not_supported_or_clear',role=role,pos=p,states=[c.final((x,Y,z))for Y in(y-1,y,y+1)]))
 edge_checks=[];walking={tuple(row['feet'])for row in walks}
 def bearing(p):return any(.9<=b[4]<=1.001 and b[0]<=.5<=b[3]and b[2]<=.5<=b[5]for b in boxes(p))
 for p in sorted(walking):
  x,y,z=p
  for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
   q=(x+dx,y,z+dz)
   if q in walking:
    # Whole 0.59m body sweep across the shared boundary, not just free centres.
    lo=(min(x,q[0])+.205,y+.01,min(z,q[2])+.205);hi=(max(x,q[0])+.795,y+1.79,max(z,q[2])+.795)
    for px,pz in((x,z),(q[0],q[2])):
     for py in(y,y+1):
      for b in boxes((px,py,pz)):
       if all((px,py,pz)[i]+b[i+3]>lo[i]and(px,py,pz)[i]+b[i]<hi[i]for i in range(3)):
        failures.append(dict(kind='cross_boundary_body_collision',from_pos=p,to_pos=q,block=[px,py,pz]))
    continue
   if bearing((q[0],y-1,q[2]))or bearing((q[0],y-2,q[2])):continue
   guarded=any(Y+b[4]>y+.6 and Y+b[1]<y+1.8 for Y in(y,y+1)for b in boxes((q[0],Y,q[2])))
   edge_checks.append(dict(inside=p,outside=q,guarded=guarded))
   if not guarded:failures.append(dict(kind='unprotected_declared_gallery_edge',inside=p,outside=q))
 for role,lo,hi in[('main',(7,-1231,251),(11,-849,255)),('east',(64,-988,300),(68,-606,304))]:
  for p in points(lo,hi):
   if boxes(p):failures.append(dict(kind='car_sweep_obstruction',role=role,pos=p,state=c.final(p)))
 # Root core after-state may be needed for a landing-side cell, but its
 # provenance is explicit. No external void is silently promoted to a route.
 changes=[dict(pos=p,before=c.old(p),after=s,owner=c.owner[p])for p,s in sorted(c.after.items())if c.old(p)!=s]
 save(out/'BLOCK_PATCH.json.gz',dict(world_written=False,cells=changes,inverse=[dict(pos=r['pos'],before=r['after'],after=r['before'])for r in changes]))
 save(out/'FULL_COMPOSED_STATES.json.gz',[dict(pos=p,before=c.old(p),after=s,owner=c.owner[p])for p,s in sorted(c.after.items())])
 save(out/'ADDED_HALL_RIGID_TRANSFERS.json.gz',transfers)
 save(out/'CONTROLLED_BE_INTERFACE.json',dict(operations=ours,root_moves_internal_86_366_five_BE=True,stationary_HQ_office_car_BE_untouched=True,not_applied=True))
 save(out/'OWNERSHIP.json',dict(shaft_exclusions_in_core_source=[SOURCE_MAINSHAFT,SOURCE_EASTSHAFT],
  shaft_exclusions_in_core_destination=[MAINSHAFT,EASTSHAFT],
  added_moving_pieces=[dict(id=n,source=[lo,hi],target=[shifted(lo),shifted(hi)])for n,lo,hi in PIECES],
  transformation=[0,DY,0],root_retirement='Y<-672 deepslate[axis=y], otherwise stone',
  shared_cells=sum(t['exact_same_transform_overlap']for t in transfers),root_deep_core_and_candidate_must_compose_same_final_states=True,
  positive_edit_mask='BLOCK_PATCH.json.gz cells[].pos',full_lift_controlled_mask='FULL_COMPOSED_STATES.json.gz pos'))
 save(out/'STATIC_VALIDATION.json',dict(walks=walks,edge_checks=edge_checks,support_contacts=supports,failures=failures,native_game_verified=False))
 save(out/'HOLDS.json',c.holds)
 save(out/'REPORT.json',dict(world=str(world),world_written=False,ready=False,changed_cells=len(changes),composed_cells=len(c.after),
  moved_addition_cells=len(transfers),typed_controller_moves=len(ours),holds=len(c.holds),static_failures=len(failures),
  source_script_sha256=sha(Path(__file__).read_bytes()),read_boxes=c.read_boxes,
  old_landing_controller_floors=[-846,-603],new_hangar=-987,new_terminal=-1230,
  actual_moving_car_created=False,remaining=['Root compose/deduplicate with deep core geometry and all native BE exactly once','all real lift riding/door and final visual checks']))
 print(json.dumps(dict(changed_cells=len(changes),composed_cells=len(c.after),holds=len(c.holds),static_failures=len(failures),world_written=False)))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path,required=True);p.add_argument('--metadata',type=Path,required=True);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
