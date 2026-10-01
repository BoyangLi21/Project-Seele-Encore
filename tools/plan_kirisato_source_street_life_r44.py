"""Private source-only street-life delta on frozen K35. No live-world reader."""
from pathlib import Path
from collections import Counter
import argparse,gzip,json,math,hashlib,shutil
import numpy as np
from scipy.spatial import cKDTree

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r44/city_expansion/kirisato_whole_joined_shores_v35'
IRON='minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]'

def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists();a.output.mkdir(parents=True)
    contract=json.loads((BASE/'construction_contract_refrozen_v2.json').read_text('utf8'))
    shapes_path=next(Path(e['path'])for e in contract['source_epochs']if 'run/saves/'in e['original_path'].replace('\\','/')and e['original_path'].endswith('native_collision_shapes.json'))
    shapes=json.loads(shapes_path.read_text('utf8'))
    baseline={tuple(r['pos']):r['after']for r in map(json.loads,gzip.open(BASE/'forward.jsonl.gz','rt',encoding='utf8'))}
    district=json.loads((BASE/'new_district.json').read_text('utf8'))
    roads=json.loads((BASE/'road_authority.json').read_text('utf8'))['columns'];road_coords=np.array([r['pos']for r in roads]);road_tree=cKDTree(road_coords)
    parcels=json.loads((BASE/'parcel_ground_plan.json').read_text('utf8'))['columns']
    candidates=[]
    for r in parcels:
        if not r['role'].startswith('graded_'):continue
        x,z=r['pos'];feet=int(r['feet'])
        # Only use positively known source-cleared AIR and known source grass.
        # No absence-as-AIR, surface-based occupancy guess, or live-world read.
        if baseline.get((x,feet-1,z))!='minecraft:grass_block[snowy=false]':continue
        if any(baseline.get((x,feet+y,z))!='minecraft:air'for y in range(6)):continue
        distance,index=road_tree.query([x,z]);neighbour=roads[int(index)]
        if not 2<=distance<=7 or abs(feet-neighbour['native_feet'])>3:continue
        candidates.append(dict(pos=[x,feet,z],road_distance=float(distance),road=neighbour['pos'],road_feet=neighbour['native_feet'],owner=r['owner']))
    chosen=[];unserved=[];claimed=set()
    for b in district['buildings']:
        ex,ey,ez=b['entry'];bounds=b['bounds'];pairs=[]
        for side in [-1,1]:
            target=[bounds[0]-5 if side<0 else bounds[2]+5,ez]
            eligible=[r for r in candidates if math.dist([r['pos'][0],r['pos'][2]],[ex,ez])<65 and all(math.dist([r['pos'][0],r['pos'][2]],[s['pos'][0],s['pos'][2]])>=14 for s in chosen+pairs)]
            if not eligible:continue
            pick=min(eligible,key=lambda r:math.dist([r['pos'][0],r['pos'][2]],target)+r['road_distance']*2);pick=dict(pick,serves=b['id'],role='Court/road-edge safety luminaire on known dry source-clearance outside whole public pavement');pairs.append(pick)
        if not pairs:unserved.append(b['id'])
        chosen+=pairs
    rows=[];components=[]
    for index,r in enumerate(chosen):
        x,feet,z=r['pos'];rx,rz=r['road'];dx,dz=rx-x,rz-z
        facing=('east'if dx>0 else'west')if abs(dx)>=abs(dz)else('south'if dz>0 else'north')
        head=f'projectseele:street_light_head[facing={facing}]';assert IRON in shapes and head in shapes
        cells=[]
        # Bolted narrow metal pole sits directly on the complete rooted soil;
        # it never replaces pavement or narrows the retained 3m approach.
        for height in range(6):
            q=x,feet+height,z;after=head if height==5 else IRON;before=baseline[q]
            rows.append(dict(pos=q,before=before,after=after,before_nbt=None,after_nbt=None,owner='r44/kirisato/street_life/lamp_'+str(index),reason='Known-clear source-only court safety lamp; five-metre slender pole, existing real emitting luminaire, outside whole pavement/entrance spine'))
            cells.append(dict(pos=q,state=after))
        components.append(dict(id='lamp_'+str(index),**r,whole_cells=cells,native_shapes_from=str(shapes_path),source_light_emission=15,
            actual_world_before_still_requires_root_after_K35=True))
    assert len(rows)==len({tuple(r['pos'])for r in rows})
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
            for row in sorted(rows,key=lambda r:r['pos']):
                r=dict(row)
                if inverse:r['before'],r['after']=r['after'],r['before']
                f.write(json.dumps(r,ensure_ascii=False)+'\n')
    reference=dict(primary_sources=[dict(url='https://www.ur-net.go.jp/rd_portal/pnf/ing_report_d/lrmhph000000jlij-att/ing_den.pdf',
        evidence='UR official housing-component history: concrete-pole outdoor lights, then manufacturer mercury/downward-open luminaires from late Showa40s; tall poles combined with lower approach lighting. Modern LED paragraph is not used as 1990s evidence.'),
        dict(url='https://www.ur-net.go.jp/rd_portal/archive/safety_k01.html',evidence='Lighting is coordinated with circulation/landscape and different functional zones; modern examples are not claimed as TV-era photographs.'),
        dict(url='https://smallworlds.jp/area/eva_tokyo/',evidence='Official licensed miniature area identifies Rei housing; secondary interpretation only, not TV settei.')],
        engineering_inference='Five-metre metal security poles at court/road-edge joints, existing downward luminaire, no fake light blocks. Exact sizes and locations are game construction choices. This source-clear subset is not the complete district street-life scope.')
    (a.output/'street_life_components.json').write_text(json.dumps(dict(components=components,missing_building_zone_lamps=unserved,source_known_clear_candidates=len(candidates),
        unchanged_K35_geometry=True,live_world_read=False,world_written=False,source_known_before_passed=True,root_after_K35_exact_preconditions_required=True,
        native_passed=False,visual_passed=False,reference=reference,
        pending=['Whole coherent green/court seating and utility-line system, gallery entrances and living fixtures','Actual post-K35 world before/NBT preflight by Root','Native lamp emitted-light / head traits and full road/approach clearance verification','Whole standing/night/day native views']),ensure_ascii=False,indent=2),'utf8')
    snapshots=a.output/'source_inputs';snapshots.mkdir()
    for i,path in enumerate([Path(__file__),BASE/'construction_contract_refrozen_v2.json',BASE/'forward.jsonl.gz',BASE/'parcel_ground_plan.json',BASE/'road_authority.json',shapes_path,ROOT/'src/main/java/com/projectseele/world/StreetLightHeadBlock.java',ROOT/'src/main/resources/assets/projectseele/models/block/street_light_head.json']):shutil.copy2(path,snapshots/(str(i)+'_'+path.name))
    print('Source-only street life:',len(components),'real emitting lamps;',len(rows),'exact source-before delta cells;',len(unserved),'zones still need sites; no world read/write',flush=True)

if __name__=='__main__':main()
