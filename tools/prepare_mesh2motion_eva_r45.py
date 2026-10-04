"""Use one pinned Mesh2Motion animation family on the measured EVA skeleton.

The original source skin is not installed. Each family's own bind pose is
retained; shared bone names alone do not establish interchangeable bind axes.
"""
from pathlib import Path
import argparse,copy,hashlib,json,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from retarget_human_r12 import Human
from author_combat_r35 import Actor
from audit_retarget_basis_r43 import AnatomicalRetarget
from author_grounded_capture_r43 import anatomy
from prepare_eva_forward_strikes_r45 import support
import author_combat_performance_r36 as performance

ROOT=Path(__file__).resolve().parents[1]

def human(decoded,clip,out,mirror=False):
    rest=np.load(decoded/'REST_BIND.npz');parts=[np.load(decoded/(name+'.npz'))for name in clip.split('+')];motion=parts[0]
    assert list(rest['names'])==list(motion['names'])
    for part in parts:assert list(part['names'])==list(motion['names'])and float(part['fps'])==float(motion['fps'])
    positions=np.concatenate([rest['positions']]+[p['positions'] if i==0 else p['positions'][1:]for i,p in enumerate(parts)])
    rotations=np.concatenate([rest['rotations']]+[p['rotations'] if i==0 else p['rotations'][1:]for i,p in enumerate(parts)])
    names=list(motion['names'])
    if mirror:
        positions[:,:,0]*=-1;rotations[:,:,[1,2]]*=-1
        names=[('R'+n[1:]if n.startswith('L')and len(n)>1 and n[1].isupper()else'L'+n[1:]if n.startswith('R')and len(n)>1 and n[1].isupper()else n)for n in names]
    target=out/(clip.replace(' ','_')+('_mirrored'if mirror else'')+'_calibrated.npz')
    np.savez_compressed(target,names=names,positions=positions,rotations=rotations,fps=motion['fps'])
    h=Human(target);h.reference_frame=0;p=positions[0]
    across=p[h.index[h.map['shoulder_l']]]-p[h.index[h.map['shoulder_r']]];forward=np.cross(across,[0,1,0])
    h.basis=R.from_euler('y',np.arctan2(forward[0],-forward[2]));h.reference=p[h.index['Hip']].copy();h.reference[1]=0
    h.floor=min(p[h.index[h.map['ankle_'+s]],1]for s in ['l','r'])
    h.height=float(p[h.index['Head_End'],1]-min(p[h.index[h.map['toe_'+s]],1]for s in ['l','r']))
    source=Path(str(motion['source']));return h,dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_clip=clip,
        source_license='CC0-1.0',mirrored=mirror,source_kind='Hand-keyed animation, not asserted live mocap',bind_source_sha256=hashlib.sha256((decoded/'REST_BIND.npz').read_bytes()).hexdigest())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--family',choices=['addon','base'],default='addon');ap.add_argument('--rigs',nargs='+',type=int,default=[1]);ap.add_argument('--decoded',type=Path,required=True);a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);(a.out/'AUTHORING_INCOMPLETE.json').write_text('{}');sources=a.out/'source';sources.mkdir()
    decoded=a.decoded
    selections=[('guard','Fighting Idle'),('jab','Fighting Left Jab'),('cross','Fighting Right Jab')]if a.family=='addon'else [('jab','Punch_Jab'),('cross','Punch_Cross'),('heavy','Melee_Hook+Melee_Hook_Rec')]
    base=ROOT/'artifacts/rebuild_r45/motion/two_stage_repair_work_v181'
    for p in base.glob('*gameplay*.json'):shutil.copy2(p,a.out/p.name)
    reports=[];original=performance.common.human
    captured={name:human(decoded,name,sources)for _,name in selections}
    for rig in a.rigs:
        actor=Actor(rig);path=a.out/f'eva_gameplay_r42_{rig}.json';data=json.loads(path.read_text())
        for role,source in selections:
            h,meta=captured[source];performance.common.human=lambda *args:(h,meta)
            try:c,origin=performance.captured(actor,source,False,role,AnatomicalRetarget,anatomy,stage_alignment='actor')
            finally:performance.common.human=original
            contacts=support(h,len(c['frames']))
            for frame,contact in zip(c['frames'],contacts):frame['foot_contact']=contact
            c.update(stance_locked=False,step_contacts=contacts,source_duration_seconds=c['duration_seconds'],source_timing_r45=role!='guard',loop=role=='guard',
                     support='Whole source family with one bind calibration; measured heel/toe support, no permanent two-foot lock')
            data['clips']['r32_'+role]=c;data['sources'][role]=dict(origin,EVA_adaptation='Same whole-body performance; anatomical hinges and existing detailed hand owner',native_accepted=False)
            reports.append(dict(rig=rig,role=role,source=source,duration=c['duration_seconds'],contact_phase=c['contact_phase'],leading_side=c['leading_side'],foot_contact_counts=np.sum(contacts,axis=0).tolist()))
        path.write_text(json.dumps(data,separators=(',',':')))
    (a.out/'provenance.json').write_text(json.dumps(dict(family=a.family,reports=reports,geometry_changed=False,art_accepted=False,native_passed=False,full_required_motion_set=False),indent=2))
    (a.out/'AUTHORING_INCOMPLETE.json').unlink();print(json.dumps(reports))

if __name__=='__main__':main()
