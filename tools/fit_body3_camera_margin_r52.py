"""Retain camera positions/FOV80; gently recenter two exact-skin windows."""
from pathlib import Path
from types import SimpleNamespace
import argparse,copy,json,hashlib
import numpy as np
from r52_motion_core import ease,read
from fit_finisher_camera_full_r52 import hulls

parser=argparse.ArgumentParser(description=__doc__)
for name in ('body','assets','angel-rig','clip','out','reuse-cache','reuse-clip'):
    parser.add_argument('--'+name,type=Path,required=True)
args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True);source=args.clip.read_bytes();clip=json.loads(source);candidate=copy.deepcopy(clip)
settings=SimpleNamespace(body=args.body,assets=args.assets,angel_rig=args.angel_rig,clip=args.clip,cache=args.out/'EXACT_BODY3_SKIN_HULLS.npz',reuse_cache=args.reuse_cache,reuse_clip=args.reuse_clip)
points=hulls(settings,clip,hashlib.sha256(source).hexdigest());changes=[]
for frame,vertices in enumerate(points):
    t=frame/60;horizontal=ease((t-14.2)/.25)*(1-ease((t-14.9)/.3));vertical=ease((t-15.95)/.20)*(1-ease((t-16.5)/.3))
    if horizontal<=0 and vertical<=0:continue
    eye=np.asarray(clip['camera']['position'][frame]);target=np.asarray(clip['camera']['target'][frame]);distance=np.linalg.norm(target-eye);forward=(target-eye)/distance;right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward);p=vertices-eye;z=p@forward;x=(p@right)/z;y=(p@up)/z
    shift_x=(x.min()+x.max())*.5*horizontal;shift_y=(y.min()+y.max())*.5*vertical
    direction=forward+right*shift_x+up*shift_y;direction/=np.linalg.norm(direction);new=eye+direction*distance;candidate['camera']['target'][frame]=new.tolist();changes.append(dict(frame=frame,target_shift_blocks=float(np.linalg.norm(new-target)),horizontal_weight=horizontal,vertical_weight=vertical))
assert all(candidate[role]==clip[role] for role in ('eva','angel'))
target=args.out/'first_battle_r52_body3_camera1.json';assert not target.exists();target.write_text(json.dumps(candidate,separators=(',',':')),'utf8')
(args.out/'CAMERA_REVISION_REPORT.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source).hexdigest(),candidate_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),actors_exactly_unchanged=True,camera_positions_unchanged=True,fov_unchanged=True,maximum_fov=max(candidate['camera']['fov']),changed_frames=changes,native_verified=False,user_accepted=False),indent=2),'utf8')
print(target,flush=True)
