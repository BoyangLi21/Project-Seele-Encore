"""Measured retirement, enclosed junctions and real exits at the reported defects."""
import argparse,json
import numpy as np
import regional_voxels as v,scan_regional_completion as scan,plan_factory_r20 as f,repair_facility_r21 as h
from query_blocks import iter_block_entities,AIR
ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_R25_REVIEW';OUT=ROOT/'artifacts/facility_r25/route_repairs'
def main(apply=False):
 OUT.mkdir(parents=True,exist_ok=True);v.WORLD=scan.WORLD=WORLD;v.OUT=OUT;p=v.Painter();walks=[];scopes=[]
 def scene(lo,hi):f.LO=h.LO=lo;f.HI=h.HI=hi;return h.Facility()
 def finish(s,name):
  changes=s.before!=s.after
  for q,t in iter_block_entities(WORLD,v.DIM,f.LO,f.HI):
   if changes[q[1]-f.LO[1],q[2]-f.LO[2],q[0]-f.LO[0]] and not str(t['id']).endswith('sign'):raise RuntimeError(('Unexpected fixture',name,q,t.snbt()))
  count=s.delta(p,'r25/'+name);walks.extend(s.walks);scopes.append(dict(name=name,lo=f.LO,hi=f.HI,changed_cells=count))
 # The west-of-platform native tail is proven absent from all depot paths.
 assert (ROOT/'artifacts/facility_r25/transit/installed_review.json').is_file()
 s=scene((91,-446,-294),(116,-430,-23))
 # Retire exactly the obsolete lower-gallery envelope. Adjacent mechanical
 # foundations, elevated boarding gallery and live station are untouched.
 s.fill((102,-443,-290,114,-437,-50),'minecraft:air')
 # The retired lower walk crossed active upper-gallery load paths. Its
 # clearance mask may retire the corridor but must not cut these columns.
 for z in range(-279,-41,24):s.fill((112,-443,z,113,-437,z+1),h.STRUCT)
 for x in (112,114):s.fill((x,-443,-82,x,-437,-82),h.STRUCT)
 s.hall('station_west_connection',[(97,112,-49,-34),(108,116,-37,-25)],-443,6,
        [(98,-442,-49,100,-439,-49),(97,-442,-47,97,-439,-44),(116,-442,-34,116,-439,-28),(109,-442,-25,115,-439,-25)])
 # Clear the old turnback ballast only within the new pedestrian footprint.
 s.path('station_west_link',[[108.5,-442,-35.5],[105.5,-442,-40.5],[99.5,-442,-44.5],[99.5,-442,-48.5]])
 s.path('station_actual_hangar_lift',[[93.5,-442,-46.5],[99.5,-442,-46.5],[105.5,-442,-40.5],[108.5,-442,-35.5]])
 finish(s,'retired_lower_dead_gallery_and_station_junction')
 s=scene((-38,-370,-228),(99,-360,-208))
 # Two Z layers, not the glass boundary at Z=-210. Retain the overhead
 # header and the separate crane portal; only the occluding plate retires.
 for z in (-214,-213):
  box=(-34,-367,z,91,-362,z);sl=s.index(box);a=s.after[sl]
  mask=np.array([q in {f.STRUCT,f.FLOOR,f.EDGE,f.MACHINE} for q in s.palette])[a];a[mask]=s.state('minecraft:air')
 # A legacy X=85 end wall crossed the through observation corridor.
 s.fill((85,-367,-225,85,-363,-217),'minecraft:air')
 s.path('observation_cross_reopened',[[92.5,-367,-220.5],[82.5,-367,-220.5]])
 finish(s,'observation_sightline_and_partition')
 s=scene((129,-451,258),(140,-438,270))
 # Remove protruding legacy black stair fragments; the current pyramid
 # panels and shaft remain. No hole is cut in the finished pyramid skin.
 for yy,zz,xx in np.argwhere(np.isin(s.before,[i for i,q in enumerate(s.palette) if q in {'minecraft:polished_blackstone','minecraft:polished_deepslate','minecraft:black_concrete','minecraft:gray_concrete'}])):
  x,y,z=int(xx+f.LO[0]),int(yy+f.LO[1]),int(zz+f.LO[2])
  if x>=133 and z>=264:s.fill((x,y,z,x,y,z),'minecraft:air')
 finish(s,'pyramid_legacy_stair_fragments')
 # A: the upper stub already overlooks a lower through corridor. Reconnect
 # it by a full-width stair instead of leaving a five-metre drop.
 s=scene((185,-471,391),(205,-451,415))
 s.hall('annex_a_landing',[(188,201,395,404)],-462,6,[(188,-461,397,188,-458,401),(194,-461,404,198,-458,404)])
 for z in range(403,411):
  y=-461-max(0,min(5,z-404));s.fill((194,y-2,z,198,y-1,z),f.STRUCT)
  s.fill((195,y,z,197,y+3,z),'minecraft:air');s.fill((195,y-1,z,197,y-1,z),f.FLOOR if z in (403,404,410) else 'minecraft:smooth_quartz_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
  for x in (194,198):s.fill((x,y,z,x,y+3,z),f.WALL)
  s.fill((194,y+4,z,198,y+4,z),f.STRUCT)
 s.fill((195,-466,411,197,-463,411),'minecraft:air');s.fill((195,-467,411,197,-467,411),f.FLOOR)
 s.path('annex_a_stair',[[190.5,-461,398.5],[196.5,-461,398.5],[196.5,-461,404.5],[196.5,-466,410.5],[196.5,-466,411.5]])
 finish(s,'annex_a_connected_to_lower_route')
 # B: remove the blind north spur and enter the adjacent retained room.
 s=scene((321,-471,437),(343,-456,455))
 s.fill((324,-469,443,332,-459,446),'minecraft:air')
 s.hall('annex_b_corner',[(324,337,446,453)],-467,6,[(326,-466,453,330,-463,453),(337,-466,448,337,-463,451)])
 s.path('annex_b_connected_room',[[328.5,-466,453.5],[328.5,-466,450.5],[338.5,-466,450.5]])
 finish(s,'annex_b_room_connection')
 # C: the original door ends six metres above the existing garden. Give it
 # a guarded stair to the measured turf, retaining its indoor landing.
 s=scene((251,-477,259),(267,-458,289))
 s.hall('annex_c_exit',[(254,264,262,273)],-467,6,[(256,-466,262,260,-463,262),(257,-466,273,261,-463,273)])
 for z in range(271,283):
  y=-466-min(6,max(0,z-274));s.fill((256,y-2,z,262,y-1,z),f.STRUCT)
  s.fill((257,y,z,261,y+3,z),'minecraft:air')
  s.fill((257,y-1,z,261,y-1,z),f.FLOOR if z<=274 or z>=281 else 'minecraft:smooth_quartz_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]')
  for x in (256,262):s.fill((x,y,z,x,y+1,z),'projectseele:clear_glass')
 s.fill((257,-472,283,261,-470,285),'minecraft:air');s.fill((257,-473,283,261,-473,285),'projectseele:nerv_hazard_paving')
 s.path('annex_c_garden_stair',[[258.5,-466,265.5],[259.5,-466,274.5],[259.5,-472,282.5],[259.5,-472,284.5]])
 finish(s,'annex_c_supported_garden_exit')
 for r in walks:r['id']=r['id'].replace('r21/','r25/',1)
 p.meta.update(scopes=scopes,walk_nodes=walks,retired_bounds=[102,-443,-290,114,-437,-50],station_unused_spur_removed=True)
 p.save_plan('reported_route_and_enclosure_repairs')
 if apply:p.apply('reported_route_and_enclosure_repairs')
 (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
