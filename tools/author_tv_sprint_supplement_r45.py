"""Isolated TV sprint study built from the installed, per-rig run take.

Never replaces production walk/run. The preview body redirects only its run
slot so an existing private viewer can inspect it. Shipping that preview is
forbidden; the separately named supplement still needs runtime integration.
"""
from pathlib import Path
import argparse,copy,hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R
from author_captured_arm_support_r45 import Pose


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def world_matrix(pose,name,matrix):
    parent=pose.rig[name].get('parent')
    local=np.linalg.inv(pose.matrix(parent))@matrix if parent else matrix
    rotation=R.from_matrix(local[:3,:3]);pivot=pose.pivots[name]
    pose.rot[name]=rotation
    pose.pos[name]=local[:3,3]-pivot+rotation.apply(pivot)
    pose.cache.clear()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--body',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();assert not a.out.exists();source=json.loads(a.body.read_text('utf8'))
    preview=copy.deepcopy(source);records=[]
    a.out.mkdir(parents=True)
    for variant in ('0','1','2'):
        profile=source['stance_clips_by_rig'][variant];original=profile['clips']['run']
        doc={'bones':profile['bones'],'rig_contract_r44':source['rigs'][variant]}
        clip=copy.deepcopy(original);poses=[Pose(doc,f)for f in original['frames']]
        arm_means={n:R.from_quat([pose.rot[n].as_quat()for pose in poses[:-1]]).mean()
                   for n in ('arm_l','arm_r')}
        changed=('torso_lower','torso_upper','leg_l','leg_r','arm_l','arm_r','head')
        rows=[]
        for index,(frame,prior) in enumerate(zip(clip['frames'],poses)):
            pose=Pose(doc,frame)
            head_world=R.from_matrix(pose.matrix('head')[:3,:3])
            # Legs are children of the lower torso on all three actual rigs.
            # Pitch the pelvis around its bilateral hip axis, then express
            # the unchanged leg world matrices in that new parent frame.
            # Merely retaining local leg angles would move both feet.
            legs={name:pose.matrix(name).copy()for name in ('leg_l','leg_r')}
            left,right=pose.point('leg_l'),pose.point('leg_r')
            centre=(left+right)*.5;axis=(right-left)/np.linalg.norm(right-left)
            delta=np.eye(4);delta[:3,:3]=R.from_rotvec(axis*np.radians(-8)).as_matrix()
            delta[:3,3]=centre-delta[:3,:3]@centre
            world_matrix(pose,'torso_lower',delta@pose.matrix('torso_lower'))
            for name,matrix in legs.items():world_matrix(pose,name,matrix)
            pose.rot['torso_upper']=R.from_euler('x',-10,degrees=True)*pose.rot['torso_upper']
            for name,mean in arm_means.items():
                excursion=(mean.inv()*pose.rot[name]).as_rotvec()
                pose.rot[name]=mean*R.from_rotvec(excursion*1.18)
            pose.cache.clear();pose.set_world_rotation('head',head_world)
            for name in changed:
                x,y,z,w=pose.rot[name].as_quat()
                frame['rotation_wxyz'][doc['bones'].index(name)]=[float(w),float(-x),float(-y),float(z)]
                if name in ('torso_lower','leg_l','leg_r'):
                    frame.setdefault('bone_position_xyz',{})[name]=(pose.pos[name]*[-1,1,1]*16).tolist()
            untouched=[n for n in doc['bones'] if n not in changed]
            assert all(frame['rotation_wxyz'][doc['bones'].index(n)]==original['frames'][index]['rotation_wxyz'][doc['bones'].index(n)]for n in untouched)
            assert frame['root_m']==original['frames'][index]['root_m']
            for name in doc['bones']:
                if name not in ('torso_lower','leg_l','leg_r'):
                    assert frame.get('bone_position_xyz',{}).get(name)==original['frames'][index].get('bone_position_xyz',{}).get(name)
            hips=(pose.point('leg_l')+pose.point('leg_r'))*.5
            shoulders=(pose.point('arm_l')+pose.point('arm_r'))*.5;direction=shoulders-hips
            rows.append({'frame':index,'trunk_lean_degrees':float(np.degrees(np.arctan2(-direction[2],direction[1]))),
                         'foot_position_change_body_blocks':max(float(np.linalg.norm(pose.point('foot_'+s)-prior.point('foot_'+s)))for s in ('l','r')),
                         'head_world_rotation_change_degrees':float(np.degrees((head_world.inv()*R.from_matrix(pose.matrix('head')[:3,:3])).magnitude()))})
        assert max(r['foot_position_change_body_blocks']for r in rows)<1e-10
        clip['source_style_r45']='TV12 sprint study; explicit authored torso/arm changes to installed run, not claimed extracted TV mocap'
        supplement={'schema':'projectseele.tv-sprint-supplement.r45.v1','rig_key':int(variant),
                    'rig_contract_r44':source['rigs'][variant],'bones':profile['bones'],'clips':{'tv_sprint':clip},
                    'source_body_sha256':sha(a.body),'reference':'https://www.youtube.com/watch?v=M_1XZ2K2fEE',
                    'observed_reference_times':[14.088236,14.328235,14.568234],
                    'authored_adaptation':{'lower_torso_extra_pitch_degrees':-8,'upper_torso_extra_pitch_degrees':-10,'upper_arm_excursion_scale':1.18},
                    'unchanged':'Original timing and complete lower-limb world motion; root/forearm/wrist/finger channels; normal walking and normal running resources. Local hip channels compensate the changed parent frame.',
                    'install_allowed':False,'native_passed':False,'art_accepted':False}
        path=a.out/f'eva_tv_sprint_supplement_{variant}.json';path.write_text(json.dumps(supplement,separators=(',',':')),'utf8')
        preview['stance_clips_by_rig'][variant]['clips']['run']=clip
        records.append({'rig':int(variant),'frames':len(rows),'supplement_sha256':sha(path),
                        'trunk_lean_range':[min(r['trunk_lean_degrees']for r in rows),max(r['trunk_lean_degrees']for r in rows)],'rows':rows})
    preview['tv_sprint_preview_only_r45']={'run_slot_redirected_for_private_viewer':True,'install_allowed':False,
                                        'do_not_publish_as_normal_run':True,'source_body_sha256':sha(a.body)}
    (a.out/'eva_body_tv_sprint_PREVIEW_ONLY.json').write_text(json.dumps(preview,separators=(',',':')),'utf8')
    (a.out/'receipt.json').write_text(json.dumps({'base':str(a.body.resolve()),'base_sha256':sha(a.body),
        'rigs':records,'world_written':False,'production_files_changed':False,'native_passed':False,'art_accepted':False,
        'remaining':['Whole torso/arm/leg surface self-contact and joint closure','Actual normal-to-sprint and braking transitions','Actual input/state integration separate from normal run','Three-rig native and artistic review']},indent=2),'utf8')
    print(json.dumps([{'rig':r['rig'],'frames':r['frames'],'lean_range':r['trunk_lean_range']}for r in records]))


if __name__=='__main__':main()
