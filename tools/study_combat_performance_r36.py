"""Export source poses and hand close-ups using the actual private game meshes."""
from pathlib import Path
import argparse,json,numpy as np
from scipy.spatial.transform import Rotation as R
import author_combat_r35 as author
import review_tv_combat_r34 as review
import combat_hand_pose_r36 as hands
ROOT=Path(__file__).resolve().parents[1]

def decode(actor,data,f):
    p=actor.rig.pose() if actor.angel else actor.rig.Pose()
    for n,(w,x,y,z) in zip(data['bones'],f['rotation_wxyz']):p.setq(n,R.from_quat([-x,-y,z,w]))
    for n,v in f.get('bone_position_xyz',{}).items():p.setp(n,np.asarray(v)*[-1,1,1])
    p.setp('root',np.asarray(f['root_m'])*112*[-1,1,1]);return p

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--profiles',type=Path,default=ROOT/'artifacts/combat_sortie_r32/gameplay_sources');ap.add_argument('--out',type=Path,required=True);ap.add_argument('--hands',action='store_true');ap.add_argument('--rigs',default='1,sachiel');ap.add_argument('--clip',default='jab');ap.add_argument('--phases',type=float,nargs='+');args=ap.parse_args()
    if args.phases:assert all(0<=t<=1 for t in args.phases)
    args.out.mkdir(parents=True,exist_ok=True);manifest=[]
    for key in args.rigs.split(','):
        key=key if key=='sachiel' else int(key);a=author.Actor(key)
        if args.hands and a.angel:continue
        model='sachiel' if a.angel else ['eva_unit00','eva_unit01','eva_unit02','eva_prototype','eva_un01'][key]
        path=args.profiles/'sachiel_gameplay_r32.json' if a.angel else next((args.profiles/f'eva_gameplay_r{revision}_{key}.json' for revision in (44,43,42,32) if (args.profiles/f'eva_gameplay_r{revision}_{key}.json').is_file()),None)
        assert path is not None,'Missing explicit actor profile'
        data=json.loads(path.read_text());c=data['clips']['r32_'+args.clip]
        for index,t in enumerate(args.phases if args.phases else [0,.25,float(c['contact_phase']),.7,.95] if not args.hands else [0,1]):
            p=decode(a,data,c['frames'][round((len(c['frames'])-1)*t)])
            if args.hands:
                for n in p.q:p.setq(n,R.identity());p.setp(n,[0,0,0])
                hands.apply(p,a.rig.rig,float(index))
            v,uv=review.mesh(a,p,model);file=f'{model}_{index}';np.savez_compressed(args.out/(file+'.npz'),vertices=v*5/16,uv=uv)
            target=(p.point('hand_r')+[0,-3,0])*5/16 if args.hands else np.array([0,25,0])
            manifest.append(dict(file=file,model=model,phase=t,camera_target=target[[0,2,1]].tolist(),scale=7 if args.hands else 74,camera_offset=[-35,65,20] if args.hands else [-78,130,25]))
    (args.out/'manifest.json').write_text(json.dumps(manifest))
if __name__=='__main__':main()
