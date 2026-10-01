"""Private DCC-to-runtime-format round trip; never installs a candidate.

World stage travel and yaw are removed exactly once from local pose channels.
The exported file is reopened through the established native-convention Pose
reader, then restored to the common stage for independent matrix comparison.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from scipy.spatial.transform import Rotation as R
from validate_combat_bundle_r44 import Pose

ROOT=Path(__file__).resolve().parents[1]
AXES=np.array([[1.,0,0],[0,0,-1],[0,1,0]])
MAP=np.eye(4);MAP[:3,:3]=AXES*5/16;INV=np.linalg.inv(MAP)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();out=args.out.resolve()
    fixture=json.loads((out/'fixture.json').read_text('utf8'));baked=json.loads((out/'baked_world_matrices.json').read_text('utf8'));roles={};expected={}
    for data in fixture['actors']:
        name=data['name'];bones=data['bones'];names=[b['name']for b in bones]
        geo=ROOT/'artifacts/rebuild_r44/network_runtime/private_resources/assets/projectseele/geo'/(name+'.geo.json')
        rig=json.loads(geo.read_text('utf8'))['minecraft:geometry'][0]['bones'];pivots={b['name']:np.asarray(b['pivot_model'])for b in bones};neutral={b['name']:np.asarray(b['neutral_model'])for b in bones};frames=[];desired=[];previous={}
        for row in baked:
            actor=row['actors'][name];stage=np.eye(4);stage[:3,:3]=R.from_euler('z',actor['yaw'],degrees=True).as_matrix();stage[:3,3]=actor['root'];stage_inv=np.linalg.inv(stage)
            world={n:INV@stage_inv@np.asarray(actor['deform'][n])@MAP@neutral[n]for n in names};qrows=[];offsets={}
            for bone in bones:
                n=bone['name'];parent=bone['parent'];local=np.linalg.inv(world[parent])@world[n]if parent else world[n]
                xyzw=R.from_matrix(local[:3,:3]).as_quat();wxyz=xyzw[[3,0,1,2]]*[1,-1,-1,1]
                if n in previous and wxyz@previous[n]<0:wxyz=-wxyz
                previous[n]=wxyz;qrows.append(wxyz.tolist());p=pivots[n];translation=local[:3,3]-p+local[:3,:3]@p;offsets[n]=(translation*[-1,1,1]).tolist()
            frames.append(dict(rotation_wxyz=qrows,bone_position_xyz=offsets,root_m=(np.asarray(offsets.pop('root'))/112).tolist(),stage_root_blocks=actor['root'],stage_yaw_degrees=actor['yaw']))
            desired.append(dict(stage=stage,world=world))
        roles[name]=dict(bones=names,rig_contract_r44=rig,frames=frames);expected[name]=desired
    target=out/'paired_runtime_pose_candidate.json';target.write_text(json.dumps(dict(schema='projectseele.private-paired-pose.r44',fps=30,roles=roles,scope='Private offline format comparison only. Not a FirstBattleClip or gameplay bundle; no loader installation.',root_authority='stage_root_blocks/stage_yaw_degrees are one world owner; pose channels contain no stage travel.'),separators=(',',':')),'utf8')
    loaded=json.loads(target.read_text('utf8'));samples=[];jumps=[]
    for name,role in loaded['roles'].items():
        rotations=np.asarray([f['rotation_wxyz']for f in role['frames']]);angles=np.degrees(2*np.arccos(np.clip(np.abs((rotations[1:]*rotations[:-1]).sum(2)),0,1)))
        for label,prefixes in [('hip-knee-ankle',('leg_','shin_','foot_')),('fingers',('finger_',)),('all',('',))]:
            idx=[j for j,n in enumerate(role['bones'])if n.startswith(prefixes)]
            if not idx:
                jumps.append(dict(actor=name,scope=label,status='NO_CHANNELS_IN_ACTUAL_RIG'));continue
            part=angles[:,idx];i,j=np.unravel_index(np.argmax(part),part.shape);jumps.append(dict(actor=name,scope=label,maximum_degrees_per_frame=float(part[i,j]),frame=int(i+2),bone=role['bones'][idx[j]]))
        for i,frame in enumerate(role['frames']):
            pose=Pose(role['rig_contract_r44'],role['bones'],frame);want=expected[name][i];maximum=0.;worst=''
            for n in role['bones']:
                error=float(np.max(np.abs(pose.matrix(n)-want['world'][n])))
                if error>maximum:maximum=error;worst=n
            samples.append(dict(actor=name,frame=i+1,matrix_error_model_units=maximum,worst_bone=worst))
    if 'source_motion_card' in fixture:
        source=fixture['source_motion_card'];provenance=dict(source_kind=source.get('source_kind','Actual ACCAD BVH full-body capture'),segments=source['segments'],source_license=source['source_license'],source_url=source['source_url'],source_finger_capture=False,authored_bridges=fixture.get('authored_target_bridges',[]))
    elif (out/'operator_receipt.json').exists():
        provenance=dict(source_kind='Actual ACCAD BVH full-body capture through pinned Rokoko offline operator',operator_receipt_sha256=hashlib.sha256((out/'operator_receipt.json').read_bytes()).hexdigest(),source_finger_capture=False,source_card='Source take identity remains in the saved source armature source_card_sha256; no boxing video is used in this candidate')
    else:provenance=dict(source_kind='data7 148 frames / data3 119 frames, 24 joints, no fingers')
    report=dict(export_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),maximum_matrix_error_model_units=max(x['matrix_error_model_units']for x in samples),samples=samples,continuity=jumps,
        chain=dict(original_capture=provenance,blender='actual saved armature + actual rigid/EVA or preserve-volume/Sachiel skin evaluator',export_reload='this independent runtime convention Pose reconstruction',native_runtime='UNVERIFIED; requires authorized root native queue',final_draw_vertices='UNVERIFIED; private rigid EVA proxy does not reproduce late seam stitching'),
        quality='No art/native/final-GPU acceptance inferred. Continuity and matrix errors only.')
    (out/'export_readback.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items()if k!='samples'},indent=2))


if __name__=='__main__':main()
