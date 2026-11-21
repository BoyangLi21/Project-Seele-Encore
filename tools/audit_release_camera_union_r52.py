"""Conservative exact camera proof: original full hull plus every affected skin part."""
from pathlib import Path
import argparse,hashlib,json,time
import numpy as np
from r52_motion_core import selected,read,UNIT,MIRROR

parser=argparse.ArgumentParser(description=__doc__)
for name in ('body','assets','angel-rig','clip','source','cache','cache-source','out'):
    parser.add_argument('--'+name,type=Path,required=True)
parser.add_argument('--both-arms',action='store_true')
args=parser.parse_args();_,hero,_=selected(args.body,args.assets,args.angel_rig);clip=read(args.clip);source=read(args.source);cached_source=read(args.cache_source)
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert clip['angel']==source['angel'] and clip['camera']==source['camera']
assert all(source[role]==cached_source[role] for role in ('eva','angel'))
cache=np.load(args.cache);assert str(cache['source_sha256'])==digest(args.cache_source)
hulls=[cache['vertices'][a:b] for a,b in zip(cache['offsets'][:-1],cache['offsets'][1:])]
modified={n for n in hero.names if n in ('arm_l','forearm_l','hand_l') or n.startswith('r45_hand_l_')}
if args.both_arms:modified.update(n for n in hero.names if n in ('arm_r','forearm_r','hand_r') or n.startswith('r45_hand_r_'))
def affected(bone):
    while bone:
        if bone in modified:return True
        bone=hero.parents[bone]
    return False
parts=[]
for name in hero.parts:
    if name not in hero.names or name in ('dorsal_liner','r37_red_upper','r37_red_lower','r37_lining'):continue
    influences=[name]
    if name in ('hand_l','hand_r'):influences=list(hero.hand_mesh['jointSkins'][name]['influences'])
    elif name in hero.mesh.get('jointSkins',{}):influences.append(hero.mesh['jointSkins'][name]['otherBone'])
    if any(affected(bone) for bone in influences if bone in hero.names):parts.append(name)
assert parts
rows=[];failed=[];changed=[];started=time.perf_counter()
for frame,vertices in enumerate(hulls):
    assert clip['eva']['root_blocks'][frame]==source['eva']['root_blocks'][frame]
    new=clip['eva']['frames'][frame];old=source['eva']['frames'][frame]
    for j,name in enumerate(source['eva']['bones']):
        if name not in modified:assert new['rotation_wxyz'][j]==old['rotation_wxyz'][j],(frame,name)
    for name in set(new.get('bone_position_xyz',{}))|set(old.get('bone_position_xyz',{})):
        if name not in modified:assert new.get('bone_position_xyz',{}).get(name)==old.get('bone_position_xyz',{}).get(name),(frame,name)
    if new!=old:
        pose=hero.decode(new,clip['eva']['bones']);extra=pose.surface(parts)*MIRROR*UNIT+np.array(clip['eva']['root_blocks'][frame]);vertices=np.concatenate([vertices,extra]);changed.append(frame)
    eye=np.array(clip['camera']['position'][frame]);target=np.array(clip['camera']['target'][frame]);forward=target-eye;forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward);delta=vertices-eye;z=delta@forward;tangent=np.tan(np.radians(clip['camera']['fov'][frame])/2)
    hh=float(np.max(np.abs((delta@right)/z/tangent/(16/9))));vv=float(np.max(np.abs((delta@up)/z/tangent)));dd=float(np.linalg.norm(delta,axis=1).max())
    row=dict(frame=frame,horizontal_ndc=hh,vertical_ndc=vv,maximum_skin_distance=dd,minimum_forward_depth=float(z.min()));rows.append(row)
    if hh>.88 or vv>.78 or dd>=95 or z.min()<=1:failed.append(row)
report=dict(clip_sha256=digest(args.clip),source_sha256=digest(args.source),cache_source_sha256=digest(args.cache_source),cache_sha256=digest(args.cache),body_sha256=digest(args.body),frame_count=len(rows),fps=60,changed_skin_frames=changed,affected_parts=parts,
    union_is_conservative=True,all_other_hero_pose_channels_and_entire_angel_exact=True,camera2_exact=True,
    horizontal_ndc_max=max(r['horizontal_ndc'] for r in rows),vertical_ndc_max=max(r['vertical_ndc'] for r in rows),maximum_skin_distance=max(r['maximum_skin_distance'] for r in rows),passed=not failed,failures=failed,
    elapsed_seconds=time.perf_counter()-started,scope='Every authored60fps frame; old exact full selected skin hull plus every actual affected new skin part. Old withdrawn arm remains in the conservative union. No native shader/camera-collision/entry blend or artistic pass inferred.',native_verified=False,user_accepted=False)
args.out.write_text(json.dumps(report,indent=2),'utf8');print({k:v for k,v in report.items() if k not in ('changed_skin_frames','failures')},flush=True)
