"""Read a frozen candidate and measure selected real support patches at 60Hz."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from r52_motion_core import selected,read,UNIT,MIRROR,skin
from author_finisher_r52 import angel_patch,world
from bake_finisher_r52 import sole_point
from calibrated_arm_r49 import axial_twist

def main():
    ap=argparse.ArgumentParser()
    for n in ('body','assets','angel-rig','clip','out'):ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();_,hero,alien=selected(a.body,a.assets,a.angel_rig);clip=read(a.clip)
    actors={};support=[]
    for role,rig in [('eva',hero),('angel',alien)]:
        worst_floor=(1e9,None);worst_plant=(0,None);worst_twist=(0,None);wrist=[];feet={s:[] for s in ('l','r')};plant_fail=[]
        for i,f in enumerate(clip[role]['frames']):
            t=i/clip['fps'];p=rig.decode(f,clip[role]['bones']);root=np.asarray(clip[role]['root_blocks'][i])
            if role=='eva' or t<18.6:
                full_surface=role=='angel' or i%6==0
                v=p.surface() if full_surface else p.surface(['leg_l','shin_l','foot_l','leg_r','shin_r','foot_r'])
                low=float(v[:,1].min()*UNIT+root[1])
                if low<worst_floor[0]:worst_floor=(low,i)
            for s,j in [('l',0),('r',1)]:
                sole=sole_point(p,root,s);feet[s].append(sole.tolist())
                if f['foot_contact'][j]:
                    gap=abs(float(sole[1]))
                    if gap>worst_plant[0]:worst_plant=(gap,i)
                    if gap>.025:plant_fail.append({'frame':i,'side':s,'sole_y_blocks':float(sole[1])})
                twist=float(np.degrees(abs(axial_twist(p.q['arm_'+s],rig.elbows[s]-rig.P['arm_'+s]))))
                if twist>worst_twist[0]:worst_twist=(twist,i)
            wrist.append([world(p,root,'hand_'+s).tolist() for s in ('l','r')])
            if role=='angel' and (5.5<=t<12 or 13<=t<=13.2):
                if t<12:patch=angel_patch(rig,p,['torso_lower','torso_upper','neck','head'],posterior=True);kind='posterior shoulder/back/hip'
                else:patch=angel_patch(rig,p,['hand_l'],palm_side='l');kind='left rear palm base'
                support.append({'frame':i,'second':t,'patch':kind,'minimum_y_blocks':float(patch[:,1].min()*UNIT+root[1])})
        wrist=np.asarray(wrist);steps=np.linalg.norm(np.diff(wrist,axis=0),axis=2);idx=np.unravel_index(steps.argmax(),steps.shape)
        actors[role]={'minimum_actual_surface_y_blocks':worst_floor[0],'minimum_surface_frame':worst_floor[1],
            'max_planted_sole_error_blocks':worst_plant[0],'max_sole_error_frame':worst_plant[1],
            'planted_sole_errors_over_0_025_blocks':plant_fail,'max_upper_arm_axial_degrees':worst_twist[0],'max_axial_frame':worst_twist[1],
            'max_wrist_displacement_blocks_frame':float(steps[idx]),'max_wrist_frame':int(idx[0]+1),'max_wrist_side':['l','r'][idx[1]]}
        print(role,actors[role],flush=True)
    rows=np.asarray([r['minimum_y_blocks'] for r in support]);worst=int(np.argmax(np.abs(rows)))
    report={'candidate':str(a.clip.resolve()),'sha256':hashlib.sha256(a.clip.read_bytes()).hexdigest(),'fps':clip['fps'],
        'measurement':'60Hz actual feet and Angel full skin; EVA actual leg/boot skin 60Hz and full skin 10Hz. Foot flags compared to actual sole patch; never long spikes as body support.',
        'actors':actors,'support_patch_max_absolute_error_blocks':float(np.abs(rows).max()),'worst_support_patch':support[worst],
        'support_patch_samples':support,'scope_limits':'Triangle collision samples are in separate leg clearance report. Native eye, jaw, explosion shaders and perceptual choreography remain pending.',
        'native_verified':False,'user_accepted':False}
    a.out.write_text(json.dumps(report,indent=2),encoding='utf-8')
if __name__=='__main__':main()
