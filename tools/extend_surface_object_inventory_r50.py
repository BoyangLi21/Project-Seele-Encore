"""Add current 48 authored buildings and 100 actual moving-city owners to R50.

Uses original current-source metadata and the actual installed topology NBT;
neither an inventory entry nor a bounding frame is a physical quality pass.
"""
from pathlib import Path
from collections import Counter
import argparse,json
import nbtlib

ROOT=Path(__file__).resolve().parents[1]
def unpack(n):
    n=int(n)&((1<<64)-1);x=n>>38;z=(n>>12)&((1<<26)-1);y=n&4095
    return x-(1<<26)if x>=(1<<25)else x,y-4096 if y>=2048 else y,z-(1<<26)if z>=(1<<25)else z

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);args=ap.parse_args();out=ROOT/'artifacts/rebuild_r49/surface_r50';inventory=json.loads((out/'surface_object_inventory.json').read_text('utf8'));objects=inventory['objects'];seen={o['id']for o in objects}
    catalogue=ROOT/'artifacts/rebuild_r45/city_entrances_sol_followup/native_241_building_catalogue.json';d=json.loads(catalogue.read_text('utf8'));cache={};newrows=[r for r in d['buildings']if not r['original']];assert len(newrows)==48
    for r in newrows:
        if r['id']in seen:continue
        p=Path(r['current_source']);source=cache.setdefault(str(p),json.loads(p.read_text('utf8')));row=next(b for b in source['buildings']if b['id']==r['id']);x0,z0,x1,z1=row['bounds'];floor=int(row['floor']);roof=int(row['roof'])
        objects.append(dict(id=r['id'],kind='current_additional_authored_building',bounds=[[x0,floor-3,z0],[x1,roof+4,z1]],status='CURRENT_NAMED_SOURCE_OWNER_PROTECTED_NOT_QA_PASS',source=str(p),current_241_catalogue=str(catalogue),declared_floor_feet=r['declared_floor_feet']));seen.add(r['id'])
    path=next((args.world.resolve()/'dimensions/projectseele/geofront/data').glob('projectseele_city_rigid_topology_r45_*.dat'));topology=nbtlib.load(path)['data'];assert str(topology['Stage'])=='INSTALLED'and len(topology['Towers'])==100
    for index,tower in enumerate(topology['Towers']):
        ident=f'current_city_rigid_tower/{index}'
        if ident in seen:continue
        x,y,z=unpack(tower['Centre']);foot=tower['Footprint'];base=int(tower['RetractedBaseY']);height=int(tower['Height'])
        objects.append(dict(id=ident,kind='current_city100_dynamic_sweep_owner',bounds=[[x+int(foot['MinX']),base,z+int(foot['MinZ'])],[x+int(foot['MaxX']),y+height,z+int(foot['MaxZ'])]],status='ACTUAL_INSTALLED_DYNAMIC_OWNER_PROTECTED_NOT_MOTION_QA_PASS',source=str(path),surface_centre=[x,y,z],retracted_base_y=base));seen.add(ident)
    inventory.update(objects=objects,counts=dict(Counter(r['kind']for r in objects)),current_ordinary_named_buildings=241,current_movable_city_towers=100,inventory_is_not_physical_quality_acceptance=True)
    (out/'surface_object_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),'utf8')
    producers=json.loads((out/'surface_generator_inventory.json').read_text('utf8'));producers['current_runtime_source_chain']=['GeoFrontBoundedChunkGenerator.fillFromNoise: TvWorldPreviewTerrain.shape only establishes fresh terrain.', 'GeoFrontBoundedChunkGenerator.applyBiomeDecoration: native ecology runs before CityRigidGenerationR45.apply.', 'CityRigidGenerationR45.load binds actual installed topology WorldUUID/GenerationFolder; apply returns for FULL chunks.', 'Exact candidate complete Static shards are the final owned source for retired C1 cells; unmodified Static/Ground and palette prefixes are preserved.', 'ThirdTokyoSurfaceBuilder.build/ensure and Tokyo3LandscapeBuilder.build defer to current CityRigidTopologyR45 / CityLegacyOwnershipR48 owner; regional quality/ecology writers require explicit construction JOB properties.']
    producers['all_old_python_builders_replayed_or_verified']=False;producers['retirement_static_shard_sync_verified']='candidate_exact_readback.json';(out/'surface_generator_inventory.json').write_text(json.dumps(producers,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(inventoried_objects=len(objects),ordinary_named=241,actual_moving_city=100,world_written=False)))

if __name__=='__main__':main()
