"""Join existing evidence without re-running or inflating its coverage claims."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/world_combat_r40'


def read(path):return json.loads((ART/path).read_text('utf8'))


def main():
    rows=[]
    def add(name,path,passed,scope):
        p=ART/path;rows.append(dict(name=name,passed=bool(passed),evidence=path,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),scope=scope))
    world=read('world_composition/composed.json');add('world_static_composition','world_composition/composed.json',not world['conflicts'],'Original owner state plus recorded static block/NBT changes')
    paths=json.loads((Path(world['destination'])/'quality_native_walk_results.json').read_text('utf8'))
    assert len(paths)==10327 and all(row['status']=='pass' for row in paths)
    add('registered_walks','reception_review/bypass_walk_results.json',all(r['status']=='pass' for r in read('reception_review/bypass_walk_results.json')),'9954 original registered routes +305 new pedestrian +68 receiving paths; last98 affected routes retested')
    lift=read('lifts_cold_without_debug_pass.json');add('cold_native_lifts','lifts_cold_without_debug_pass.json',not lift['error'] and all(t['passed'] for t in lift['trips']),'Native calls/rides after cold start, debug assistance disabled')
    for key in range(5):
        name='candidate' if key==1 else f'candidate_v{key}';path='phrase_candidate/'+name+'_result.json';r=read(path)
        add(f'normal_motion_variant_{key}',path,r['passed'] and len(r['cases'])==7,'Production player inputs and active Sachiel duel; original fleet identities preserved')
    for name in ['un0_nerv_final_regression','un1_offset_full_pass']:
        path='airlift/'+name+'.json';add(name,path,read(path)['passed'],'Original identity outbound/fallen recovery/intake and physical touchdown')
    path='envelopment_native_final/result.json';add('natural_awakening_to_finale',path,read(path)['passed'],'50HP silence/roar/protected feral combat → paired film → one death → control return')
    surface=max((ART/'native_surface_audit').glob('surface_*.json'),key=lambda p:p.stat().st_mtime)
    relative=surface.relative_to(ART).as_posix();add('native_surface_geometry',relative,read(relative)['passed'],'Actual submitted surface points against authored points in the same native draw')
    city=read('reception_review/city_status_nonblocking.json')
    add('city_status_nonblocking','reception_review/city_status_nonblocking.json',city['passed'],'Previously stalled station-board scene completes both faces and clean save; no remote chunk request in the periodic status refresh')
    current=json.loads((ROOT/'run/projectseele-local-maps/revision_r40.json').read_text())
    for name,digest in current['runtime_sha256'].items():assert hashlib.sha256((ROOT/'run/projectseele-local-maps'/name).read_bytes()).hexdigest()==digest
    photo_counts={state:len(list((ART/'reception_review'/('shader_'+state)).glob('*.png'))) for state in ['on','off']}
    assert photo_counts==dict(on=12,off=7),photo_counts
    out=dict(passed=all(r['passed'] for r in rows),checks=rows,world_changed_cells=world['changed_cells'],registered_native_routes=len(paths),
             new_facility_photos=photo_counts,previous_station_and_facility_photos=44,
             limits='Sampling/route catalogue and functional regressions; manual aesthetics, control feel and sound judgement remain with the user. WASAPI review audio reported capture discontinuities.')
    (ART/'native_acceptance.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),'utf8');print('R40 evidence joined',out['passed'],len(rows),'checks',flush=True)


if __name__=='__main__':main()
