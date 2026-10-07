"""R48 exact underground fronts and authorized supported recovery aprons; no world writer."""
from pathlib import Path
import argparse,json,math
from collections import Counter
from query_blocks import AIR,iter_block_entities
from measure_world_r40 import MeasuredWorld
from prepare_facilities_r48 import Author,FLOOR,WALL,FRAME
ROOT=Path(__file__).resolve().parents[1]
NATURAL=AIR|{'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel','minecraft:andesite','minecraft:diorite','minecraft:granite','minecraft:deepslate','minecraft:tuff'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);args=p.parse_args()
 airport=args.world/'r50_underground_airport.json'
 if airport.is_file()and json.loads(airport.read_text('utf8')).get('installed')is True:
  raise RuntimeError('R50 receivers and side crew access own this frontage; do not regenerate retired R48 upper stairs over the current rail. Use the complete current airport source.')
 out=ROOT/'artifacts/rebuild_r48/underground';out.mkdir(parents=True,exist_ok=True);a=Author(args.world.resolve(),out)
 m=MeasuredWorld(a.world);m.box((-48,-520,-58),(107,-344,142));m.load();assert set(m.status.values())=={'full'}
 tags=dict(iter_block_entities(a.world,m.dimension,(-48,-520,-20),(107,-344,142)));a.t=tags
 door={};civil={};trees={};conflicts=[];plans=[]
 def put(q,state,reason,owner):
  old=m.block(q);assert old is not None
  if q in tags:raise ValueError(('Full BE protected',q,tags[q].snbt()))
  if old==state:return
  a.s[q]=old;owner[q]=(state,reason,None)
 for variant,cx in enumerate((-12,30,72)):
  dz=(-13,-10,-7)[variant]
  assert m.get(cx,-411,-36)=='minecraft:lodestone'
  aperture=[(cx-15,-410,-19),(cx+15,-346,-17)]
  for x in range(cx-15,cx+16):
   for y in range(-410,-345):
    for z in(-19,-18,-17,dz):
     q=x,y,z;old=m.block(q)
     assert old.split('[')[0]in AIR|{FRAME,WALL,'projectseele:nerv_shaft_panel','projectseele:nerv_machine_edge','minecraft:black_concrete'},('Foreign front wall',q,old)
     put(q,'minecraft:barrier','Full three-layer original forward wall becomes motion-owned emergency door aperture',door)
  # Static apron is completely outside the 31x31 launch vertical volume.
  for x in range(cx-17,cx+18):
   for z in range(-12,17):
    for y in range(-413,-410):
     old=m.get(x,y,z);assert old.split('[')[0]in NATURAL,('Foreign apron foundation',x,y,z,old)
     put((x,y,z),FLOOR if y==-411 else FRAME,'Whole supported external recovery apron',civil)
  # Three diagonal reinforced load paths join the existing -444 wall base.
  for beam in(cx-18,cx+17):
   for z in range(-17,17):
    top=min(-414,-444+(z+18))
    for x in range(beam,beam+2):
     for y in range(top-2,top+1):
      q=x,y,z;old=m.block(q)
      if q in door:continue
      assert old.split('[')[0]in NATURAL|{FRAME,WALL,'projectseele:nerv_shaft_panel','projectseele:nerv_machine_edge','minecraft:black_concrete'}
      put(q,FRAME,'Reinforced diagonal cantilever from retained original wall-base bearing',civil)
  # 56 one-metre risers with two-metre treads; each riser uses the native half-step.
  for z in range(17,129):
   if z%2:
    floor=-411-(z-17)//2;surface='minecraft:polished_blackstone_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]'
   else:floor=-412-(z-18)//2;surface=FLOOR
   for x in range(cx-17,cx+18):
    for y in range(floor-2,floor+1):
     q=x,y,z;old=m.block(q);name=old.split('[')[0]
     if name not in NATURAL and not(name.endswith('_log')or name.endswith('_leaves')):conflicts.append(dict(pos=q,state=old,kind='stair_foundation'));continue
     put(q,surface if y==floor and cx-16<=x<=cx+16 else FRAME,'Full EVA-width terraced descent to measured grass datum',civil)
   # Braced piers under each side edge, down to its exact bearing grass/stone.
   if z in(20,36,52,68,84,100,116):
    for px in(cx-16,cx+16):
     for x in range(px-1,px+2):
      for zz in range(z-1,z+2):
       soil=max((y for y in range(-520,floor-2)if m.get(x,y,zz).split('[')[0]in NATURAL-AIR),default=None)
       assert soil is not None,('No exact stair bearing',x,zz)
       for y in range(soil+1,floor-2):
        old=m.get(x,y,zz);assert old.split('[')[0]in AIR or old.split('[')[0].endswith(('_log','_leaves')),('Foreign pier',x,y,zz,old)
        put((x,y,zz),FRAME,'Stair edge braced pier down to individually measured bearing',civil)
   # Native edge guards stay outside the 33-wide driving surface.
   for x,side in((cx-17,'west'),(cx+17,'east')):
    if z<125:
     state='projectseele:nerv_edge_rail['+','.join(k+'='+str(k==side).lower()for k in('east','north','south','west'))+']'
     put((x,floor+1,z),state,'Outer terraced edge guard outside original EVA body corridor',civil)
  # Guard apron edges, leaving both full movement endpoints and leaf pockets free.
  for z in range(-4,17):
   for x,side in((cx-17,'west'),(cx+17,'east')):
    state='projectseele:nerv_edge_rail['+','.join(k+'='+str(k==side).lower()for k in('east','north','south','west'))+']'
    put((x,-410,z),state,'Apron edge guard outside body and door full slide pocket',civil)
  for x in range(cx-16,cx+17):
   for z in range(129,135):
    assert m.get(x,-467,z).startswith('minecraft:grass_block'),('Actual grass handoff differs',x,z,m.get(x,-467,z))
  # Full operation corridor remains dry/clear. Only explicit natural trees in it may retire.
  for x in range(cx-15,cx+16):
   for z in range(-16,135):
    floor=-411 if z<=16 else(-411-(z-17)//2 if z%2 else-412-(z-18)//2)if z<=128 else-467
    for y in range(floor+1,min(-343,floor+66)):
     q=x,y,z;old=m.block(q);name=old.split('[')[0]
     if name in AIR:continue
     if name.endswith(('_log','_leaves')):trees[q]=old
     elif q not in civil:conflicts.append(dict(pos=q,state=old,kind='full_EVA_head_and_body_corridor'))
  plans.append(dict(variant=variant,bed=[cx,-411,-36],pad=[cx,-411,6],wall_aperture=aperture,door_centre=[cx+.5,-410,dz],collision_planes=[-19,-18,-17,dz],clear_width=31,pressure_mesh_width=33,pressure_mesh_height=65,leaf_sweep=[[cx-34,-410,dz-.7],[cx+35,-345,dz+.7]],pad_bounds=[[cx-17,-413,-12],[cx+17,-411,16]],stairs_bounds=[[cx-17,-469,17],[cx+17,-411,128]],grass_handoff=[[cx-16,-467,129],[cx+16,-467,134]],motion_from=[cx+.5,-410,-35.5],motion_to=[cx+.5,-410,6.5]))
 (out/'conflicts.json').write_text(json.dumps(conflicts,ensure_ascii=False,indent=2),'utf8');assert not conflicts,conflicts[:12]
 # Remove complete tree components that actually intersect an authorized new operating corridor.
 seen=set();tree_components=[]
 for seed in trees:
  if seed in seen:continue
  frontier=[seed];component=set()
  while frontier:
   q=frontier.pop()
   if q in seen:continue
   name=(m.block(q)or'').split('[')[0]
   if not name.endswith(('_log','_leaves')):continue
   seen.add(q);component.add(q)
   for dx,dy,dz in((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
    p=q[0]+dx,q[1]+dy,q[2]+dz
    if all((-48,-520,-20)[i]<=p[i]<(107,-344,142)[i]for i in range(3)):frontier.append(p)
    else:raise ValueError(('Tree crosses measured box; extend before retirement',p))
  for q in component:
   if q not in civil:put(q,'minecraft:air','Whole tree component intersecting explicitly authorized EVA corridor retires, including trunk/leaves',civil)
  tree_components.append(dict(cells=len(component),bounds=[[min(q[i]for q in component)for i in range(3)],[max(q[i]for q in component)for i in range(3)]]))
 a.emit('E01_three_forward_wall_doors',door,dict(first_error='R47 emergency control addressed old wet-cage rear pressure gates Z-213, while actual requested front lower launch walls are Z-19/-18/-17',plans=plans,all_3_real_lodestone_lowerBeds_confirmed=True,whole_thickness=3,original_bay_vertical_core_not_filled=True,no_new_model=True))
 a.emit('E03_three_supported_recovery_aprons',civil,dict(plans=plans,tree_components=tree_components,bearing='Cantilever joins retained wall base; each stair pier reaches individually read soil',explicit_new_building_authorization=True,grass_handoff_exact_33wide_six_rows_each=True,ground_roads_rail_APG_and_named_other_facilities_untouched=True))
 (out/'r48_underground_sortie.json').write_text(json.dumps(dict(schema=48,dimension=m.dimension,installed=True,plans=plans),indent=2),'utf8');a.recipe();(out/'manifest.json').write_text(json.dumps(dict(cells=len(a.all),components=a.components,world_written=False,native_function_and_visual_verified=False),ensure_ascii=False,indent=2),'utf8')
 print('Total',len(a.all),'trees',len(tree_components))
if __name__=='__main__':main()
