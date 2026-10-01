"""Prepare seed-independent shipped ecology and reversible source metadata.

This script edits source resources and ART metadata only. The parent is the
sole writer of level.dat and must apply the prepared biome source explicitly.
"""
from pathlib import Path
import json,math

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/ecology'

def main():
    source=json.loads((OUT/'biome_source.json').read_text('utf8'))
    plan=json.loads((ROOT/'run/saves/SEELE_FIELD_R44_REVIEW/regional_plan.json').read_text('utf8'))
    underground=[]
    for zone in plan['zones']:
        if zone.get('floor',80)>=0:continue
        x0,x1,z0,z1=zone['bounds'];underground.append([x0-24,z0-24,x1+24,z1+24])
    # Original HQ, hangars, lift/silo wells and transfer corridors precede the
    # regional_plan table; they are complete authored reservation components.
    underground.extend([[-218,-315,410,705],[-474,688,-226,844]])
    native=json.loads((ROOT/'artifacts/repair_r43/transit_resolved/native_snapshot.json').read_text('utf8'))
    tiles={(int(x//16),int(z//16)) for c in native['curves'] if c['mode']=='TRAIN' for x,y,z in c['points'] if y<60}
    underground.extend([[x*16-20,z*16-20,x*16+35,z*16+35] for x,z in sorted(tiles)])
    source['underground_reserved_bounds']=[list(r) for r in sorted({tuple(r) for r in underground})]
    (OUT/'biome_source.completed.json').write_text(json.dumps(source,indent=2),'utf8')
    dimension=ROOT/'src/main/resources/data/projectseele/dimension/geofront.json'
    data=json.loads(dimension.read_text('utf8'));shipped=dict(source);shipped.pop('seed')
    data['generator']['biome_source']=shipped;dimension.write_text(json.dumps(data,indent=2)+'\n','utf8')
    report=dict(shipped_source=str(dimension),fixed_world_seed_shipped=False,
        world_seed_policy='Default mosaic reads climate sampled from RandomState seeded by each world; installed measured saves use their actual level.dat seed.',
        surface_reservations=len(source['reserved_bounds']),underground_reservations=len(source['underground_reserved_bounds']),
        underground_virtual_rail_tiles=len(tiles),current_level_dat_changed=False,
        installation='Parent must install biome_source.completed.json with level.dat backup and full metadata inverse; native seed check is required.')
    (OUT/'source_completion.json').write_text(json.dumps(report,indent=2),'utf8');print(report,flush=True)

if __name__=='__main__':main()
