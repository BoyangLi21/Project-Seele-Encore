"""Read-only attribution to explicit original civil operations and exact copied source cells."""
from pathlib import Path
import json,hashlib,math,collections
import numpy as np
from r52_spatial_plan import Frame
from facility_frame_nbt_r52 import state_in_frame
ROOT=Path(__file__).resolve().parents[1];BASE=Path('D:/eva/artifacts/map_complete_20261013');O=ROOT/'.Codex/map_complete_20261013/route_audit/prelaunch_world_current'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guide(z):
 length=160.;d=min(length,max(0.,z+212.));blend=6.;effective=154.
 def rounded(a):return a*.5-blend/(2*math.pi)*math.sin(math.pi*a/blend)
 rise=rounded(d) if d<blend else effective-rounded(length-d) if d>length-blend else d-blend*.5
 return -443+32*rise/effective
def roles(q):
 x,y,z=q;out=[];cx=min((-12,30,72),key=lambda c:abs(x-c));dx=x-cx
 if -212<=z<=-54:
  f=math.floor(guide(z));d=y-f
  if d==-6 and -35<=x<=95:out.append(('ramp/sealed_common_underside','原斜轨三槽共同密封底板','plan_factory_r20.py:143'))
  if d==-5 and abs(dx)<=14:out.append(('ramp/recessed_trench_floor','原斜轨29格凹槽底板','plan_factory_r20.py:140'))
  if -4<=d<=0 and abs(dx)<=14:out.append(('ramp/authored_transport_negative','原作者明确载台净空槽内的后续实体格，尚需查后续归属','plan_factory_r20.py:139'))
  if -2<=d<=0 and 15<=abs(dx)<=17:out.append(('ramp/trench_side_lip','原29格凹槽两侧槽唇/围护基体','plan_factory_r20.py:125,139-141'))
  if d==0 and abs(dx)==15:out.append(('ramp/one_cell_edge_strip','原槽边单格机件饰边','plan_factory_r20.py:141'))
  if x in (-35,95) and 1<=d<=85:out.append(('ramp/outer_wall','原斜轨外侧墙','plan_factory_r20.py:128'))
  if d>=84 and d<=86:out.append(('ramp/roof_or_roof_rib','原斜轨屋顶或同高横肋','plan_factory_r20.py:124-132'))
  if any(abs(x-c)<=1 for c in (9,51)) and 1<=d<=4:out.append(('ramp/middle_service_spine','原两机位间设备脊','plan_factory_r20.py:129-130'))
 if z in (-214,-213):
  if any(abs(x-c)==18 for c in (-12,30,72)) and -442<=y<=-365:out.append(('wet_transfer/original_gate_jamb','原机库出口门侧框','plan_factory_r20.py:147'))
  if -365<=y<=-363 and any(abs(x-c)<=18 for c in (-12,30,72)):out.append(('wet_transfer/original_gate_header','原机库出口门上框','plan_factory_r20.py:148'))
  if y==-443:out.append(('wet_transfer/original_floor_join','原机库出口接缝地板','plan_factory_r20.py:149-150'))
  if y==-449:out.append(('wet_transfer/lower_floor_join','原机库出口下方槽底接缝','plan_factory_r20.py:121-123'))
 if -54<=z<=-18 and abs(dx)<=18:
  if -444<=y<=-412:out.append(('bank/original_foundation','原高位发射室基础体','plan_factory_r20.py:98-99'))
  if -412<=y<=-411:out.append(('bank/original_deck_ring','原高位发射室载台地板环','plan_factory_r20.py:100'))
  if y==-416 and abs(dx)<=15 and -51<=z<=-21:out.append(('bank/original_trench_floor','原高位发射室凹槽底板','plan_factory_r20.py:102'))
  if abs(dx)==17 and -410<=y<=-310:out.append(('bank/original_sidewall','原高位发射室侧壁','plan_factory_r20.py:104-106'))
  if -19<=z<=-18 and abs(dx)<=16 and -410<=y<=-310:out.append(('bank/original_end_wall','原高位发射室端墙','plan_factory_r20.py:107'))
  if y in (-311,-310):out.append(('bank/original_upper_roof_ring','原发射室顶环','plan_factory_r20.py:108-109'))
  if z in (-54,-53) and -326<=y<=-312:out.append(('bank/original_upper_front_return','原发射室上前封边','plan_factory_r20.py:110'))
  if abs(dx)==10 and z==-20 and -410<=y<=-311:out.append(('bank/original_end_reinforcement','原发射室端面竖加强带','plan_factory_r20.py:111'))
 if 95<=x<=113 and -397<=y<=-389 and -279<=z<=-42:out.append(('personnel/documented_side_gallery_region','原作者明确侧向操作廊区域（保护，细部需原通行图复核）','plan_factory_r20.py:167-175'))
 return out
