"""Root-authored roles from pinned source clips, with whole-body bearing.

This produces private profiles and evidence; it never installs a world or
asserts that a library name establishes EVA choreography or native acceptance.
"""
from pathlib import Path
import argparse,copy,hashlib,json,shutil
import numpy as np
from scipy.spatial import ConvexHull,QhullError
from author_combat_r35 import Actor
from audit_retarget_basis_r43 import AnatomicalRetarget
from author_grounded_capture_r43 import anatomy
from prepare_mesh2motion_eva_r45 import human
from prepare_eva_forward_strikes_r45 import support
import author_combat_performance_r36 as performance

ROOT=Path(__file__).resolve().parents[1]
ROLES={
 'evade_forward':('base','Shield_Dash_RM',False),
 'evade_back':('addon','Dodge_back_RM',False),
 'evade_left':('addon','Dodge_left_RM',False),
 'evade_right':('addon','Dodge_right_RM',False),
 'roll_forward':('base','Roll_RM',False),
 'sword_a':('base','Sword_Regular_A+Sword_Regular_A_Rec',False),
 'sword_b':('base','Sword_Regular_B+Sword_Regular_B_Rec',False),
 'sword_c':('base','Sword_Regular_C_RM',False),
 'sword_heavy':('base','Sword_Attack_RM',False),
 'sword_guard':('base','Idle_Sword',True),
 'shield_idle':('base','Idle_Shield',True),
 'shield_brace':('base','Shield_OneShot',False),
 'shield_hit':('base','Idle_Shield_Break',False),
 'berserk_walk':('addon','Walk_Large',True),
 'berserk_guard':('addon','Zombie_Idle_Crouch',True),
 'berserk_roar':('addon','Zombie Yell',False),
 'berserk_rise':('addon','Zombie_Rise',False),
 'berserk_l':('base','Zombie_Scratch',False),
 'berserk_r':('base','Zombie_Scratch',False),
 'death_a':('addon','Death_A',False),
 'death_b':('addon','Death_B',False),
 'death_c':('addon','Death_C',False),
 'death_d':('base','Death_D',False),
 'recover_laying':('base','LayToIdle',False),
}

def hulls(rig):
    path=ROOT/f'run/resourcepacks/eva_real_model/assets/projectseele/mesh/eva_unit0{rig}.mesh.json'
    data=json.loads(path.read_text());result={}
    for name,part in data['parts'].items():
        if name in ('knife','lance','rifle','shield','n2_bomb'):continue
        points=np.unique((np.asarray(part['vertices']).reshape(-1,8)[:,:3]+part['pivot'])*[-1,1,1],axis=0)
        try:points=points[ConvexHull(points).vertices]
        except QhullError:pass
        result[name]=points
    return result,dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())

def low(p,points):
    return min(float((v@p.matrix(n)[1,:3]+p.matrix(n)[1,3]).min())for n,v in points.items()if n in p.q)

