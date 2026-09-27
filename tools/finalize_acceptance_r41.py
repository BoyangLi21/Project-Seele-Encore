"""Gate R41 adoption on exact motion, spatial and real mechanism evidence."""
from pathlib import Path
import hashlib,json
import numpy as np

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41'


def read(name):return json.loads((ART/name).read_text('utf8'))


def main():
    spatial=read('spatial_acceptance.json');assert spatial['passed']
    source=ART/'stance_candidate/eva_body_r41.json';digest=hashlib.sha256(source.read_bytes()).hexdigest()
    motion=read('accepted_motion_runs.json');assert {r['name'] for r in motion}=={'contacts','pose0','pose2','rifle','normal','recovery'}
    assert all(r['passed'] and not r['exit'] and r['body_sha256']==digest for r in motion)
    duel=read('final_duel_result.json');assert duel['passed'] and any(r['name']=='continuous_live_duel' and r['passed'] for r in duel['cases'])
    performance=read('performance_result.json');assert performance['passed']
    lifts=read('lifts_final_result.json');assert not lifts['error'] and len(lifts['trips'])==3 and all(r['passed'] for r in lifts['trips'])
    sortie=read('sortie_release_result.json');assert sortie['pass'] and sortie['original_eva_and_plug_recovered'] and sortie['return_bridge_floor_rebuilt']
    # The latest TV palm correction leaves the two UN transforms identical to
    # their already-rendered native candidates (only unused contact tags vary).
    a=json.loads(source.read_text('utf8'));b=read('stance_candidate/before_tv_palm_mirror/eva_body_r41.json')
    for key in ('3','4'):
        assert a['rigs'][key]==b['rigs'][key]
        for name,clip in a['stance_clips_by_rig'][key]['clips'].items():
            old=b['stance_clips_by_rig'][key]['clips'][name]
            for f,g in zip(clip['frames'],old['frames']):
                for field in ('rotation_wxyz','root_m'):assert np.allclose(f[field],g[field],rtol=0,atol=1e-10)
                assert f.get('bone_position_xyz',{})==g.get('bone_position_xyz',{})
    assert read('final_pose_3_result.json')['passed'] and read('hand_baked_4_result.json')['passed']
    cases=read('accepted_motion_contacts_result.json')['stance_r41'];assert all(r['passed'] for r in cases['contact_cases'])
    report=dict(passed=True,body_sha256=digest,spatial=spatial,motion_runs=motion,close_contacts=cases['contact_cases'],
                un_native_geometry_equivalent=True,normal_duel=duel['cases'],lift_trips=lifts['trips'],
                three_original_sorties=True,original_player_unit_recovered=True,
                performance_without_capture=dict(media=performance['media'],scope='Fixed native arena, shader enabled, diagnostic bone dumps and image readback disabled; not a whole-world FPS guarantee'),
                owner_world_progress_copied_from_review=False,visual_acceptance='Actual native images reviewed; final aesthetic and control-feel acceptance remains with the owner')
    (ART/'native_acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('R41 acceptance gate complete',flush=True)


if __name__=='__main__':main()
