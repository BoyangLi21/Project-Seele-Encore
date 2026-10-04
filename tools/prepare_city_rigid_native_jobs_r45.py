"""Prepare exact real96 native jobs without launching Minecraft or editing a world."""
from pathlib import Path
import argparse,hashlib,json
import nbtlib

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--world',type=Path,default=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW')
    parser.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r45/city_motion/real_city_native_jobs_v1');args=parser.parse_args()
    world=args.world.resolve();out=args.out.resolve();assert world.name=='SEELE_FIELD_R45_REVIEW'and not out.exists();out.mkdir(parents=True)
    identity=str(nbtlib.load(world/'dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat')['data']['WorldUUID'])
    seed=int(nbtlib.load(world/'level.dat')['Data']['WorldGenSettings']['seed'])
    suite=[('actual_restore_all96','travel',False,True,0,312),('actual_retract_all96','travel',True,True,312,0),
        ('actual_interrupt_restore','interrupt',False,True,0,312),('actual_cold_resume_restore','resume',False,False,0,None)]
    rows=[]
    for name,mode,retract,request,endpoint,start in suite:
        common=dict(world=str(world),world_seed=seed,world_id=identity)
        control=dict(schema='projectseele.actual96-native-control-job-r45.v1',**common,enable_native_district=True,request_on_start=request,retract=retract,
            actual_existing_structures=True,helper_replacement=False,requires_installed_native_verified_topology=True,expected_source_endpoint=start)
        quality=dict(schema='projectseele.actual96-native-quality-job-r45.v1',**common,mode=mode,endpoint_depth=endpoint,
            witness_indices=[43,64],checkpoint_motion_tick=100,timeout_ticks=24000,stop_server_when_done=True,
            output=str(out/(name+'_result')),actual_existing_structures=True,helper_replacement=False)
        if mode=='resume':quality['checkpoint_report']=str(out/'actual_interrupt_restore_result/checkpoint.json')
        c=out/(name+'.control.json');q=out/(name+'.quality.json');c.write_text(json.dumps(control,indent=2),'utf8');q.write_text(json.dumps(quality,indent=2),'utf8')
        props=['-Dprojectseele.nativeReviewWorld=SEELE_FIELD_R45_REVIEW',f'-Dprojectseele.r45CityCreateDistrict={c.as_posix()}',f'-Dprojectseele.r45CityRigidQuality={q.as_posix()}']
        rows.append(dict(name=name,control=str(c),quality=str(q),properties=props,
            precondition='Root exact topology+archive migration installed first; current stable depth'+str(start)if start is not None else'Normal save/close after the exact checkpoint, same world and existing96 owner UUIDs',
            no_surrogate_source=True,control_sha256=hashlib.sha256(c.read_bytes()).hexdigest(),quality_sha256=hashlib.sha256(q.read_bytes()).hexdigest()))
    report=dict(schema='projectseele.real-city-native-suite-r45.v1',world_written=False,mc_launched=False,build_invoked=False,
        production_default_enabled=False,source_objects=96,largest_actual_index=43,noncore_actual_index=64,
        largest_original_cargo_cells=19381,largest_after_floor_migration=19382,noncore_original_cargo_cells=6078,
        phase_order=['actual_restore_all96','actual_retract_all96','actual_interrupt_restore','actual_cold_resume_restore'],jobs=rows)
    (out/'suite.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