def capture(actor,h,meta,role,loop,points):
    retarget=AnatomicalRetarget(h);count=max(61,int(round((h.frames-2)/h.fps*60))+1)
    poses=[];travel=[];poles={};levels=[]
    for f in np.linspace(1,h.frames-1,count):
        p,delta,_=retarget.pose(float(f),support='air');p=anatomy(actor,p,closure=.5,poles=poles)
        minimum=low(p,points);p.setp('root',p.p['root']+[0,-minimum,0]);levels.append(minimum)
        poses.append(p);travel.append(delta)
    # Source performances own the complete body. A support test over the actual
    # rigid part hulls includes shoulders/back/head while rolling or falling.
    contacts=support(h,count);world=np.asarray(travel)-travel[0];world[:,1]=0
    lead=max(('l','r'),key=lambda s:np.ptp([p.point('hand_'+s)[2] for p in poses]))
    hands=np.array([p.point('hand_'+lead)for p in poses]);speed=np.linalg.norm(np.gradient(hands,axis=0),axis=1)
    contact=int(np.argmax(speed))
    if loop:
        # A short loop closure affects only the final tenth; source traversal
        # remains separate so the skeleton does not jump to the entity origin.
        for i,p in enumerate(poses):
            t=i/(count-1)
            if t>.9:
                p=performance.mix(p,copy.deepcopy(poses[0]),performance.ease((t-.9)/.1))
                p.setp('root',p.p['root']+[0,-low(p,points),0]);poses[i]=p
    c=dict(frames=[performance.record(actor,p,c)for p,c in zip(poses,contacts)],
        trajectory_m=(world*[-1,1,1]/112).tolist(),duration_seconds=(h.frames-2)/h.fps,
        source_duration_seconds=(h.frames-2)/h.fps,source_timing_r45=True,
        contact_phase=float(np.clip(contact/(count-1),.08,.9)),leading_side=lead,
        loop=loop,stance_locked=False,step_contacts=contacts,
        support='Whole posed EVA body surface; no fixed foot anchors',
        source_contact_estimate='Peak captured hand speed; blade contact is authoritative at runtime')
    return c,dict(meta,role=role,frames=count,whole_body_floor_error=max(abs(low(p,points))for p in poses),
        relative_travel_m=c['trajectory_m'][-1],contact_phase=c['contact_phase'],native=False,art_accepted=False)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--decoded',type=Path,required=True)
    ap.add_argument('--roles',nargs='+',choices=list(ROLES),required=True);ap.add_argument('--rigs',nargs='+',type=int,default=[0,1,2]);ap.add_argument('--base-profiles',type=Path,default=ROOT/'artifacts/rebuild_r45/motion/mesh2motion_base_recovery_v196');a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);sources=a.out/'source';sources.mkdir();(a.out/'AUTHORING_INCOMPLETE.json').write_text('{}')
    base=a.base_profiles
    for file in base.glob('*gameplay*.json'):shutil.copy2(file,a.out/file.name)
    captures={}
    for role in a.roles:
        family,clip,_=ROLES[role]
        mirrored=role=='berserk_l'
        if(family,clip,mirrored)not in captures:captures[family,clip,mirrored]=human(a.decoded/family,clip,sources,mirrored)
    reports=[]
    for rig in a.rigs:
        actor=Actor(rig)
        hand_root=ROOT/'artifacts/rebuild_r45/models/hands'
        hand_file=hand_root/({0:'transition_crease_refinement_v136/unit00',1:'cannon_support_candidate_v133/unit01',2:'unit02_sword_thumb_v209/unit02'}[rig])/'hand_rig_contract.json'
        hand_contract=json.loads(hand_file.read_text());basis={}
        for side,hand in hand_contract['hands'].items():
            digits=hand['digits'];across=np.asarray(digits['index']['joints'][0]['head_bind'])-np.asarray(digits['little']['joints'][0]['head_bind'])
            basis[side]=dict(longitudinal_bind=hand['longitudinal_bind'],across_bind=across.tolist())
        actor.rig.anatomical_hand_basis_r45=basis
        points,geometry=hulls(rig);geometry['hand_bind_contract_sha256']=hashlib.sha256(hand_file.read_bytes()).hexdigest()
        file=a.out/f'eva_gameplay_r42_{rig}.json';data=json.loads(file.read_text())
        for role in a.roles:
            if role.startswith('sword_')and rig!=2 or role.startswith('shield_')and rig!=0 or role.startswith('berserk_')and rig!=1:continue
            family,clip,loop=ROLES[role];h,meta=captures[family,clip,role=='berserk_l']
            c,report=capture(actor,h,meta,role,loop,points);data['clips']['r32_'+role]=c
            data['sources'][role]=dict(meta,adaptation='Whole source, anatomical EVA limb lengths, complete body bearing')
            reports.append(dict(report,rig=rig,geometry=geometry));print(rig,role,len(c['frames']),c['duration_seconds'],flush=True)
        file.write_text(json.dumps(data,separators=(',',':')))
    (a.out/'provenance.json').write_text(json.dumps(dict(reports=reports,native_passed=False,user_accepted=False),indent=2))
    (a.out/'AUTHORING_INCOMPLETE.json').unlink()

if __name__=='__main__':main()