def source_for(p):
 x,y,z=p
 if 10<=z<=46:return 'compact_bank3_copy',(60-x,y+620,-8-z)
 if 47<=z<=57:return 'compact_bank2_to3_original_slice_copy',(60-x,y+610,-100)
 if 58<=z<=94:return 'compact_bank2_copy',(60-x,y+620,40-z)
 if 95<=z<=105:return 'compact_bank1_to2_original_slice_copy',(60-x,y+610,-100)
 return 'original_hangar_ramp_bank1_rigid_copy',(60-x,y+620,88-z)
def main():
 source=BASE/'survey/original_hangar_transfer_launch.npz';a=np.load(source);origin=a['origin'];pal=list(map(str,a['palette']));vox=a['states'];frame=Frame(180,60,-620,88)
 data=json.loads((O/'CURRENT_PRELAUNCH_CATEGORIES.json').read_text('utf8'));selected=[]
 for key in ('other_native_obstruction_requires_authored_role','fixed_steel_inside_native','near_fixed_steel_no_finite_face','finite_fixed_steel_native_face'):
  for c in data['groups'].get(key,[]):
   c=c.copy();c['prior_geometry_category']=key;component,q=source_for(c['position']);ix=np.array(q)-origin;matches=False;before=None
   if 0<=ix[0]<vox.shape[2] and 0<=ix[1]<vox.shape[0] and 0<=ix[2]<vox.shape[1]:before=state_in_frame(pal[int(vox[ix[1],ix[2],ix[0]])],frame);matches=before==c['original_scan_state']
   found=roles(q);c.update(explicit_copy_component=component,actual_original_block_index=q,frozen_source_transformed_state=before,frozen_source_equals_scan=matches,authored_operations=[dict(id=r[0],label=r[1],source=r[2]) for r in found])
   # Most specific later authored operation wins only as an attribution label;
   # all overlapping source records remain visible. Nothing becomes permission.
   role=found[-1][0] if found else 'UNATTRIBUTED_TO_LISTED_SOURCE_OPERATIONS'
   if not matches:role='SOURCE_STATE_CHANGED_OR_NOT_COPIED/'+role
   c['group_role']=role;selected.append(c)
 grouped=collections.defaultdict(list)
 for c in selected:grouped[c['explicit_copy_component'],c['group_role'],c['prior_geometry_category']].append(c)
 summaries=[]
 for (component,role,category),rows in grouped.items():
  parts=collections.Counter(m['part'] for c in rows for m in c['motion_witnesses']);materials=collections.Counter(c['state'] for c in rows)
  summaries.append(dict(copy_component=component,authored_role=role,geometry_category=category,cells=len(rows),bbox=[[min(c['position'][i] for c in rows) for i in range(3)],[max(c['position'][i] for c in rows) for i in range(3)]],materials=dict(materials),actual_moving_parts=dict(parts),source_operation_refs=sorted({r['source'] for c in rows for r in c['authored_operations']})))
 summaries.sort(key=lambda r:(r['copy_component'],-r['cells']))
 report=dict(world_written=False,apply_authorized=False,scope='Author/source attribution only. Explicit original author fill/clear operations and exact frozen copied palette are used; no room, corridor, support function, or edit authority is inferred from air. Both original block-index frame and compact chamber/section-copy offsets are explicit. Later source owners not listed remain UNATTRIBUTED.',source_sha256={str(p):sha(p) for p in [source,ROOT/'tools/plan_factory_r20.py',ROOT/'tools/prepare_complete_compact_banks.py',ROOT/'tools/hangar_tv_design_r44.py',Path(__file__)]},groups=summaries,cells=selected)
 (O/'PRELAUNCH_AUTHORED_COMPONENT_GROUPS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('groups',len(summaries),'cells',len(selected),'source_exact',sum(c['frozen_source_equals_scan'] for c in selected));print(json.dumps([r for r in summaries if r['cells']>=100],ensure_ascii=False))
if __name__=='__main__':main()
