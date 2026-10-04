"""Rebuild only the three NERV hand candidates through the same checked pipeline."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--basis',type=Path,required=True);p.add_argument('--unit01',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--palm-cup',action='store_true');p.add_argument('--shared-anatomical-controls',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
def run(script,*args):
 subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools'/script),*map(str,args)],cwd=ROOT,check=True)
shutil.copytree(a.unit01,a.out/'unit01')
for key in [0,2]:
 stage=a.out/'source_stages'/f'unit0{key}';stage.mkdir(parents=True)
 run('rebind_anatomical_hand_r45.py','--basis',a.basis/f'unit0{key}','--reference',ROOT/'artifacts/rebuild_r45/models/hands/makehuman_reference','--out',stage/'coherent',*(['--palm-cup']if a.palm_cup else []))
 run('mirror_anatomical_hand_r45.py','--candidate',stage/'coherent','--out',stage/'mirror')
 run('rebind_phalange_proportions_r45.py','--candidate',stage/'mirror','--out',stage/'phalanges')
 run('author_natural_thumb_r45.py','--candidate',stage/'phalanges','--out',stage/'thumb')
 run('author_hand_grip_frames_r45.py','--candidate',stage/'thumb','--out',a.out/f'unit0{key}')
 if a.shared_anatomical_controls:
  import copy
  template=json.loads((a.unit01/'hand_rig_contract.json').read_text('utf8'));path=a.out/f'unit0{key}'/'hand_rig_contract.json';target=json.loads(path.read_text('utf8'))
  assert len(template['new_bones'])==len(target['new_bones'])==34
  target['pose_controls']=copy.deepcopy(template['pose_controls'])
  target['control_transfer_r45']=dict(source=str(a.unit01.resolve()),method='Anatomical local-angle vocabulary only; target-specific measured geometry, inverse binds and palm frames rebuilt',pose_space_corrective_not_transferred=True,weapon_contacts_pending=True,visual_accepted=False)
  path.write_text(json.dumps(target,indent=2),'utf8')
for key in [0,1,2]:run('validate_anatomical_asset_r45.py','--candidate',a.out/f'unit0{key}','--out',a.out/f'structural_{key}.json')
(a.out/'status.json').write_text(json.dumps(dict(rigs=[0,1,2],structural_only=True,native_verified=[],surface_verified=[],user_approved=False,UN_unchanged=True,basis=str(a.basis.resolve()),unit01_template=str(a.unit01.resolve()),palm_cup=a.palm_cup,shared_anatomical_controls=a.shared_anatomical_controls),indent=2),encoding='utf8')
