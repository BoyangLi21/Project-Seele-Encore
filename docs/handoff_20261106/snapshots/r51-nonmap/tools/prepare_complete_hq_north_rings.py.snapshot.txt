"""Two finite missing HQ public-ring links; candidates only, no WORLD writes.

Author actual three-wide deck edges and original-room exclusions. Never uses
the failed six-link script as a writer, or a private room as a public shortcut.
"""
from pathlib import Path
import argparse,collections,gzip,json
import numpy as np
from query_blocks import AIR
from prepare_complete_remaining_personnel import ReadPlan
from prepare_complete_main_lift_civil import STRUCT,FLOOR,points,need,save,sha

ROOT=Path(__file__).resolve().parents[1]
BASE=Path('D:/eva/artifacts/map_complete_20261013')
WALL='projectseele:nerv_wall_panel'
PLANS=[dict(id='B1_north',y=-554,path=[[-30,270],[-30,263],[89,263],[89,270]],
  rationale='North crossway at Z263 leaves both original polished-deepslate columns X-26/-6 Z265 outside the full three-wide walking footprint.'),
 dict(id='7F_north',y=-457,path=[[11,300],[6,300],[6,283],[58,283],[58,309]],
  rationale='Outside original optical room X10..50/Z286..298, relay room X-5..6/Z302..332, SEELE room and all native east-lift hardware; preserves original guide at9/-455/294.')]

def path_points(nodes,radius):
 out=set()
 for(x,z),(X,Z)in zip(nodes,nodes[1:]):
  need(x==X or z==Z,'Orthogonal finite corridor required')
  for xx in range(min(x,X)-radius,max(x,X)+radius+1):
   for zz in range(min(z,Z)-radius,max(z,Z)+radius+1):out.add((xx,zz))
 return out

