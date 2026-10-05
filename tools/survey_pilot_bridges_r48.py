from pathlib import Path
import sys,json,collections
sys.path.insert(0,'D:/eva/tools')
from query_blocks import iter_block_entities
from measure_world_r40 import MeasuredWorld,properties
r=Path('D:/eva');w=r/'artifacts/rebuild_r48/construction/SEELE_R48_WORLD';o=r/'artifacts/rebuild_r48/bridge_static';m=MeasuredWorld(w)
for cx in(-12,30,72):m.box((cx-23,-399,-275),(cx+23,-384,-211))
m.load();assert set(m.status.values())=={'full'}
meta=json.loads((w/'r44_tv_personnel_platforms.json').read_text('utf8'));rooms=json.loads((w/'r47_pilot_restrooms.json').read_text('utf8'))
mesh=json.loads((r/'artifacts/rebuild_r48/assets/assets/projectseele/mesh/tv_shoulder_shells_r44.json').read_text('utf8'));recipe=json.loads((r/'src/main/resources/data/projectseele/worldgen/authored/tv_personnel_recipe_r44.json').read_text('utf8'))
result={'world':str(w),'mesh_resource':str(r/'artifacts/rebuild_r48/assets/assets/projectseele/mesh/tv_shoulder_shells_r44.json'),'runtime_loader':'TvCageEnclosureR44 ResourceLocation projectseele:mesh/tv_shoulder_shells_r44.json; Root-selected R48 overlay inherited from delivered R47, not stale src visual template','mesh_revision':mesh.get('personnel_platform_revision'),'recipe_resource':str(r/'src/main/resources/data/projectseele/worldgen/authored/tv_personnel_recipe_r44.json'),'recipe_operations':len(recipe['operations']),'current_full_427_world_owner_comparison':[],'bays':[],'world_written':False,'native_NPC_and_model_visual_passed':False}
for op in recipe['operations']:
 q=tuple(op['position']);s=m.block(q);result['current_full_427_world_owner_comparison'].append({'pos':q,'expected':op['after'],'actual':s,'matches_source':s==op['after']})
for v,cx in enumerate((-12,30,72)):
 room=next(x for x in rooms['slots']if x['variant']==v);gates=[g for g in meta['entry_gate_pairs']if g['variant']==v];routes=[x for x in meta['crew_exit_routes']if x['id'].startswith(f'tv_operator/{v}/')]
 states=[]
 for x in range(cx-22,cx+23):
  for y in range(-398,-384):
   for z in range(-274,-210):
    s=m.get(x,y,z)
    if s and any(t in s for t in('tv_personnel','city_personnel_door','nerv_edge_rail','nerv_room_partition')):states.append({'pos':[x,y,z],'state':s})
 tags=[{'pos':q,'nbt':t.snbt()}for q,t in iter_block_entities(w,m.dimension,(cx-23,-399,-275),(cx+23,-384,-211))]
 result['bays'].append({'variant':v,'bed':[cx,-443,-240],'original_pilot_UUID':room['pilot_uuid']if'pilot_uuid'in room else room.get('pilot'),'restroom_plan':room,'native_gate_pairs':gates,'lower_registered_fixed_routes':routes,'complete_native_part_states':states,'adjacent_full_BE':tags,'declared_boarding_position':[cx+2,-394,-221]})
(o/'survey.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
print('recipe',len(recipe['operations']),'mismatches',sum(not x['matches_source']for x in result['current_full_427_world_owner_comparison']))
for b in result['bays']:
 print('bay',b['variant'],'roomroute',b['restroom_plan'].get('route'),'goal',b['restroom_plan'].get('goal_centre'));print('fixed routes',[(x['id'],x.get('waypoints_for_native_refinement'))for x in b['lower_registered_fixed_routes']]);print('gatePairs',b['native_gate_pairs'])
