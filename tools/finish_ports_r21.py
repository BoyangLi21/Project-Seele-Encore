"""Complete full-width interfaces found by the original end-to-end native routes."""
import json,math
import regional_voxels as v
ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_R21_REVIEW';OUT=ROOT/'artifacts/world_repair_r21/details'
F='projectseele:nerv_floor_panel';W='projectseele:nerv_wall_panel';S='projectseele:nerv_structural_panel';G='projectseele:clear_glass';A='minecraft:air'
def main():
 v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();o='r21/complete_registered_ports'
 p.protect((113,-444,-54,184,-433,-37),'r43/native_station_platform_and_apron')
 def b(box,state):p.fill(*box,state,o,'owned')
 # One station-side room, not overlapping corridor boxes that close one
 # another's internal edges. The active track starts south of Z=-43.
 b((102,-444,-56,132,-437,-43),S);b((103,-442,-55,131,-438,-44),A);b((103,-443,-55,131,-443,-44),F)
 for x in (102,132):b((x,-441,-55,x,-438,-44),G)
 for z in (-56,-43):b((103,-441,z,131,-438,z),G)
 for x in (108,120):b((x,-437,-53,x+3,-437,-48),'projectseele:nerv_strip_light')
 ports=[(103,-442,-57,113,-438,-54),(101,-442,-48,104,-438,-44),(130,-442,-54,134,-438,-44),
        (115,-442,-50,121,-438,-44),
        (114,-442,247,116,-438,249),
        (85,-394,-263,91,-390,-260),(88,-394,-260,93,-390,-257),
        (99,-369,-77,109,-364,-75)]
 for box in ports:
  b(box,A);x,y,z,X,Y,Z=box;b((x,y-1,z,X,y-1,Z),F)
 # Remove the unnecessary inner strip left by the first edge guard. The
 # actual external edge is the room's west wall, seven metres farther west.
 b((107,-442,-55,107,-438,-44),A)
 b((6709,75,-6049,6709,76,-6043),A)
 # Paint the revised, safe native UN taxi entry at the already level datum.
 samples=json.loads((OUT.parent/'airport/revision2/track_samples.json').read_text())
 for r in samples:
  if not r['id'].startswith('F2_un_depart'):continue
  for x,y,z in r['points']:
   x,y,z=math.floor(x),round(y),math.floor(z);b((x-8,y-1,z-8,x+8,y-1,z+8),S);b((x-8,y,z-8,x+8,y,z+8),'minecraft:gray_concrete')
  for x,y,z in r['points']:
   x,y,z=math.floor(x),round(y),math.floor(z);b((x,y,z,x,y,z),'minecraft:yellow_concrete')
 # A displaced landing threshold belongs to the actual native touchdown.
 b((6816,74,-6481,6848,74,-6479),'minecraft:white_concrete')
 for z in range(-6632,-6493,40):
  b((6831,74,z,6833,74,z+18),'minecraft:white_concrete')
  for i in range(8):
   for sign in (-1,1):b((6832+sign*i,74,z+18-i,6832+sign*i,74,z+19-i),'minecraft:white_concrete')
 p.meta.update(ports=ports,station_track_sweep_unchanged=True,lower_stair_side_exit=True,UN_terminal_guard_has_real_entry=True)
 p.apply('full_width_ports_and_taxi_finish')
if __name__=='__main__':main()