def main(args):
 world=args.world.resolve();out=args.out.resolve();need(out.is_relative_to((ROOT/'.Codex').resolve())and not out.exists(),'Fresh .Codex output required');out.mkdir(parents=True)
 c=ReadPlan(world);shapes=json.loads((world/'native_collision_shapes.json').read_text('utf8'));unknown=set()
 room_source=json.loads((world/'spatial_contract_r23.json').read_text('utf8'))['room_entries']
 owned=np.load(BASE/'pyramid_component/owner_mask.npz');om=owned['owned'];origin=owned['origin']
 def is_inside(p):
  x,y,z=p;i=(y+93-int(origin[1]),z-int(origin[2]),x-int(origin[0]))
  return all(0<=i[k]<om.shape[k]for k in range(3))and bool(om[i])
 def boxes(state):
  if state in AIR:return[]
  if state.startswith('mtr:escalator_step[')and'orientation=flat'in state:return[[0,0,0,1,.9375,1]]
  if state not in shapes:unknown.add(state);return None
  return shapes[state]
 def bearing(state):
  b=boxes(state);return b is not None and any(.9<=r[4]<=1.001 and r[0]<=.5<=r[3]and r[2]<=.5<=r[5]for r in b)
 def clear(state,height=1):
  b=boxes(state);return b is not None and not any(r[3]>.205 and r[0]<.795 and r[5]>.205 and r[2]<.795 and r[4]>.01 and r[1]<height for r in b)
 summaries=[];walks=set();guarded=set();supports=[];cut_cells=[];rooms_saved=[]
 for plan in PLANS:
  y=plan['y'];foot=path_points(plan['path'],1);margin=path_points(plan['path'],3)
  lo=(min(x for x,z in margin),y-4,min(z for x,z in margin));hi=(max(x for x,z in margin),y+4,max(z for x,z in margin));c.read(lo,hi)
  named=[r for r in room_source if r['floor']-93+1==y]
  protected_room_cells=set()
  for r in named:
   x,X,z,Z=r['bounds'];protected_room_cells.update((xx,zz)for xx in range(x,X+1)for zz in range(z,Z+1));rooms_saved.append(dict(id=r['id'],bounds=r['bounds'],floor=r['floor']-93))
  for x,z in foot:
   if(x,z)in protected_room_cells:c.holds.append(dict(kind='original_room_in_public_corridor',pos=[x,y,z]))
   for Y in range(y-2,y+3):
    if not is_inside((x,Y,z)):c.holds.append(dict(kind='outside_original_pyramid_component',pos=[x,Y,z]))
   under=(x,y-1,z)
   if not bearing(c.old(under)):
    if c.old(under)not in AIR:c.holds.append(dict(kind='foreign_nonbearing_floor',pos=under,state=c.old(under)))
    c.put(under,FLOOR,'new_three_wide_public_deck')
    beam=(x,y-2,z)
    if c.old(beam)in AIR:c.put(beam,STRUCT,'underside_longitudinal_box_beam')
    elif not bearing(c.old(beam)):c.holds.append(dict(kind='beam_crosses_unknown_feature',pos=beam,state=c.old(beam)))
    supports.append(dict(deck=under,beam=beam))
   for Y in range(y,y+3):
    p=(x,Y,z);s=c.old(p)
    if p in c.tags:c.holds.append(dict(kind='functional_BE_in_walk_aperture',pos=p,nbt=c.tags[p].snbt()));continue
    if s not in AIR and not s.startswith('projectseele:nerv_ceiling_light['):
     # ModBlocks.java registers wall_datum as an ordinary iron-based finish,
     # without BE or runtime behavior. Only this measured three-wide portal
     # crosses its existing decorative band; no general functional whitelist.
     datum_port=s=='projectseele:nerv_wall_datum'and x==8 and Y==-456 and 299<=z<=301
     if not datum_port and s not in{'minecraft:deepslate_bricks','minecraft:polished_deepslate','projectseele:nerv_structural_panel',WALL,'projectseele:clear_glass','minecraft:light_gray_concrete','minecraft:gray_concrete'}:
      c.holds.append(dict(kind='unknown_aperture_function',pos=p,state=s));continue
     cut_cells.append(dict(pos=p,before=s,after='minecraft:air'))
     c.put(p,'minecraft:air','finite_original_public_boundary_opening')
   walks.add((x,y,z))
  # Perimeter protection is added only at real drops. Existing supported
  # circulation and original room walls remain unblocked and byte-preserved.
  border={ (x+dx,z+dz)for x,z in foot for dx,dz in((1,0),(-1,0),(0,1),(0,-1))if(x+dx,z+dz)not in foot}
  new_guards=set()
  for x,z in border:
   if bearing(c.old((x,y-1,z)))or bearing(c.old((x,y-2,z))):continue
   footstate=c.old((x,y,z));headstate=c.old((x,y+1,z))
   if not clear(footstate)or not clear(headstate,.79):continue
   if(x,z)in protected_room_cells:c.holds.append(dict(kind='guard_would_enter_original_room',pos=[x,y,z]));continue
   if(x,y,z)in c.tags:c.holds.append(dict(kind='BE_at_guard',pos=[x,y,z]));continue
   for Y in(y-2,y-1,y):
    if not is_inside((x,Y,z)):c.holds.append(dict(kind='guard_outside_original_component',pos=[x,Y,z]))
   for Y,state in((y-2,STRUCT),(y-1,STRUCT)):
    p=(x,Y,z)
    if c.old(p)in AIR:c.put(p,state,'outer_bracket_and_guard_footing')
    elif not bearing(c.old(p)):c.holds.append(dict(kind='guard_footing_has_other_feature',pos=p,state=c.old(p)))
   new_guards.add((x,z));guarded.add((x,y,z))
  for x,z in new_guards:
   props={name:((x+dx,z+dz)not in foot|new_guards and not bearing(c.final((x+dx,y-1,z+dz)))and not bearing(c.final((x+dx,y-2,z+dz))))for name,dx,dz in(('east',1,0),('north',0,-1),('south',0,1),('west',-1,0))}
   state='projectseele:tv_personnel_guard_r44[drop=0,'+','.join(name+'='+str(props[name]).lower()for name in('east','north','south','west'))+']'
   c.put((x,y,z),state,'thin_native_safety_rail')
  # This edge-mounted native rail preserves the supported outer strip too;
  # audit every additional standing centre and its own outer boundary.
  walks.update((x,y,z)for x,z in new_guards)
  # Original-style low floor lights, within new deck only; no floating fixture.
  centre=path_points(plan['path'],0)
  for x,z in sorted(centre):
   p=(x,y,z)
   if((x if z==plan['path'][1][1]else z)%16==0 and c.old((x,y-1,z))in AIR and c.final(p)in AIR):
    c.put(p,'projectseele:nerv_ceiling_light[hanging=false,lit=true]','original_style_deck_light')
  summaries.append(dict(**plan,full_width_foot_cells=len(foot),new_guard_cells=len(new_guards),full_footprint=sorted(foot)))
 # Keep all measured NBT, room interiors, optical fixtures and native lifts.
 for p,t in c.tags.items():
  if c.final(p)!=c.old(p):c.holds.append(dict(kind='original_BE_touched',pos=p,nbt=t.snbt()))
 failures=[];edges=[]
 for x,y,z in sorted(walks):
  p=(x,y,z)
  if not bearing(c.final((x,y-1,z)))or not clear(c.final(p))or not clear(c.final((x,y+1,z)),.79):failures.append(dict(kind='full_width_footprint_not_walkable',pos=p))
  for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
   q=(x+dx,y,z+dz)
   if q in walks:
    lo=(min(x,q[0])+.205,y+.01,min(z,q[2])+.205);hi=(max(x,q[0])+.795,y+1.79,max(z,q[2])+.795)
    for X,Z in((x,z),(q[0],q[2])):
     for Y in(y,y+1):
      for b in boxes(c.final((X,Y,Z)))or[]:
       if all((X,Y,Z)[i]+b[i+3]>lo[i]and(X,Y,Z)[i]+b[i]<hi[i]for i in range(3)):failures.append(dict(kind='full_body_edge_collision',from_pos=p,to_pos=q,block=[X,Y,Z]))
   elif not bearing(c.final((q[0],y-1,q[2])))and not bearing(c.final((q[0],y-2,q[2]))):
    low=(min(x,q[0])+.205,min(z,q[2])+.205);high=(max(x,q[0])+.795,max(z,q[2])+.795)
    ok=any(Y+b[4]>y+.6 and Y+b[1]<y+1.8 and X+b[3]>low[0]and X+b[0]<high[0]and Z+b[5]>low[1]and Z+b[2]<high[1]
     for X,Z in((x,z),(q[0],q[2]))for Y in(y,y+1)for b in boxes(c.final((X,Y,Z)))or[])
    edges.append(dict(inside=p,outside=q,guarded=ok))
    if not ok:failures.append(dict(kind='unguarded_edge',inside=p,outside=q))
 # The lower original Y=-559 floor stays open below the new B1 beam.
 under_checks=[]
 for x,z in path_points(PLANS[0]['path'],2):
  p=(x,-558,z)
  if bearing(c.old((x,-559,z)))and clear(c.old(p))and clear(c.old((x,-557,z)),.79):
   ok=clear(c.final(p))and clear(c.final((x,-557,z)),.79);under_checks.append(dict(foot=p,preserved=ok))
   if not ok:failures.append(dict(kind='lower_original_lobby_blocked',pos=p))
 for s in sorted(unknown):failures.append(dict(kind='missing_native_shape',state=s))
 rows=c.export(out)
 save(out/'SPATIAL_CONTRACT_CANDIDATE.json',dict(schema='projectseele.r53.hq-two-north-rings.candidate.v1',plans=summaries,readiness=False,original_named_rooms=rooms_saved,
  original_main_lifts_and_office_unchanged=True,source_pyramid_mask_sha256=sha((BASE/'pyramid_component/owner_mask.npz').read_bytes())))
 save(out/'EXACT_BOUNDARY_OPENINGS.json',cut_cells)
 save(out/'PRESERVED_BLOCK_ENTITIES.json',[dict(pos=p,nbt=t.snbt())for p,t in sorted(c.tags.items())])
 save(out/'STATIC_VALIDATION.json',dict(failures=failures,walking_cells=len(walks),perimeter_drop_checks=edges,original_lower_lobby=under_checks,deck_supports=supports,native_game_verified=False))
 save(out/'REPORT.json',dict(world=str(world),world_written=False,ready=False,changed_cells=len(rows),holds=len(c.holds),static_failures=len(failures),new_floors=[-554,-457],
  source_script_sha256=sha(Path(__file__).read_bytes()),needs=['Root review of this single actual geometry candidate','Whole native navigation and visual readback after final integration']))
 print(json.dumps(dict(changed_cells=len(rows),holds=len(c.holds),failures=len(failures),world_written=False)))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path,required=True);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
