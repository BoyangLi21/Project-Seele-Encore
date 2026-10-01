"""Read actual native sole extrema at each recorded pose layer.

Independent diagnostic only: no Java, source motion or runtime asset writes.
"""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from validate_combat_bundle_r44 import Pose

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--native',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--profile',type=Path);ap.add_argument('--stage-prefix',default='normal_');args=ap.parse_args()
    file=args.native/'body_layers_r40.json';samples=json.loads(file.read_text('utf8'))['samples']
    points={(v,s):np.load(ROOT/f'artifacts/rebuild_r44/combat/runtime_hands_basis/actual_foot_points/variant_{v}_foot_{s}.npy')for v in range(5)for s in('l','r')}
    profile=json.loads(args.profile.read_text('utf8'))if args.profile else None
    rows=[];selection=[]
    for sample in samples:
        if not sample['stage'].startswith(args.stage_prefix):continue
        layers={}
        for layer,bones in sample['layers'].items():
            sole={}
            for side in('l','r'):
                matrix=np.asarray(bones['foot_'+side]['matrix']).reshape(4,4).T
                posed=points[(sample['variant'],side)]@matrix[:3,:3].T+matrix[:3,3]
                sole[side]=dict(minimum_y_blocks=float(posed[:,1].min()*5),centroid_blocks=(posed.mean(axis=0)*5).tolist())
            layers[layer]=dict(soles=sole,root_position=bones['root']['position_blocks'],root_quaternion=bones['root']['quaternion_xyzw'])
        changes=[];order=list(layers)
        for a,b in zip(order,order[1:]):
            for s in('l','r'):
                delta=layers[b]['soles'][s]['minimum_y_blocks']-layers[a]['soles'][s]['minimum_y_blocks']
                if abs(delta)>.05:changes.append(dict(before=a,after=b,side=s,delta_blocks=delta))
        rows.append(dict(stage=sample['stage'],tick=sample['tick'],review_tick=sample['review_tick'],partial=sample['partial'],ordinary=sample['ordinary'],ordinary_phase=sample['ordinary_phase'],heavy_phase=sample['heavy_phase'],layers=layers,changes=changes))
        if profile is not None:
            label=('jab','cross','hook')[min(2,sample['ordinary'])]if sample['ordinary']>=0 else 'heavy'if 0<sample['heavy_phase']<1 else None
            phase=sample['ordinary_phase']if sample['ordinary']>=0 else sample['heavy_phase']
            if label and phase>=.18:
                names=('root','leg_l','leg_r','shin_l','shin_r','foot_l','foot_r');actual=Rotation.from_quat([sample['layers']['authored'][n]['quaternion_xyzw']for n in names]);matches=[]
                for key,clip in profile['clips'].items():
                    if not key.endswith('_'+label):continue
                    at=phase*(len(clip['frames'])-1);lo=int(at);hi=min(lo+1,len(clip['frames'])-1);u=at-lo
                    frame=dict(rotation_wxyz=[],bone_position_xyz={},root_m=(np.array(clip['frames'][lo]['root_m'])*(1-u)+np.array(clip['frames'][hi]['root_m'])*u).tolist())
                    for n in profile['bones']:
                        ix=profile['bones'].index(n);a=clip['frames'][lo]['rotation_wxyz'][ix];b=clip['frames'][hi]['rotation_wxyz'][ix];xyzw=Slerp([0,1],Rotation.from_quat([np.array(a)[[1,2,3,0]],np.array(b)[[1,2,3,0]]]))([u]).as_quat()[0]
                        frame['rotation_wxyz'].append(xyzw[[3,0,1,2]].tolist())
                        frame['bone_position_xyz'][n]=(np.array(clip['frames'][lo].get('bone_position_xyz',{}).get(n,[0,0,0]))*(1-u)+np.array(clip['frames'][hi].get('bone_position_xyz',{}).get(n,[0,0,0]))*u).tolist()
                    pose=Pose(profile['rig_contract_r44'],profile['bones'],frame)
                    expected=Rotation.from_quat([pose.q[n].as_quat()for n in names]);error=np.degrees((expected.inv()*actual).magnitude())
                    direct={s:float((points[(sample['variant'],s)]@(pose.matrix('foot_'+s)[:3,:3]).T+pose.matrix('foot_'+s)[:3,3]/16)[:,1].min()*5)for s in('l','r')}
                    matches.append(dict(clip=key,maximum_rotation_error_degrees=float(max(error)),bone_errors=dict(zip(names,error.tolist())),direct_export_soles_blocks=direct))
                chosen=min(matches,key=lambda r:r['maximum_rotation_error_degrees']);selection.append(dict(stage=sample['stage'],review_tick=sample['review_tick'],tick=sample['tick'],phase=phase,match=chosen,actual_authored_soles=layers['authored']['soles'],all_matches=matches))
    summary={}
    for stage in sorted(set(r['stage']for r in rows)):
        group=[r for r in rows if r['stage']==stage]
        summary[stage]=dict(rows=len(group),largest_final_lift=sorted(group,key=lambda r:max(v['minimum_y_blocks']for v in r['layers']['final']['soles'].values()),reverse=True)[:5],first_authored_lift=next((r for r in group if max(v['minimum_y_blocks']for v in r['layers']['authored']['soles'].values())>2),None),first_late_lift=next((r for r in group if max(v['minimum_y_blocks']for v in r['layers']['final']['soles'].values())-max(v['minimum_y_blocks']for v in r['layers']['authored']['soles'].values())>2),None))
    args.out.mkdir(parents=True,exist_ok=True)
    report=dict(native=str(args.native),source_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),scope='Original decoded rigid sole vertices through actual same-render recorded palette matrices. Includes whole foot shell; final CPU joint/seam skin and GPU pixels require separate witnesses. Actual sole y is actor-relative, not inferred force/support.',visual_acceptance=False,rows=rows,summary=summary,actual_clip_selection=selection)
    (args.out/'native_attack_support_first_layer.json').write_text(json.dumps(report,indent=2),'utf8')
    for stage,value in summary.items():
        r=value['largest_final_lift'][0]
        print(stage,'worst',r['review_tick'],'ordinary',r['ordinary'],'phase',r['ordinary_phase'],'heavy',r['heavy_phase'], {s:v['minimum_y_blocks']for s,v in r['layers']['final']['soles'].items()},'changes',r['changes'])
    for stage in sorted(set(r['stage']for r in selection)):
        group=[r for r in selection if r['stage']==stage];counts={key:sum(r['match']['clip']==key and r['match']['maximum_rotation_error_degrees']<.001 for r in group)for key in sorted(set(r['match']['clip']for r in group))}
        print('SELECTION',stage,counts,'unmatched',sum(r['match']['maximum_rotation_error_degrees']>=.001 for r in group))

if __name__=='__main__':main()
