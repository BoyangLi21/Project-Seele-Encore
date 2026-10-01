"""Read actual authored fist/feet against the canonical opponent task plane."""
from pathlib import Path
import argparse,json
import numpy as np


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();out=args.out
    fixture=json.loads((out/'fixture.json').read_text('utf8'))['actors'][0];baked=json.loads((out/'baked_world_matrices.json').read_text('utf8'))
    receipt=json.loads((out/'contact_pass_receipt.json').read_text('utf8'))['records'];segments=json.loads((out/'fixture.json').read_text('utf8'))['source_motion_card']['segments']
    points=np.asarray(fixture['vertices']);ids=np.asarray(fixture['influences']);weights=np.asarray(fixture['weights']);owner=ids[np.arange(len(ids)),weights.argmax(axis=1)];names=[b['name']for b in fixture['bones']];rows=[]
    for segment in segments:
        if segment['label']=='guard':continue
        selected=[i for i,r in enumerate(receipt)if r['raw_frame']is not None and segment['candidate_frames'][0]<=r['raw_frame']<=segment['candidate_frames'][1]]
        index=int(round(segment['runtime_contact_phase']*(len(selected)-1)));frame=selected[index];pose=baked[frame]['actors'][fixture['name']]['deform'];feet={};patches=[]
        for side in('l','r'):
            matrix=np.asarray(pose['foot_'+side]);boot=np.asarray(fixture['toes'][side]['vertices']);actual=boot@matrix[:3,:3].T+matrix[:3,3];minimum=actual[:,2].min();patch=actual[actual[:,2]<=minimum+.08]
            feet[side]=dict(actual_bottom_world_z=float(minimum),actual_low_patch_world_centre=patch.mean(axis=0).tolist(),source_contact=receipt[frame]['source_contacts']['foot_'+side]);patches.append(patch.mean(axis=0))
        centre=np.mean(patches,axis=0);side=segment['leading_side'];hand='hand_'+side;shape=[]
        for bone in names:
            if bone==hand or bone.startswith('finger_')and bone.endswith('_'+side):
                raw=points[owner==names.index(bone)];matrix=np.asarray(pose[bone]);shape.append(raw@matrix[:3,:3].T+matrix[:3,3])
        actual=np.concatenate(shape);forward=actual[:,1].max();fist=actual[actual[:,1]>=forward-.025].mean(axis=0);delta=fist-centre
        row=dict(clip=segment['label'],author_frame=frame+1,actual_closed_fist_forward_surface_world=fist.tolist(),actual_both_boot_patch_centre_world=centre.tolist(),
            actual_target_vector_from_foot_support_world=delta.tolist(),actual_target_horizontal_heading_degrees=float(np.degrees(np.arctan2(delta[0],delta[1]))),
            left_right_actual_feet=feet,source_task_frame=segment.get('world_task_frame_r44'),
            canonical_opponent_task_plane=dict(forward_axis_world=[0,1,0],normal_world=[0,-1,0],origin_world=[centre[0],fist[1],fist[2]],
                lateral_fist_offset_blocks=float(fist[0]-centre[0]),scope='Authored shared target plane only; no opponent mesh/contact/impact is present in this single-actor scene'))
        rows.append(row)
    (out/'actual_task_plane_hand_foot_readback.json').write_text(json.dumps(dict(rows=rows,native_contact_verified=False,artistic_acceptance=False,
        scope='Actually authored whole mesh matrices and closed fist/boots. Native actor world yaw, actual receiver surface and damage must be joined by shared draw/backend witnesses.'),indent=2),'utf8')
    print(json.dumps([{k:r[k]for k in('clip','author_frame','actual_target_horizontal_heading_degrees','canonical_opponent_task_plane')}for r in rows],indent=2))


if __name__=='__main__':main()
