"""Read-only R50 surface object audit and exact, reversible retirement candidates.

Uses the existing whole-object ownership and retirement ledgers. It never
opens a world for writing and does not equate sampled heights with acceptance.
"""
from pathlib import Path
from collections import Counter
import argparse,gzip,json,math,time
import numpy as np
from scipy.spatial import cKDTree
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities

ROOT=Path(__file__).resolve().parents[1]
DIM='projectseele:geofront'
SOIL={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel','minecraft:sand','minecraft:sandstone','minecraft:clay','minecraft:coarse_dirt','minecraft:rooted_dirt','minecraft:deepslate','minecraft:tuff','minecraft:andesite','minecraft:diorite','minecraft:granite'}
NATURAL=SOIL|{'minecraft:water','minecraft:lava','minecraft:snow','minecraft:powder_snow'}
R50_KEEP=[('new_yashima_hill',(-95,0,438,155,255,534)),('new_armor_column',(25,19,351,42,87,360)),
          ('marine_crew_path_a',(1415,0,588,1421,140,774)),('marine_crew_path_b',(1415,0,768,1520,140,774)),
          ('marine_recovery_crown',(1504,25,756,1534,129,786)),('marine_side_console',(1535,25,756,1546,129,780)),('private_service_vaults',(6,-443,-242,12,-437,-238)),
          ('city100_dynamic_reserve',(-210,0,-20,270,255,464)),('launch_surface_sweeps',(-65,0,-175,195,255,20))]

def load(path):
    path=Path(path)
    return json.load(gzip.open(path,'rt',encoding='utf8')) if path.suffix=='.gz' else json.loads(path.read_text('utf8'))
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
def bounds(points):return [[min(p[k]for p in points)for k in range(3)],[max(p[k]for p in points)for k in range(3)]]
def contains(box,q):return all(box[k]<=q[k]<=box[k+3]for k in range(3))
def basename(state):return state.partition('[')[0] if state else None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r49/surface_r50');args=ap.parse_args()
    world=args.world.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    catalogue=load(ROOT/'artifacts/repair_r43/facility_catalogue/catalogue.json')
    ownership=load(ROOT/'artifacts/rebuild_r44/city_buildings/actual_authored_ownership.json')
    physical=load(ROOT/'artifacts/repair_r43/facility_catalogue/physical_components.json.gz')
    surface_physical=[p for p in physical if p['dimension']==DIM and p['bounds'][1][1]>=0]
    regional=load(world/'regional_plan.json');native=load(world/'native_transit_r28.json')
    inventories=[]
    for row in regional['zones']:
        if row['kind']in {'district','airport','gateway','eva_plant'}:
            a,b,c,d=row['bounds'];inventories.append(dict(id=row['id'],kind=row['kind'],bounds=[[a,0,c],[b,255,d]],status='REGISTERED_CURRENT_USE_NOT_QUALITY_PASS',source='regional_plan.json'))
    for group in ('buildings','ships','nonstandard_height_objects'):
        for row in ownership.get(group,[]):
            inventories.append(dict(id=row.get('id',row.get('name',group)),kind=group,bounds=row.get('actual_building_bounds',row.get('planned_bounds',row.get('bounds',row.get('imported_bounds')))),status='KNOWN_OWNER_REQUIRES_CURRENT_FULL_QA',source='actual_authored_ownership.json'))
    for row in catalogue['stations']:
        if row['bounds'][1][1]>=0:inventories.append(dict(id='station/'+str(row['id']),kind='native_station',bounds=row['bounds'],status='ACTIVE_TRANSPORT_PROTECTED',source='facility_catalogue/catalogue.json'))
    for filename,key in [('r07_installations.json','entities'),('nerv_airport_r21.json','vehicles')]:
        for row in load(world/filename)[key]:
            point=row['position'];inventories.append(dict(id=row['key'],kind='original_equipment_or_vehicle',position=point,status='PRESERVE_SAVED_IDENTITY_AND_LIVE_MOTION_ENVELOPE',source=filename))
    for row in load(world/'un_hangars_r31.json')['hangars']:
        inventories.append(dict(id='un_hangar/'+str(row['serial']),kind='wet_cell_hangar',bounds=row['bounds'],status='ACTIVE_HANGAR_WET_DRY_DOOR_SWEEP_PROTECTED',source='un_hangars_r31.json'))
    for i,curve in enumerate(native['curves']):
        points=[p for p in curve['points']if p[1]>=0]
        if points:inventories.append(dict(id='native_curve/'+str(curve.get('id',i)),kind='native_curve/'+curve['mode'],bounds=bounds(points),status='CURRENT_TRANSPORT_TRACK_OR_AIRCRAFT_SWEPT_CORRIDOR_PROTECTED',source='native_transit_r28.json'))
    inventories.extend(dict(id=p['id'],kind='physical/'+p['kind'],bounds=p['bounds'],status='DISCOVERED_NOT_YET_CLASSIFIED',source='physical_components.json.gz')for p in surface_physical)
    write(out/'surface_object_inventory.json',dict(world=str(world),objects=inventories,counts=dict(Counter(r['kind']for r in inventories)),global_surface_quality_passed=False,world_written=False))
    generator_names={'TvWorldPreviewTerrain':'Fresh surface biome/noise adaptation plus underground dome; natural cliff severity is not automatically a defect',
        'TvWorldSurfaceLandscape':'Surface soil and planted features; ignores inside-city footprint',
        'CityRigidGenerationR45':'Complete saved Static/Ground chunk generation shards; candidate exact cells merge without replacing unmodified NBT',
        'ThirdTokyoSurfaceBuilder':'Legacy city surface builder; current invocation and protection require audit',
        'Tokyo3LandscapeBuilder':'Legacy designed city landscaping; current invocation requires audit',
        'RegionalEcologyRetrofitR44':'Finite ecology migration, protected construction ownership required',
        'RegionalBuildingQualityR44':'Existing authored exterior/interior lifecycle, complete active facilities protected',
        'GeoFrontBoundedChunkGenerator':'Current dimension generator and fresh chunk ordering',
        'GeoFrontFabricPlan':'Legacy fabric/road generation; positive surface invocation gate not yet classified'}
    producers=[]
    for name,role in generator_names.items():
        path=ROOT/'src/main/java/com/projectseele/world'/f'{name}.java'
        if path.exists():
            text=path.read_text('utf8');producers.append(dict(module=path.relative_to(ROOT).as_posix(),role=role,contains_world_write='setBlock' in text or 'setBlockState' in text,status='SOURCE_READ_NOT_FULL_LIFECYCLE_VERIFIED'))
    for name in ['build_regional_geometry.py','repair_regional_terrain.py','clean_quality_terrain_fragments.py','install_regional_transit.py','restore_retired_pier_terrain_r30.py','closed_surface_guard_admission_r46.py','compose_facility_generation_r49.py']:
        producers.append(dict(module='tools/'+name,role='Legacy construction or guarded source-recipe producer',status='EXISTING_SOURCE_REQUIRES_CURRENT_WORLD_ADMISSION'))
    write(out/'surface_generator_inventory.json',dict(producers=producers,exact_retirement_recipe='generation_recipe/file_patch.json',terrain_noise_or_all_old_tools_fixed=False,world_written=False))
    rails=np.asarray([p for curve in native['curves']if curve['mode']=='TRAIN'for p in curve['points']if p[1]>=0],float)
    tree=cKDTree(rails[:,[0,2]]) if len(rails)else None
    stations=[r['bounds']for r in catalogue['stations']if r['bounds'][1][1]>=0]
    buildings=[r.get('actual_building_bounds',r['planned_bounds'])for r in ownership['buildings']]
    def protection(q):
        for name,box in R50_KEEP:
            if contains(box,q):return name
        if q[1]>=0 and math.hypot(q[0]-1630,q[2]-685)<=118:return 'new_marine_basin'
        for box in buildings:
            if all(box[0][k]-1<=q[k]<=box[1][k]+1 for k in range(3)):return 'current_authored_building'
        for box in stations:
            if all(box[0][k]<=q[k]<=box[1][k]for k in range(3)):return 'active_native_station'
        if tree is not None:
            near=tree.query_ball_point([q[0]+.5,q[2]+.5],5)
            if any(rails[i,1]-6<=q[1]<=rails[i,1]+10 for i in near):return 'active_train_support_or_clearance'
        return None
    c1=load(ROOT/'artifacts/rebuild_r46/stations_terrain/C1_pier_whole_inventory_v3.json')['all_whole_components']
    retired=load(ROOT/'artifacts/rebuild_r44/surface_network/retired_component_readback.json')['objects']
    pits=load(ROOT/'artifacts/rebuild_r46/stations_terrain/surface_pit_survey_v2.json')['unclosed']
    w=MeasuredWorld(world)
    for row in c1:
        x0,y0,z0,x1,y1,z1=row['complete_declared_frame'];w.box((x0-3,max(0,y0-8),z0-3),(x1+3,min(255,y1+20),z1+3))
    for row in retired:
        for event in row['events']:w.around(event['pos'],2)
    for row in pits:w.around(row['seed'],5)
    w.load();print('Retirement and pit whole-object sections',len(w.tiles),'elapsed',round(time.monotonic()-started,1),flush=True)
    qlo=(min(x for x,z in w.selected)*16,0,min(z for x,z in w.selected)*16)
    qhi=((max(x for x,z in w.selected)+1)*16-1,255,(max(z for x,z in w.selected)+1)*16-1)
    bes=dict(iter_block_entities(world,DIM,qlo,qhi,selected_chunks=set(w.selected)))
    forward={};results=[]
    def natural_grade(x,z,low,high,original):
        central=None
        for y in range(high,low-1,-1):
            if basename(w.get(x,y,z))in SOIL:central=y;break
        if central is None:return None
        paving={'minecraft:smooth_stone','minecraft:smooth_stone_slab','minecraft:black_concrete','minecraft:white_concrete','projectseele:road_asphalt_slab','projectseele:road_marking_slab','minecraft:gravel'}
        for y in range(central+1,high+1):
            state=w.get(x,y,z);q=(x,y,z);name=basename(state)
            if state is None:return None
            if name in AIR or original.get(q)==state or name in {'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:snow'}or name.endswith(('_log','_leaves')):continue
            if name in paving and y<=central+2:continue
            return None
        heights=[]
        for dx,dz in [(-2,-2),(-2,0),(-2,2),(0,-2),(0,2),(2,-2),(2,0),(2,2)]:
            found=None
            for y in range(high,low-1,-1):
                state=w.get(x+dx,y,z+dz)
                if state is None:return None
                if basename(state)in SOIL and all(basename(w.get(x+dx,t,z+dz))in AIR|{'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:snow'}or basename(w.get(x+dx,t,z+dz)).endswith(('_log','_leaves'))or basename(w.get(x+dx,t,z+dz))in paving and t<=y+2 for t in range(y+1,high+1)):
                    found=y;break
            if found is None:return None
            heights.append(found)
        return central if max(abs(h-central)for h in heights)<=6 else None
    for row in c1:
        original={tuple(r['pos']):r['original_after']for r in row['original_constructed_owned_cells']}
        remaining={q:before for q,before in original.items()if w.block(q)==before}
        info=dict(id=row['id'],kind='retired_C1_whole_pier',bounds=[row['complete_declared_frame'][:3],row['complete_declared_frame'][3:]],original_owned_cells=len(original),actual_remaining_owned_cells=len(remaining),historic_status=row['status'],current_status='',evidence=[])
        if not remaining:info['current_status']='NO_ORIGINAL_COMPONENT_REMAINS'
        else:
            reasons=Counter(protection(q)for q in remaining if protection(q));nbt=[q for q in original if q in bes]
            if reasons:info['current_status']='ACTIVE_OWNER_REUSED_COMPONENT_RETAINED';info['protected_owners']=dict(reasons)
            elif nbt:info['current_status']='FULL_NBT_OWNER_RETAINED';info['nbt_positions']=nbt
            else:
                frame=row['complete_declared_frame'];x,z=frame[0],frame[2]
                grade=natural_grade(x,z,max(0,frame[1]-8),min(255,frame[4]+20),original)
                foreign=[]
                for q,expected in original.items():
                    current=w.block(q)
                    if current is None or current!=expected and basename(current)not in SOIL|AIR:foreign.append(dict(pos=q,state=current))
                if foreign:info['current_status']='COMPLETE_FRAME_NEW_USE_UNCLASSIFIED';info['evidence']=foreign
                elif grade is None:info['current_status']='NATURAL_GRADE_OR_UPSTREAM_USE_REQUIRES_COMPLETE_REVIEW'
                else:
                    info['current_status']='EXACT_WHOLE_RETIREMENT_CANDIDATE';info['measured_natural_grade']=grade;info['evidence']=[dict(pos=q,before=s)for q,s in remaining.items()]
                    for q,before in remaining.items():
                        after='minecraft:air'if q[1]>grade else 'minecraft:grass_block[snowy=false]'if q[1]==grade else 'minecraft:dirt'if q[1]>=grade-3 else 'minecraft:stone'
                        forward[q]=dict(pos=q,before=before,after=after,owner=row['id'],reason='Retired original route; complete original pier mask and actual surviving natural centre grade verified; preserve current paving, plants and eight surrounding natural grades',before_nbt=None,after_nbt=None)
        results.append(info)
    for row in retired:
        remain=[];changed=[]
        for event in row['events']:
            q=tuple(event['pos']);current=w.block(q)
            if current==event['before']:remain.append(dict(pos=q,state=current,protection=protection(q),full_nbt=q in bes))
            elif current not in AIR:changed.append(dict(pos=q,state=current,protection=protection(q),full_nbt=q in bes))
        results.append(dict(id=row['id'],kind='retired_recorded_tunnel_or_rail',bounds=row['bounds'],complete_recorded_cells=row['complete_recorded_component_cells'],current_status='RECORDED_RETIREMENT_MASK_CLEAR'if not remain else 'OLD_SOURCE_REMAINS_NEEDS_COMPLETE_COMPONENT_RECONCILIATION',remaining=remain,new_use=changed))
    pit_results=[]
    for row in pits:
        x,y,z=row['seed'];column=[dict(pos=[x,t,z],state=w.get(x,t,z),full_nbt=(x,t,z)in bes)for t in range(y-5,y+4)]
        pit_results.append(dict(seed=row['seed'],historic_reason=row['reason'],protected_owner=protection((x,y,z)),actual_column=column,current_status='FUNCTION_AND_COMPLETE_BOUNDARY_REVIEW_REQUIRED'))
    rows=list(forward.values())
    for name,content in [('forward.jsonl.gz',rows),('inverse.jsonl.gz',[dict(r,before=r['after'],after=r['before'])for r in rows])]:
        with gzip.open(out/name,'wt',encoding='utf8',newline='\n')as stream:
            for row in content:stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
    write(out/'retirement_readback.json',dict(world=str(world),objects=results,counts=dict(Counter(r['current_status']for r in results)),world_written=False,global_retirement_passed=False))
    write(out/'surface_pit_readback.json',dict(world=str(world),objects=pit_results,world_written=False,global_pits_passed=False))
    write(out/'patch_contract.json',dict(schema=50,world=str(world),dimension=DIM,objects=[r['id']for r in results if r['current_status']=='EXACT_WHOLE_RETIREMENT_CANDIDATE'],rows=len(rows),world_written=False,source_written=False,native_verified=False,visual_verified=False,protected=R50_KEEP,only_root_may_apply=True,required_readback='Every exact before state and complete NBT must still match; an object with any mismatch is excluded whole, never partially applied'))
    if rows:
        from prepare_facilities_r48 import Author
        author=Author(world,out)
        for row in rows:author.all[tuple(row['pos'])]=row
        author.recipe()
        write(out/'metadata_patch.json',dict(schema=50,operations=[],world_written=False))
    print('Read-only R50 objects',len(inventories),'C1/tunnel components',len(results),'pits',len(pit_results),'exact retirement candidate cells',len(rows),'elapsed',round(time.monotonic()-started,1),flush=True)
if __name__=='__main__':main()
