"""Install a reversible future-chunk biome source with explicit authored reservations."""
from pathlib import Path
import argparse,copy,gzip,json
import nbtlib

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';OUT=ROOT/'artifacts/rebuild_r44/ecology'
def main(apply=False,configuration_file=None):
    if apply:
        from release_combat_r36 import guard
        guard()
    OUT.mkdir(exist_ok=True);plan=json.loads((WORLD/'regional_plan.json').read_text());bounds=[]
    # Bounds are x-min,z-min,x-max,z-max. Keep canopy clearance as well as soil clearance.
    for zone in plan['zones']:
        if zone.get('floor',-100)<0:continue
        x0,x1,z0,z1=zone['bounds'];bounds.append([x0-24,z0-24,x1+24,z1+24])
    bounds.extend([[-218,-28,278,468],[6220,-6550,6760,-5880],[1295,285,1640,680],[-2995,-1215,-2700,-955]])
    owners=json.loads((ROOT/'artifacts/repair_r43/facility_catalogue/authored_ownership.json').read_text())
    for b in owners['buildings']:
        lo,hi=b['planned_bounds'];bounds.append([lo[0]-20,lo[2]-20,hi[0]+20,hi[2]+20])
    # Actual surface rail cells protect tracks and bridge piers, including extensions not in the old plan.
    rail_tiles=set()
    with gzip.open(ROOT/'artifacts/repair_r43/object_inventory_v2/projectseele_geofront_cells.jsonl.gz','rt',encoding='utf8') as stream:
        for line in stream:
            row=json.loads(line)
            if row[1]>=60 and (row[4]=='rails' or row[3].partition('[')[0].startswith('mtr:rail')):rail_tiles.add((row[0]//16,row[2]//16))
    native=json.loads((ROOT/'artifacts/repair_r43/transit_resolved/native_snapshot.json').read_text())
    for curve in native['curves']:
        if curve['mode']!='TRAIN':continue
        for x,y,z in curve['points']:
            if y>=60:rail_tiles.add((int(x//16),int(z//16)))
    for x,z in rail_tiles:bounds.append([x*16-20,z*16-20,x*16+35,z*16+35])
    bounds=sorted({tuple(b) for b in bounds});level=nbtlib.load(WORLD/'level.dat');seed=int(level['Data']['WorldGenSettings']['seed'])
    configuration=dict(type='projectseele:regional_ecology',civil='projectseele:geofront_surface',meadow='projectseele:geofront_meadow',woodland='projectseele:geofront_woodland',highland='projectseele:geofront_highland',seed=seed,reserved_bounds=[list(b) for b in bounds])
    if configuration_file:
        configuration=json.loads(Path(configuration_file).read_text('utf8'));assert configuration['seed']==seed,'Job seed differs from actual world'
        bounds=configuration['reserved_bounds']
    (OUT/'biome_source.json').write_text(json.dumps(configuration,indent=2),'utf8')
    if apply:
        target=level['Data']['WorldGenSettings']['dimensions']['projectseele:geofront']['generator']
        assert str(target['biome_source']['type']) in {'minecraft:fixed','projectseele:regional_ecology'},'Existing ecology source must be reviewed before replacing'
        if not (OUT/'level.dat.before').exists():(OUT/'level.dat.before').write_bytes((WORLD/'level.dat').read_bytes())
        stamp=__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
        (OUT/('level.dat.before_'+stamp)).write_bytes((WORLD/'level.dat').read_bytes())
        (OUT/('biome_source.before_'+stamp+'.snbt')).write_text(target['biome_source'].snbt(),'utf8')
        target['biome_source']=nbtlib.Compound({k:nbtlib.Long(v) if k=='seed' else nbtlib.List[nbtlib.List[nbtlib.Int]]([nbtlib.List[nbtlib.Int](b) for b in v]) if isinstance(v,list) else nbtlib.String(v) for k,v in configuration.items()})
        pack_path=WORLD/'datapacks/tv_world_preview/data/projectseele/dimension/geofront.json'
        if pack_path.exists():
            pack=json.loads(pack_path.read_text('utf8'));assert pack['generator']['type']=='projectseele:geofront_bounded'
            (OUT/('dimension_datapack.before_'+stamp+'.json')).write_bytes(pack_path.read_bytes())
            pack['generator']['biome_source']=configuration
            pack_path.write_text(json.dumps(pack,ensure_ascii=False,indent=2),'utf8')
            (OUT/('dimension_datapack.after_'+stamp+'.json')).write_bytes(pack_path.read_bytes())
        level.save(WORLD/'level.dat')
    (OUT/'future_generation.json').write_text(json.dumps(dict(reservations=len(bounds),rail_tiles=len(rail_tiles),source_configuration=configuration,changed_existing_blocks=False,existing_chunk_retrofit='PENDING',validation='Fresh native registry/worldgen load pending'),indent=2),'utf8')
    print('Future ecology source:',len(bounds),'reservations;',len(rail_tiles),'surface railway tiles; existing ground not replaced')

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');a.add_argument('--configuration',type=Path);args=a.parse_args();main(args.apply,args.configuration)
