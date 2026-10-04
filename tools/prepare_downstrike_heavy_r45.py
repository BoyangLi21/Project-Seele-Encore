"""Author a complete captured downstrike without the rejected G1 gesture or fixed dual-foot bake."""
from pathlib import Path
import argparse,copy,hashlib,json,shutil
import numpy as np
from author_combat_r35 import Actor
from audit_retarget_basis_r43 import AnatomicalRetarget
from author_grounded_capture_r43 import anatomy
import author_combat_performance_r36 as performance

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    incomplete=a.out/'AUTHORING_INCOMPLETE.json';incomplete.write_text('{"incomplete":true}')
    source_dir=a.out/'source';source_dir.mkdir();performance.common.OUT=source_dir
    base=ROOT/'artifacts/rebuild_r45/motion/two_stage_repair_work_v181'
    for f in base.glob('*gameplay*.json'):shutil.copy2(f,a.out/f.name)
    reports=[]
    for rig in [0,1,2]:
        actor=Actor(rig)
        clip,meta=performance.captured(actor,'SlapDownwards',False,'heavy',AnatomicalRetarget,anatomy)
        human,_=performance.common.human('SlapDownwards',False)
        times=np.linspace(1,human.frames-1,len(clip['frames']));points=[human.sample(float(t))[0]for t in times]
        dt=(human.frames-2)/human.fps/max(1,len(times)-1);contacts=[]
        side_contacts=[]
        for side in ['l','r']:
            heel=np.array([x['ankle_'+side]for x in points]);toe=np.array([x['toe_'+side]for x in points]);tip=np.array([x['toe_end_'+side]for x in points])
            feet=[heel,toe,tip];floor=min(float(np.percentile(x[:,1],3))for x in feet)
            support=np.zeros(len(times),bool)
            for end in feet:
                speed=np.linalg.norm(np.gradient(end[:,[0,2]],dt,axis=0),axis=1)
                support|=(end[:,1]<=floor+.025*human.height)&(speed<=.30*human.height)
            side_contacts.append(support)
        contacts=np.column_stack(side_contacts).tolist()
        path=a.out/f'eva_gameplay_r42_{rig}.json';profile=json.loads(path.read_text());old=profile['clips']['r32_heavy'];new=copy.deepcopy(old)
        new.update(clip);new.update(source_duration_seconds=clip['duration_seconds'],source_timing_r45=True,stance_locked=False,step_contacts=contacts,support='Actual source heel/toe height and velocity; no persistent dual-foot anchors')
        for row,contact in zip(new['frames'],contacts):row['foot_contact']=contact
        profile['clips']['r32_heavy']=new;profile['sources']['heavy']=dict(meta,adaptation='Complete source pelvis/chest/limbs; anatomical hinge reconstruction; source clock; current hand controller owns fingers',native_accepted=False)
        path.write_text(json.dumps(profile,separators=(',',':')))
        reports.append(dict(rig=rig,source=meta,leading_side=new['leading_side'],duration_seconds=new['duration_seconds'],contact_phase=new['contact_phase'],frames=len(new['frames']),contact_counts=np.sum(contacts,axis=0).tolist(),runtime_clock='Explicit authoredHeavyTicksR45 then existing1.5 melee rate; requires post182 compile',damage_and_cooldown_unchanged=True))
    (a.out/'provenance.json').write_text(json.dumps(dict(reports=reports,third_stage_removed=True,existing_first_two_preserved=True,rejected_heavy_reused=False,geometry_changed=False,native=False,art_accepted=False),indent=2))
    incomplete.unlink();print(json.dumps(reports))

if __name__=='__main__':main()
