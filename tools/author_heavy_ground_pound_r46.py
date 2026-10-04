"""Root-authored full-source downward heavy strike; no mesh or other clip replacement."""
from pathlib import Path
import json,copy,argparse,shutil
import numpy as np
from prepare_mesh2motion_eva_r45 import human
from author_combat_r35 import Actor
from audit_retarget_basis_r43 import AnatomicalRetarget
from author_grounded_capture_r43 import anatomy
from prepare_eva_forward_strikes_r45 import support
import author_combat_performance_r36 as performance
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 sources=a.out/'source';sources.mkdir()
 h,meta=human(ROOT/'artifacts/rebuild_r45/motion/mesh2motion_research_v190/decoded_addon_v192','Attack_Ground_Pound',sources)
 reports=[]
 for rig in (0,1,2):
  path=ROOT/f'artifacts/rebuild_r45/delivery_inputs_v224/motion_core/projectseele-local-maps/eva_gameplay_r44_{rig}.json'
  original=json.loads(path.read_text('utf8'));profile=copy.deepcopy(original);actor=Actor(rig)
  old=performance.common.human;performance.common.human=lambda *args:(h,meta)
  try:clip,provenance=performance.captured(actor,'Attack_Ground_Pound',False,'heavy',AnatomicalRetarget,anatomy,stage_alignment='actor')
  finally:performance.common.human=old
  # Ground impact is the recorded low point after the first complete downward stroke,
  # not the forwardmost hand as used by the lateral hook detector.
  data=np.load(sources/'Attack_Ground_Pound_calibrated.npz');names=list(data['names']);points=data['positions'][1:]
  hand_y=(points[:,names.index('LHand'),1]+points[:,names.index('RHand'),1])*.5
  peak=int(np.argmax(hand_y[:len(hand_y)//2]));contact=peak+int(np.argmin(hand_y[peak:]))
  contacts=support(h,len(clip['frames']))
  for frame,c in zip(clip['frames'],contacts):frame['foot_contact']=c
  clip.update(contact_phase=contact/(len(hand_y)-1),leading_side='r',stance_locked=False,
      step_contacts=contacts,source_duration_seconds=clip['duration_seconds'],source_timing_r45=True,
      loop=False,support='Recorded heel/toe support and weight transfer; full windup, strike and recovery, no persistent two-foot anchor')
  profile['clips']['r32_heavy']=clip
  profile['sources']['heavy']=dict(provenance,EVA_adaptation='Original giant double-fist downward strike interpretation; source full-body timing and foot sequence retained. Not a claim of TV animation reproduction.',native_accepted=False,user_accepted=False)
  unchanged=[k for k,v in original['clips'].items()if k!='r32_heavy'and profile['clips'][k]==v]
  assert len(unchanged)==len(original['clips'])-1
  assert all(np.isfinite(np.array(f['rotation_wxyz'])).all() for f in clip['frames'])
  (a.out/path.name).write_text(json.dumps(profile,ensure_ascii=False,separators=(',',':')),'utf8')
  reports.append(dict(rig=rig,source_clip='Attack_Ground_Pound',duration=clip['duration_seconds'],contact_phase=clip['contact_phase'],source_peak_frame=peak,source_contact_frame=contact,other_clips_preserved=len(unchanged),mesh_changed=False,damage_changed=False,native_verified=False,user_accepted=False))
 (a.out/'receipt.json').write_text(json.dumps(reports,indent=2),'utf8');print(json.dumps(reports))
if __name__=='__main__':main()
