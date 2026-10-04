"""Audit whole corridor footprints, with named ports and mechanical exclusions."""
import json
from pathlib import Path
import numpy as np
import scan_regional_completion as scan
from query_blocks import AIR
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/world_repair_r21'
WORLD=ROOT/'run/saves/SEELE_R21_REVIEW'
def main():
 contract=json.loads((OUT/'facility_contract.json').read_text())
 contract['world']='SEELE_TV_WORLD_PREVIEW_20260906'
 for section in contract['sections']:
  if section['id']=='factory_lower':section['rects']=[[102,114,-290,-54]]
  if section['id']=='factory_middle':
   section['rects']=[[95,113,-275,-43],[89,113,-49,-43],[86,113,-271,-259]]
   section['south_end_role']='Enclosed industrial observation window; no south door'
   section['enclosed_observation_boundaries']=[{'x': [90, 112], 'z': -43, 'feet': -394, 'wall_y': [-394, -389], 'waist_state': 'projectseele:nerv_wall_panel', 'glass_state': 'projectseele:clear_glass', 'frame_state': 'projectseele:nerv_structural_panel', 'vertical_frame_x': [90, 96, 104, 112], 'top_seal_y': -389, 'continuous_roof_y': -388, 'through_route': False, 'enclosed': True, 'clear_waiting_rows_z': [-46, -45, -44]}]
  if section['id']=='launch_station_west_foyer':section['rects']=[[102,132,-56,-43]];section['height']=6
 contract['sections'].append(dict(id='launch_station_retained_platform_gallery',rects=[[108,116,-35,-25]],floor=-443,height=7,ports=[]))
 contract['ports']=json.loads((OUT/'details/full_width_ports_and_taxi_finish/places.json').read_text())['ports']
 contract['mechanical_exclusions']=json.loads((ROOT/'artifacts/world_rebuild_r20/lifts/sweep_masks.json').read_text())
 contract['retired']=[dict(bounds=[135,-449,195,164,-436,265],purpose='obsolete east platform'),dict(bounds=[138,-465,207,150,-450,207],purpose='obsolete platform end wall')]
 contract['verification']={'full_route_catalogue':8861,'edges':'edge_physics_pass.json','downward_sightline':'native image required; old cage wall now glazed','long_corridor_cross_sections':'global_corridor_sections.json'}
 scan.WORLD=WORLD;lo=(-42,-475,-298);hi=(207,-345,478);a,p=scan.volume(lo,hi)
 empty=np.array([s.split('[')[0] in AIR|{'minecraft:light','minecraft:structure_void'} for s in p])
 def at(x,y,z):return p[int(a[y-lo[1],z-lo[2],x-lo[0]])]
 def free(x,y,z):return bool(empty[a[y-lo[1],z-lo[2],x-lo[0]]])
 def excluded(x,y,z):
  if 109<=x<=115 and 247<=z<=255:return True # actual six-riser stair, independently traversed at all five widths
  if 98<=x<=110 and -94<=z<=-75:return True # two real level transitions -369 -> -367
  for s in contract['mechanical_exclusions']:
   b,c=s['sweep']
   if b[0]-1<=x<=c[0]+1 and b[2]-1<=z<=c[2]+1 and b[1]-1<=y<=c[1]+1:return True
  return False
 findings=[];checked=0
 for section in contract['sections']:
  f=section['floor'];mask={(xx,zz) for x0,x1,z0,z1 in section['rects'] for xx in range(x0,x1+1) for zz in range(z0,z1+1)}
  for x,z in sorted(mask):
   if excluded(x,f+1,z):continue
   checked+=1
   neighbours=[(x+dx,z+dz) for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]]
   interior=all(q in mask for q in neighbours)
   if interior and free(x,f,z) and free(x,f-1,z):
    findings.append(dict(kind='missing_floor',section=section['id'],pos=[x,f,z],state=at(x,f,z)))
   if not free(x,f,z) and free(x,f+1,z) and free(x,f+2,z):
    if interior and all(free(x,yy,z) for yy in range(f+section['height'],min(hi[1],f+section['height']+4)+1)):
     findings.append(dict(kind='missing_roof',section=section['id'],pos=[x,f+section['height'],z]))
    for xx,zz in neighbours:
     if (xx,zz) in mask or excluded(xx,f+1,zz):continue
     if all(free(xx,yy,zz) for yy in range(f-2,f+3)):
      findings.append(dict(kind='unguarded_drop',section=section['id'],pos=[xx,f+1,zz],from_pos=[x,f+1,z]))
 report=dict(checked_footprint_cells=checked,candidates=findings,interpretation='Candidates require named-port and stair inspection; native collision/guard tests remain authoritative for partial blocks')
 (OUT/'global_audit/spatial_footprint.json').write_text(json.dumps(report,indent=2))
 (OUT/'spatial_contract_r21.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf8')
 print('R21 complete footprint audit',checked,'cells;',len(findings),'candidates')
if __name__=='__main__':main()
