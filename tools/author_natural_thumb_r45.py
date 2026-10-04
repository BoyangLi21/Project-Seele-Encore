"""Authored thumb opposition: lay across the fist; never chase a tip target."""
from pathlib import Path
import argparse,copy,json,shutil

p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
for f in a.candidate.iterdir():
 if f.is_file():shutil.copy2(f,a.out/f.name)
path=a.out/'hand_rig_contract.json';c=json.loads(path.read_text());c.pop('thumb_opposition_solver',None)
for pose in c['pose_controls'].values():
 for name in list(pose.get('bone_angles',{})):
  if '_thumb_'in name:pose['bone_angles'].pop(name)
poses={
 'fist':[[55,18,-45],[18,0,0],[12,0,0]],
 'knife':[[55,18,-45],[18,0,0],[12,0,0]],
 'grab':[[10,12,12],[15,0,0],[10,0,0]],
 'rifle_right':[[18,25,25],[18,0,0],[12,0,0]],
 'rifle_left':[[10,12,12],[15,0,0],[10,0,0]],
}
for name,angles in poses.items():c['pose_controls'][name]['thumb']=angles
c['pose_controls']['fist']['index']=[85,100,80]
for side in ['l','r']:
 joints=c['hands'][side]['digits']['thumb']['joints']
 joints[1]['anatomical_limits_degrees']=[[0,45],[0,0],[-8,8]]
 joints[2]['anatomical_limits_degrees']=[[0,35],[0,0],[0,0]]
c['thumb_direction']='Outside-index thumb contact, gently flexed MCP/IP. Index pad closes past the thenar surface rather than through it. No endpoint attraction or thumb wrap underneath the fist.'
c['construction']['thumb_visual_accepted']=False
path.write_text(json.dumps(c,indent=2),'utf8');print('Authored thumb: fist MCP18deg/IP12deg; contact seeking removed')
