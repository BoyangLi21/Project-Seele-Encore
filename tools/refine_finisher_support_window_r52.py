"""Recompute only the support transfer window in a complete candidate."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
from r52_motion_core import selected,read,UNIT
from author_finisher_r52 import keyposes,world
from bake_finisher_r52 import constrained,anchors,sole_point
from calibrated_arm_r49 import axial_twist

def main():
    ap=argparse.ArgumentParser()
    for n in ('body','assets','angel-rig','source','candidate','report'):ap.add_argument('--'+n,type=Path,required=True)
    ap.add_argument('--start',type=int,default=720);ap.add_argument('--end',type=int,default=872)
    a=ap.parse_args();body,hero,alien=selected(a.body,a.assets,a.angel_rig);source=read(a.source);out=read(a.candidate);report=read(a.report);keys=keyposes(hero,alien);baseline=anchors(source,hero)
    start,end=a.start,a.end;index=max(0,start-1)
    previous=None if start==0 else {'t':index/60,'eva':hero.decode(out['eva']['frames'][index],out['eva']['bones']),'angel':alien.decode(out['angel']['frames'][index],out['angel']['bones']),'hr':np.asarray(out['eva']['root_blocks'][index]),'ar':np.asarray(out['angel']['root_blocks'][index])}
    samples={s['frame']:s for s in report['surface_samples']}
    for i in range(start,end+1):
        item=constrained(keys,i/60,previous);previous=item
        for role,root_key,rig in [('eva','hr',hero),('angel','ar',alien)]:
            p=item[role];root=item[root_key];out[role]['frames'][i]=p.encode(out[role]['bones'],item[role+'_contacts']);out[role]['root_blocks'][i]=root.tolist()
            for s in ('l','r'):
                out[role]['hand_'+s+'_blocks'][i]=world(p,root,'hand_'+s).tolist();out[role]['foot_'+s+'_blocks'][i]=sole_point(p,root,s).tolist()
            if role=='eva':
                for channel,(bone,point) in baseline.items():out[role][channel][i]=world(p,root,bone,point).tolist()
            else:
                for channel,bone,point in [('eye_blocks','head',rig.eye),('core_blocks','torso_upper',rig.core),('waist_blocks','torso_lower',rig.waist)]:out[role][channel][i]=world(p,root,bone,point).tolist()
        if i%12==0:
            row={'frame':i,'second':i/60,'eva_root':item['hr'].tolist(),'angel_root':item['ar'].tolist()}
            for role,root_key in [('eva','hr'),('angel','ar')]:
                p=item[role];row[role+'_minimum_y_blocks']=float(p.surface()[:,1].min()*UNIT+item[root_key][1]);row[role+'_upper_arm_axial_degrees']={s:float(np.degrees(abs(axial_twist(p.q['arm_'+s],p.rig.elbows[s]-p.rig.P['arm_'+s])))) for s in ('l','r')}
            samples[i]=row
    speeds={};outliers=[]
    for role in ('eva','angel'):
        rows=out[role]['frames'];raw=np.asarray([f['rotation_wxyz'] for f in rows]);raw/=np.linalg.norm(raw,axis=-1,keepdims=True)
        for i in range(1,len(raw)):
            sign=np.where((raw[i]*raw[i-1]).sum(1)<0,-1,1);raw[i]*=sign[:,None];rows[i]['rotation_wxyz']=raw[i].round(8).tolist()
        angles=2*np.degrees(np.arccos(np.clip(np.abs((raw[1:]*raw[:-1]).sum(-1)),0,1)))*60;speeds[role]=float(angles.max())
        for i in np.flatnonzero(angles.max(1)>900):
            j=int(angles[i].argmax());outliers.append({'frame':int(i+1),'actor':role,'bone':out[role]['bones'][j],'speed_deg_s':float(angles[i,j])})
    out['r52_finisher_rebuild']['support_transfer_window_refined_frames']=[start,end]
    a.candidate.write_text(json.dumps(out,separators=(',',':')),encoding='utf-8');report.update(sha256=hashlib.sha256(a.candidate.read_bytes()).hexdigest(),surface_samples=[samples[i] for i in sorted(samples)],max_bone_speed_deg_s=speeds,speed_outliers_over_900=outliers)
    a.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print('Refined support window',start,end,'max speed',speeds,'outliers',len(outliers),flush=True)
if __name__=='__main__':main()
