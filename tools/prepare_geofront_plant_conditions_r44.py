"""Freeze measured, FULL-chunk coordinates for a read-only server plant probe."""
from pathlib import Path
import argparse,json,hashlib,shutil
import numpy as np
import nbtlib
from measure_world_r40 import MeasuredWorld

ROOT=Path(__file__).resolve().parents[1]
STATES=['minecraft:oak_sapling[stage=0]','minecraft:birch_sapling[stage=0]',
        'minecraft:dandelion','minecraft:fern','minecraft:grass']

def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists();a.output.mkdir(parents=True)
    field=ROOT/'artifacts/rebuild_r44/city_expansion/geofront_tree_integrated_range_v5/corrected_heightfield.npz'
    d=np.load(field);x0,z0=map(int,d['origin']);world=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';w=MeasuredWorld(world)
    points=[('west_lowland',744,606),('north_ridge_lower',820,680),('north_ridge_upper',990,745),
            ('inter_ridge_valley',860,770),('south_ridge_lower',850,855),('south_ridge_upper',1010,890),
            ('eastern_transition',1060,760),('moved_tree_surround',884,752),('unaltered_west_edge',727,760)]
    request=[];measured=[]
    for name,x,z in points:
        y=int(d['after'][z-z0,x-x0]);assert y>-32768
        w.box((x,y-1,z),(x,y+4,z));request.extend([dict(name=name+'/soil',position=[x,y,z],states=['minecraft:grass_block[snowy=false]']),dict(name=name+'/plants',position=[x,y+1,z],states=STATES)])
    moved=json.loads((field.parent/'report.json').read_text('utf8'))['moved_small_vegetation']
    for n,r in enumerate(moved[:4]):
        x,y,z=r['pos'];q=[x,y+r['dy'],z];w.box((x,q[1]-1,z),(x,q[1]+3,z));request.append(dict(name='installed_moved_plant_'+str(n),position=q,states=[r['state']]))
    w.load()
    for row in request:
        x,y,z=row['position'];status=w.status.get((x//16,z//16));assert status=='full',(row,status)
        measured.append(dict(name=row['name'],position=row['position'],chunk=[x//16,z//16],chunk_status=status,
                             actual_source_profile=[dict(position=[x,Y,z],state=w.get(x,Y,z))for Y in range(y-1,y+4)]))
    request_path=a.output/'requested_server_plant_conditions.json';request_path.write_text(json.dumps(request,indent=2)+'\n','utf8')
    rules=nbtlib.load(world/'level.dat')['Data']['GameRules'];snapshot=a.output/'source_inputs';snapshot.mkdir();sources=[]
    for i,f in enumerate([Path(__file__),field,field.parent/'report.json',ROOT/'src/main/resources/data/projectseele/dimension_type/geofront.json',ROOT/'src/main/java/com/projectseele/GameEvents.java',ROOT/'src/main/java/com/projectseele/world/NativeGeofrontVegetationR44.java',ROOT/'src/main/java/com/projectseele/world/RegionalEcologyRetrofitR44.java']):
        target=snapshot/(str(i)+'_'+f.name);shutil.copy2(f,target);sources.append(dict(original_path=str(f.resolve()),path=str(target.resolve()),sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    report=dict(request=str(request_path.resolve()),request_sha256=hashlib.sha256(request_path.read_bytes()).hexdigest(),points=measured,
        disk_gamerules={k:str(rules[k])for k in ['randomTickSpeed','doDaylightCycle','doWeatherCycle','doVinesSpread']},
        runtime_gamerules_still_required=True,source_epochs=sources,world_written=False,native_passed=False,
        required_runtime_fields=['actual BLOCK light','actual SKY light','getMaxLocalRawBrightness at plant and above','sapling-above brightness >=9','grass-neighbor propagation raw brightness >=9 and source grass survival','canSurvive for each exact candidate state','actual chunk/block/entity ticking','current randomTickSpeed','dayTime/skyDarken/light-engine pending work'],
        interpretation='No growth is induced and no plant is placed by this probe. canSurvive alone is not sapling growth or grass spread. Dimension ambient .62 and shader brightness do not supply server light. Builders frozen by S20 markers are separate from vanilla random ticking; no randomTickSpeed override found in project source.')
    (a.output/'measured_full_chunk_source_proof.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf8')
    print('Read-only runtime plant request:',len(request),'samples; measured FULL chunks; no world write',flush=True)

if __name__=='__main__':main()
