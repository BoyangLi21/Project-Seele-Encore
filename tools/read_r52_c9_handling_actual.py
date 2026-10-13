"""Read the one completed immutable C9 handling capture; never start a game."""
from pathlib import Path
import argparse,hashlib,json,zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text('utf8'))
def rows(p):return [json.loads(x) for x in Path(p).read_text('utf8').splitlines() if x.strip()]
def mat(a):return np.asarray(a,float).reshape(4,4,order='F')
def basis(a):
 m=mat(a)[:3,:3];return m/np.linalg.norm(m,axis=0)[None,:]
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--capture-dir',type=Path,default=ROOT/'artifacts/r52_native_handling_candidate9');ap.add_argument('--out',type=Path,default=ROOT/'.codex/r52_c9_handling_readback');a=ap.parse_args();run,out=a.capture_dir.resolve(),a.out.resolve();assert run.is_relative_to(ROOT/'artifacts') and out.is_relative_to(ROOT)
 result=read(run/'RUN_RESULT.json');assert result['functional_capture_complete'] and result['natural_exit'] and not result['forced_cleanup'] and not result['timed_out'] and result['first_battle_movies']==0
 assert read(run/'OPTIONS_RESTORED.json')['byte_equal'];jar=Path(result['immutable_jar']['path']);assert hashlib.sha256(jar.read_bytes()).hexdigest()==result['immutable_jar']['sha256'];poses=rows(run/'ordinary/poses.jsonl');assert {r['variant'] for r in poses}=={1};assert max(r['age'] for r in poses)>=200
 launch=read(run/'launch.json');bundle=Path(launch['bundle_directory']);body=read(bundle/'eva_body_r44.json');parents={b['name']:b.get('parent') for b in body['rigs']['1']};parts={}
 with zipfile.ZipFile(jar) as z:
  data=z.read('assets/projectseele/mesh/eva_unit01.mesh.json');mesh=json.loads(data);mesh_sha=hashlib.sha256(data).hexdigest();assert {r['actual_foot_witness']['mesh_sha256'] for r in poses}=={mesh_sha}
  for side in ('l','r'):
   n='foot_'+side;assert n not in mesh.get('jointSkins',{});part=mesh['parts'][n];v=np.asarray(part['vertices'],float).reshape(-1,mesh['stride'])[:,:3];v=(v+part['pivot'])*[-1,1,1]/16;parts[side]=np.c_[v,np.ones(len(v))]
 soles=[]
 for r in poses:
  feet={}
  for side in ('l','r'):
   v=parts[side]@(mat(r['model_to_world'])@mat(r['final_rendered_model_bones']['foot_'+side])).T;i=int(np.argmin(v[:,1]));feet[side]=dict(minimum_world_y=float(v[i,1]),minimum_world_point=v[i,:3].tolist(),clearance_over_named_fixture_minus60=float(v[i,1]+60))
  soles.append(dict(age=r['age'],wall_ns=r['wall_ns'],weapon=r['getWeapon'],handling=r['handling_active'],onGround=r['onGround'],airAge=r['actual_airAge'],visuallyAirborne=r['isVisuallyAirborneForRender'],move=r['rifleMoveBlend'],memory=r['actual_ordinary_support_memory'],feet=feet))
 bands={}
 for name,lo,hi in [('before_draw',0,60),('draw',60,88),('draw_outlet',88,101),('knife_hold',101,120),('stow',120,161),('stow_outlet',161,177),('rifle_settled',177,210)]:
  selected=[r for r in soles if lo<=r['age']<hi and r['move']<.01 and not r['visuallyAirborne'] and r['airAge']<0];gaps=[p['clearance_over_named_fixture_minus60'] for r in selected for p in r['feet'].values()]
  bands[name]=dict(rows=len(selected),sole_clearance_range=[min(gaps),max(gaps)] if gaps else None,max_target_error_blocks=max(abs(x-.08) for x in gaps) if gaps else None,missing_memory_rows=sum(not r['memory']['present'] for r in selected),false_ground_retained_memory_rows=sum(not r['onGround'] and r['memory']['present'] for r in selected))
 def angles(a,b):
  r={}
  for n in ['arm_l','arm_r','forearm_l','forearm_r','hand_l','hand_r']:
   def local(row):return basis(row['final_rendered_model_bones'][parents[n]]).T@basis(row['final_rendered_model_bones'][n])
   q=local(a).T@local(b);r[n]=float(np.degrees(np.arccos(np.clip((np.trace(q)-1)/2,-1,1))))
  return r
 switches=[]
 for before,after in zip(poses,poses[1:]):
  if before['getWeapon']==after['getWeapon']:continue
  switches.append(dict(ages=[before['age'],after['age']],weapons=[before['getWeapon'],after['getWeapon']],elapsed_wall_seconds=(after['wall_ns']-before['wall_ns'])/1e9,local_joint_angle_degrees=angles(before,after),before_history=before['actual_pose_transition_history'],after_history=after['actual_pose_transition_history']))
 switch=next(r for r in switches if r['weapons']==[1,4]);handoff=[r for r in poses if r['getWeapon']==4 and r['age']>=switch['ages'][1]];timeline=[]
 for r in handoff:
  h=r['actual_pose_transition_history'];timeline.append(dict(age=r['age'],wall_ns=r['wall_ns'],time=h.get('time'),start=h.get('start'),duration=h.get('duration'),guard_exit=h.get('weaponGuardExit'),phase=h.get('time',0)-h.get('start',0),history=h))
 guard_pass=bool(switch['after_history'].get('weaponGuardExit') and switch['after_history'].get('duration')==.2 and max(switch['local_joint_angle_degrees'].values())<1 and any(not r['guard_exit'] and r['phase']>=.2 for r in timeline))
 support_pass=all(b['rows']>0 and b['max_target_error_blocks']<.001 and b['missing_memory_rows']==0 for b in bands.values())
 critical=[r for r in soles if r['age'] in (87,88,89,160,161,165,176,209)];images=rows(run/'ordinary/frames.jsonl');selected_images=[]
 for age in (80,88,89,160,161,165,176,209):
  nearest=min(images,key=lambda r:abs(r['age']-age));selected_images.append(dict(requested_age=age,actual_age=nearest['age'],path=str(run/'ordinary/frames'/nearest['file']),wall_ns=nearest['wall_ns'],capture_ns=nearest['capture_ns'],camera_view=nearest['camera_view']))
 report=dict(schema='projectseele.r52.c9-actual-handling-readback.v1',immutable_jar=result['immutable_jar'],pose_rows=len(poses),captured_pose_age_range=[min(r['age'] for r in poses),max(r['age'] for r in poses)],native_images=len(images),first_battle_movies=0,actual_support_status='PASS' if support_pass else 'FAIL',actual_guard_status='PASS' if guard_pass else 'FAIL',ordinary_sole_bands=bands,actual_weapon_switches=switches,actual_rifle_handoff_history=timeline,critical_outlet_rows=critical,all_actual_shoe_rows=soles,key_real_native_images=selected_images,natural_exit=True,options_byte_restored=True,gpu_vertex_output_readback=False,user_artistic_acceptance=False,limits=['All original rigid-shoe vertices reconstructed with same-row actual final bone/model-to-world matrices; no GPU deformation readback','210 input ticks completed; only the recorded pose rows qualify, not every-tick/per-frame matrices. Images can hold the most recent captured pose metadata','Named unchanged QA flat floor top=-60; helper floor rays are not separately exported','Guard PASS requires actual knife-to-rifle first presented joint continuity, a finite .2s history window and its actual expiration; images still require human review'])
 out.mkdir(parents=True,exist_ok=True);(out/'ACTUAL_C9_HANDLING_READBACK.json').write_text(json.dumps(report,indent=2)+'\n','utf8');summary={k:v for k,v in report.items() if k not in ('all_actual_shoe_rows','actual_rifle_handoff_history','key_real_native_images','critical_outlet_rows')};print(json.dumps(summary));assert support_pass and guard_pass,'Actual C9 handling evidence fails; no native retry initiated'
if __name__=='__main__':main()
