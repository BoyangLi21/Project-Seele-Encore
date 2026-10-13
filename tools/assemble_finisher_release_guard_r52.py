"""Keep the checked departure; recover to a known local guard without IK branches."""
from pathlib import Path
import argparse,copy,hashlib,json
from r52_motion_core import selected,read
from revise_finisher_body_r52 import rotation_mix,preserve_hinges
from author_finisher_r52 import world
from r52_motion_core import ease
import numpy as np

parser=argparse.ArgumentParser(description=__doc__)
for name in ('body','assets','angel-rig','source','departure','out'):
    parser.add_argument('--'+name,type=Path,required=True)
args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True);output=args.out/'first_battle_r52_body3_release_guard.json';assert not output.exists()
_,hero,_=selected(args.body,args.assets,args.angel_rig);source=read(args.source);departure=read(args.departure);candidate=copy.deepcopy(source)
changed=lambda n:n in ('arm_l','forearm_l','hand_l') or n.startswith('r45_hand_l_')
guard=hero.decode(source['eva']['frames'][792],source['eva']['bones']);start=hero.decode(departure['eva']['frames'][600],source['eva']['bones'])
for frame in range(541,601):
    candidate['eva']['frames'][frame]=copy.deepcopy(departure['eva']['frames'][frame]);candidate['eva']['hand_l_blocks'][frame]=copy.deepcopy(departure['eva']['hand_l_blocks'][frame])
for frame in range(601,750):
    t=frame/60;body=hero.decode(source['eva']['frames'][frame],source['eva']['bones']);pose=copy.deepcopy(body)
    arrival=ease((t-10)/.5);returning=ease((t-12.25)/.25)
    for name in pose.q:
        if changed(name):pose.setq(name,rotation_mix(rotation_mix(start.q[name],guard.q[name],arrival),body.q[name],returning))
    preserve_hinges(pose)
    encoded=pose.encode(source['eva']['bones'],source['eva']['frames'][frame]['foot_contact']);original=source['eva']['frames'][frame]
    for index,name in enumerate(source['eva']['bones']):
        if not changed(name):encoded['rotation_wxyz'][index]=copy.deepcopy(original['rotation_wxyz'][index])
    encoded['root_m']=copy.deepcopy(original['root_m']);positions=copy.deepcopy(original.get('bone_position_xyz',{}))
    for name in list(positions):
        if changed(name):del positions[name]
    positions.update({n:v for n,v in encoded.get('bone_position_xyz',{}).items() if changed(n)})
    encoded['bone_position_xyz']=positions;candidate['eva']['frames'][frame]=encoded
    candidate['eva']['hand_l_blocks'][frame]=world(pose,np.array(source['eva']['root_blocks'][frame]),'hand_l').tolist()
assert candidate['angel']==source['angel'] and candidate['camera']==source['camera']
assert candidate['eva']['root_blocks']==source['eva']['root_blocks']
assert all(candidate['eva']['frames'][frame]==source['eva']['frames'][frame] for frame in range(750,1117))
candidate['r52_finisher_rebuild']['release_revision']='Checked9–10.0 departure, 10.0–10.5 local existing guard recovery, original autonomous Angel; no later IK branch'
output.write_text(json.dumps(candidate,separators=(',',':')),'utf8')
(args.out/'ASSEMBLY_RECEIPT.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),departure_sha256=hashlib.sha256(args.departure.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),departure_frames_exact=[541,600],known_guard_frame=792,guard_local_transition=[10,10.5],root_positions_exact=True,angel_entire_source_exact=True,camera2_exact=True,late367_pose_root_frames_exact=True,native_verified=False,user_accepted=False),indent=2),'utf8')
print(output,flush=True)
