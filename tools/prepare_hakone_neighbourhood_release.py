"""Prepare verified neighbourhood recipes and the five terrain delivery entries."""
import argparse,json,shutil,zipfile
from pathlib import Path
from argparse import Namespace
from install_r53_carrier_trays import stopped_world
from prepare_hakone_network_recipes import parallel_recipes,field
from map_pipeline.verify_corridors import write_replay_expected
from native_transit_additions import inventory,assert_preserved

def prepare(a):
    resource='data/projectseele/worldgen/'
    if a.out.exists():raise ValueError('Choose a fresh release directory')
    for C in a.candidate:
        from verify_hakone_owakudani_release import require_verified
        require_verified(C)
        for name in('functional-check.json','independent-check.json'):
            if json.loads((C/name).read_text('utf8'))['errors']:raise ValueError('Unverified '+str(C/name))
        check=json.loads((C/'functional-check.json').read_text('utf8'))
        if check.get('native_geometry_requires_verified_migration'):
            from map_pipeline.native_geometry_patch import expected
            final,proof=expected(C)
            if proof['changed_members']==0:raise ValueError('Native geometry repair lacks its finite member migration')
            loaded=json.loads((C/'native-load-check.json').read_text('utf8'))
            if not loaded['service_and_vehicle_records_equal'] or loaded['new_path_gaps']:raise ValueError('Native engine load verification failed')
        stations=[r for r in json.loads((C/'plan/buildings.json').read_text('utf8'))if r.get('kind')=='station']
        if stations:
            r=json.loads((C/'station-access-check.json').read_text('utf8'))
            if r['errors']or len(r['stations'])!=len(stations):raise ValueError('Unverified station passenger connection')
    with stopped_world(a.world):
        for C in a.candidate:
            assert_preserved(a.world,inventory(C/'preserved-native'));parallel_recipes(Namespace(candidate=C,world=a.world,regions=None,workers=2))
        identity=a.candidate[0]/'identity-before';identity.mkdir();files=[a.world/'level.dat',a.world/'level.dat_old']+list((a.world/'playerdata').glob('*'))+list((a.world/'dimensions/projectseele/geofront/entities').glob('*.mca'));kept=[]
        for file in files:
            if not file.is_file():continue
            rel=file.relative_to(a.world);target=identity/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target);kept.append(rel.as_posix())
        (identity/'files.json').write_text(json.dumps(kept,indent=2),'utf8')
    previous=a.previous_field/'hakone_surface.bin.gz'
    for i,C in enumerate(a.candidate):
        write_replay_expected(C);dest=a.out/str(i);field(Namespace(plan=C/'plan',resource=previous,out=dest));previous=dest/'hakone_surface.bin.gz'
    shutil.copy2(previous,a.out/'hakone_surface.bin.gz')
    with zipfile.ZipFile(a.previous_field/'terrain-delivery.jar')as verified:
        (a.out/'hakone_surface_blend.bin.gz').write_bytes(verified.read(resource+'hakone_surface_blend.bin.gz'))
        with zipfile.ZipFile(a.out/'terrain-delivery.jar','x',compression=zipfile.ZIP_DEFLATED)as bundle:
            for name in('hakone_surface.bin.gz','hakone_surface_blend.bin.gz'):bundle.writestr(resource+name,(a.out/name).read_bytes())
            for suffix in('','$Field','$Surface'):
                name='com/projectseele/world/HakoneSurfaceField'+suffix+'.class';bundle.writestr(name,verified.read(name))
    for C in a.candidate:
        terrain=C/'terrain';terrain.mkdir();m=json.loads((C/'manifest.json').read_text('utf8'));m['terrain_inputs']={};m['preserve_native_members']=True
        for name in('hakone_surface.bin.gz','hakone_surface_blend.bin.gz'):shutil.copy2(a.out/name,terrain/name);m['terrain_inputs'][resource+name]='terrain/'+name
        (C/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),'utf8')
    print('Prepared',len(a.candidate),'verified neighbourhoods and five terrain delivery entries',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('world','previous-field','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--candidate',type=Path,action='append',required=True);prepare(p.parse_args())
