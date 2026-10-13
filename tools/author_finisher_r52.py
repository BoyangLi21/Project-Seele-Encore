"""R52 paired blocking from selected rigs. Key poses precede full-rate baking."""
from pathlib import Path
import argparse,copy,json,hashlib,subprocess
import numpy as np
from scipy.spatial.transform import Rotation as R
from PIL import Image,ImageDraw,ImageFont
from r52_motion_core import selected,read,UNIT,MIRROR,ease,mix,hand_controls,hand_carry,skin
from anatomical_hinge_r35 import solve as hinge
from calibrated_arm_r49 import solve as arm_solve

def vec(v):return np.asarray(v,float)

def foot_solve(rig,p,goals,yaw=0,sole_heights=None):
    rotation=R.from_euler('y',yaw,degrees=True)
    knee_pole=p.q['root'].apply([0,0,-1])
    for _ in range(10):
        for s in ('l','r'):
            hip=p.point('leg_'+s);reach=np.linalg.norm(rig.knees[s]-rig.P['leg_'+s])+np.linalg.norm(rig.P['foot_'+s]-rig.knees[s])
            delta=hip-goals[s];length=np.linalg.norm(delta)
            if length>reach*.989:p.setp('root',p.p['root']-delta*(1-reach*.989/length))
    for s in ('l','r'):
        hinge(p,rig.P,'leg_'+s,'shin_'+s,'foot_'+s,rig.knees[s],goals[s],knee_pole,[-1,0,0],rotation)
    if rig.angel:
        # The delivered Angel boot soles contain 50/50 shin/foot weights.
        # A foot-bone-only hull misses those actual heel vertices.
        for _ in range(3):
            for s in ('l','r'):
                mask=(np.where(rig.ids==rig.names.index('foot_'+s),rig.weights,0).sum(1)>.20)&(rig.vertices[:,1]<17)
                matrices=np.asarray([p.matrix(n) for n in rig.names])
                floor=skin(rig.vertices[mask],matrices,rig.ids[mask],rig.weights[mask])[:,1].min()
                goals[s]=goals[s]+vec([0,(sole_heights or {}).get(s,0)-floor,0])
                hinge(p,rig.P,'leg_'+s,'shin_'+s,'foot_'+s,rig.knees[s],goals[s],knee_pole,[-1,0,0],rotation)

def arms(rig,p,goals,yaw=0,relaxed=False,pole_override=None,stable=False):
    result=[];rot=R.from_euler('y',yaw,degrees=True)
    for s in ('l','r'):
        sign=-1 if s=='l' else 1
        # Elbows remain out of the rib cage; the solver's twist guard alone
        # cannot establish that the visible limb is on the front body surface.
        pole=rot.apply([sign*.12,0,-1] if relaxed else [sign*.8,-.45,-.35])
        if pole_override is not None:pole=vec(pole_override[s])
        solver=__import__('calibrated_arm_r52').solve if stable else arm_solve
        item=solver(p,rig.P,'arm_'+s,'forearm_'+s,'hand_'+s,rig.elbows[s],goals[s],pole,[1,0,0])
        direction=p.point('hand_'+s)-p.point('forearm_'+s,rig.elbows[s]);direction/=np.linalg.norm(direction)
        # A relaxed wrist follows the forearm's longitudinal direction.
        bind=rig.P['hand_'+s]-rig.elbows[s];bind/=np.linalg.norm(bind)
        q=R.align_vectors([direction],[bind])[0]
        p.setq('hand_'+s,R.identity() if rig.angel else R.from_matrix(p.parent('hand_'+s)[:3,:3]).inv()*q)
        item.update(side=s,target_error_blocks=float(np.linalg.norm(p.point('hand_'+s)-goals[s])*UNIT))
        result.append(item)
    hand_carry(p);hand_controls(p)
    p.arm_diagnostics=result
    return result

def stance(rig,yaw=0,drop=0,lean=0,width=None,feet=None):
    p=rig.pose();rot=R.from_euler('y',yaw,degrees=True)
    p.setq('root',rot);p.setq('torso_lower',R.from_euler('x',lean*.55,degrees=True));p.setq('torso_upper',R.from_euler('x',lean*.45,degrees=True))
    p.setp('root',[0,-drop,0])
    w=width if width is not None else (19 if not rig.angel else 20)
    goals={s:rot.apply([(-1 if s=='l' else 1)*w,-rig.feet[s][:,1].min(),(-8 if s=='l' else 8)]) for s in ('l','r')}
    if feet is not None:goals=feet
    foot_solve(rig,p,goals,yaw)
    goals={s:p.point('arm_'+s)+rot.apply([(-1 if s=='l' else 1)*3,-(58 if not rig.angel else 80),-7]) for s in ('l','r')}
    arms(rig,p,goals,yaw,relaxed=True)
    return p

def world(p,root,n,rigpoint=None):
    return root+p.point(n,rigpoint)*(np.ones(3) if p.rig.angel else MIRROR)*UNIT

def hand_world(rig,p,root,goals,yaw,stable=False):
    mirror=np.ones(3) if rig.angel else MIRROR
    return arms(rig,p,{s:(vec(goals[s])-root)*mirror/UNIT for s in ('l','r')},yaw,stable=stable)

def hip_world(rig,p,root,wanted):
    mirror=np.ones(3) if rig.angel else MIRROR
    hip=(p.point('leg_l')+p.point('leg_r'))*.5
    p.setp('root',p.p['root']+(vec(wanted)-root)*mirror/UNIT-hip)

def angel_patch(rig,p,bones,posterior=False,palm_side=None):
    ids=[rig.names.index(n) for n in bones]
    weight=np.isin(rig.ids,ids)*rig.weights;mask=weight.sum(1)>.82
    if posterior:mask&=(rig.vertices[:,2]>1)&(rig.vertices[:,1]>58)&(rig.vertices[:,1]<193)
    if palm_side is not None:
        # This mesh's palm lies about 25px beyond the wrist pivot. Selecting a
        # radius at that pivot selects the wrist cuff instead of the palm.
        mask&=(rig.vertices[:,1]>111)&(rig.vertices[:,1]<134)&(rig.vertices[:,2]<-55)&(rig.vertices[:,2]>-79)
    if np.count_nonzero(mask)<4:raise ValueError('Selected support patch is empty')
    matrices=np.asarray([p.matrix(n) for n in rig.names])
    return skin(rig.vertices[mask],matrices,rig.ids[mask],rig.weights[mask])

def back_support(rig,p):
    # The shoulder/back surface has blended neck/head weights in this actual
    # skin. The region is selected geometrically before skinning, and excludes
    # arms, hands, spikes, feet and the front chest/core.
    verts=angel_patch(rig,p,['torso_lower','torso_upper','neck','head'],posterior=True)
    p.setp('root',p.p['root']+[0,-verts[:,1].min(),0])

def alien_palm_orientation(p,side,forward=-1):
    # Rest claws curve towards -Z and -Y. A flat -90deg wrist buries the
    # fingers; this oblique palm-base contact raises the claws and leaves
    # the wrist/forearm above the floor without altering the mesh or bones.
    rotation=R.from_euler('y',(1-float(forward))*90,degrees=True)*R.from_euler('x',-150,degrees=True)
    p.setq('hand_'+side,R.from_matrix(p.parent('hand_'+side)[:3,:3]).inv()*rotation)

def palm_support(rig,p,root,xz,yaw=0,forward=-1,palm_heights=None,stable=False):
    goals={s:vec([xz[s][0],2,xz[s][1]]) for s in ('l','r')}
    best=None
    for _ in range(12):
        hand_world(rig,p,root,goals,yaw,stable=stable)
        for s in ('l','r'):alien_palm_orientation(p,s,forward[s] if isinstance(forward,dict) else forward)
        errors={}
        for s in ('l','r'):
            patch=angel_patch(rig,p,['hand_'+s],palm_side=s)*UNIT+root
            errors[s]=(palm_heights or {}).get(s,0)-patch[:,1].min()
        score=max(abs(v) for v in errors.values())
        if best is None or score<best[0]:best=(score,copy.deepcopy(p))
        if score<1e-5:break
        for s in ('l','r'):goals[s][1]+=errors[s]
    for s in ('l','r'):
        for bone in ('arm_'+s,'forearm_'+s,'hand_'+s):p.setq(bone,best[1].q[bone]);p.setp(bone,best[1].p[bone])
    return {s:float((angel_patch(rig,p,['hand_'+s],palm_side=s)*UNIT+root)[:,1].min()) for s in ('l','r')}

def keyposes(hero,alien):
    # Shared space: EVA is west of the supine body during core strikes. Both
    # its feet remain outside the Angel's lateral torso surface.
    out=[];flat_root=vec([0,0,31]);attack_root=vec([-32,0,71])
    hr=vec([0,0,0]);ar=vec([0,0,31]);h=stance(hero,drop=7,lean=-7);a=stance(alien,drop=2,lean=3)
    hand_world(hero,h,hr,{'l':[8,43,8],'r':[-8,45,10]},0)
    out.append(dict(t=0,name='guard',eva=h,angel=a,hr=hr,ar=ar))
    h=stance(hero,drop=8,lean=-10);hr=vec([0,0,8]);a=stance(alien,drop=6,lean=12)
    hand_world(hero,h,hr,{'l':[13,39,21],'r':[-13,39,21]},0)
    hand_world(alien,a,ar,{'l':[-13,39,21],'r':[13,39,21]},0)
    out.append(dict(t=3.2,name='wrist_pressure',eva=h,angel=a,hr=hr,ar=ar))
    flat=alien.pose();flat.setq('root',R.from_euler('x',90,degrees=True))
    flat.setq('neck',R.from_euler('x',-8,degrees=True));flat.setq('head',R.from_euler('x',-20,degrees=True))
    for s in ('l','r'):
        sign=1 if s=='l' else -1
        # Roll the dorsal elbow spikes away from the floor, then fold the
        # forearms over the abdomen. The stock bind forearm is 90deg bent.
        flat.setq('arm_'+s,R.from_euler('z',sign*65,degrees=True)*R.from_euler('y',sign*65,degrees=True)*R.from_euler('x',20,degrees=True))
        flat.setq('forearm_'+s,R.from_euler('x',25,degrees=True))
        flat.setq('hand_'+s,R.from_matrix(flat.parent('hand_'+s)[:3,:3]).inv()*R.from_euler('x',135,degrees=True))
    back_support(alien,flat)
    # Independent folded legs bring the heels onto the same ground as the
    # back. Long claws do not determine the height of the horizontal torso.
    feet={s:vec([(-1 if s=='l' else 1)*23,-alien.feet[s][:,1].min(),18]) for s in ('l','r')}
    foot_solve(alien,flat,feet,0)
    back_support(alien,flat)
    a=flat;ar=flat_root.copy();h=stance(hero,yaw=70,drop=11,lean=-8);hr=vec([-32,0,50])
    out.append(dict(t=5.5,name='landed',eva=h,angel=a,hr=hr,ar=ar))
    h=stance(hero,yaw=90,drop=63,lean=-72,width=22);hr=attack_root.copy()
    h.setq('torso_upper',R.from_euler('xyz',[-20,17,0],degrees=True))
    h.setq('clavicle_r',R.from_euler('xyz',[0,-9,-4],degrees=True))
    core=world(flat,flat_root,'torso_upper',alien.core)
    controlled_wrist=world(flat,flat_root,'hand_l')+vec([2,1.4,0])
    # Cock the fist above and in front of the actual right shoulder. This
    # folds the elbow beside the chest instead of abducting it behind EVA.
    goals={'l':controlled_wrist,'r':world(h,hr,'arm_r')+vec([4,5,2])}
    hand_world(hero,h,hr,goals,90)
    hand_controls(h,'support','fist')
    out.append(dict(t=7.9,name='core_chamber',eva=h,angel=copy.deepcopy(flat),hr=hr,ar=ar.copy()))
    h=stance(hero,yaw=90,drop=63,lean=-72,width=22)
    h.setq('torso_upper',R.from_euler('xyz',[-32.4,-11,0],degrees=True))
    h.setq('clavicle_r',R.from_euler('xyz',[0,7,2],degrees=True))
    hand_world(hero,h,hr,{'l':controlled_wrist,'r':core+[-1,2,0]},90)
    hand_controls(h,'support','fist')
    out.append(dict(t=8.35,name='core_contact',eva=h,angel=copy.deepcopy(flat),hr=hr,ar=ar.copy()))
    # Curl into a seated support, then release one hand while the opposite
    # posterior palm and both heels carry the body. No front/back hand swap.
    a=alien.pose();a.setq('root',R.from_euler('x',30,degrees=True));ar=vec([0,0,48])
    hip_world(alien,a,ar,[0,9.5,59])
    goals={s:(vec([(-1 if s=='l' else 1)*8,0,43])-ar)/UNIT+vec([0,-alien.feet[s][:,1].min(),0]) for s in ('l','r')}
    foot_solve(alien,a,goals,0)
    palm_support(alien,a,ar,{'l':[-21,73],'r':[21,73]},forward=1)
    planted_left={n:a.q[n] for n in ('arm_l','forearm_l','hand_l')}
    hand_world(alien,a,ar,{'l':world(a,ar,'hand_l'),'r':world(a,ar,'arm_r')+vec([-2,-6,-7])},0)
    for n,q in planted_left.items():a.setq(n,q)
    h=stance(hero,yaw=90,drop=18,lean=-6);hr=vec([-37,0,66])
    out.append(dict(t=13.0,name='palms_and_feet',eva=h,angel=a,hr=hr,ar=ar))
    lowfeet={s:vec([(-1 if s=='l' else 1)*24,-alien.feet[s][:,1].min(),(-8 if s=='l' else 8)]) for s in ('l','r')}
    a=stance(alien,drop=40,lean=10,width=24,feet=lowfeet);ar=vec([0,0,48])
    # The feet now carry the low squat. Both free arms fold in front of the
    # chest, avoiding a second planted-hand IK branch near full extension.
    hand_world(alien,a,ar,{s:world(a,ar,'arm_'+s)+vec([(-1 if s=='l' else 1)*-2,-6,-7]) for s in ('l','r')},0)
    for s in ('l','r'):alien_palm_orientation(a,s,-1)
    h=stance(hero,yaw=90,drop=7,lean=0);hr=vec([-37,0,60])
    out.append(dict(t=14.0,name='low_crouch',eva=h,angel=a,hr=hr,ar=ar))
    a=stance(alien,yaw=90,drop=3,lean=3,width=24);ar=vec([0,0,60]);h=stance(hero,yaw=90,drop=7,lean=0)
    out.append(dict(t=15.4,name='standing_turn',eva=h,angel=a,hr=hr.copy(),ar=ar))
    a=stance(alien,yaw=90,drop=7,lean=10,width=40);ar=vec([-19,0,60]);hr=vec([-31,0,60]);h=stance(hero,yaw=90,drop=0,lean=0)
    hand_world(alien,a,ar,{'l':[-36,44,65.5],'r':[-36,44,54.5]},90)
    for s in ('l','r'):
        rotation=R.from_euler('y',0 if s=='l' else 180,degrees=True)*R.from_euler('x',45,degrees=True)
        a.setq('hand_'+s,R.from_matrix(a.parent('hand_'+s)[:3,:3]).inv()*rotation)
    hand_world(hero,h,hr,{'l':[-26,36,52],'r':[-26,36,68]},90)
    hand_controls(h,'grab','grab')
    out.append(dict(t=18.25,name='embrace',eva=h,angel=a,hr=hr,ar=ar))
    h=stance(hero,yaw=90,drop=3,lean=0);a=copy.deepcopy(a)
    out.append(dict(t=22.8,name='natural_arms',eva=h,angel=a,hr=hr.copy(),ar=ar.copy()))
    return out

def sample(keys,t):
    if 13.0<=t<14.0:
        left,right=keys[5],keys[6];u=ease((t-13.20)/.80)
        out={'t':t,'name':'single_palm_to_heel_bearing'}
        for role in ('eva','angel'):out[role]=mix(left[role],right[role],u)
        for channel in ('hr','ar'):out[channel]=left[channel]*(1-u)+right[channel]*u
        return out
    if 12.0<=t<13.0:
        left,right=keys[3],keys[5];u=ease(t-12)
        out={'t':t,'name':'supported_sit_up'}
        for role in ('eva','angel'):out[role]=mix(left[role],right[role],u)
        for channel in ('hr','ar'):out[channel]=left[channel]*(1-u)+right[channel]*u
        return out
    if 7.9<=t<12.0:
        chamber,contact=keys[3],keys[4]
        phase=((t-7.9)/1.025)%1
        # One sharp driving stroke, then a slower recovery around the body.
        u=ease(phase/.44) if phase<.44 else 1 if phase<.56 else 1-ease((phase-.56)/.44)
        out={'t':t,'name':'supported_core_strike'}
        out['eva']=mix(chamber['eva'],contact['eva'],u);out['angel']=copy.deepcopy(contact['angel'])
        recoil=float(np.exp(-((phase-.47)/.085)**2))
        # EVA holds the near arm, so its shoulder/wrist stay pinned while the
        # head and neck flinch. Moving that shoulder into the planted knee
        # would make the visible control contact pass through the boot.
        out['angel'].setq('neck',contact['angel'].q['neck']*R.from_euler('x',-5*recoil,degrees=True))
        out['angel'].setq('head',contact['angel'].q['head']*R.from_euler('x',-9*recoil,degrees=True))
        back_support(out['angel'].rig,out['angel'])
        out['hr']=contact['hr'].copy();out['ar']=contact['ar'].copy()
        return out
    if 18.25<=t<=18.6:
        out=copy.deepcopy(keys[-2]);out['t']=t;return out
    if 18.6<t<22.8:
        out={'t':t,'name':'post_explosion_release'};u=ease((t-18.6)/3.0)
        for role in ('eva','angel'):out[role]=mix(keys[-2][role],keys[-1][role],u)
        for channel in ('hr','ar'):out[channel]=keys[-2][channel].copy()
        return out
    if t<=keys[0]['t']:return copy.deepcopy(keys[0])
    for left,right in zip(keys,keys[1:]):
        if t<=right['t']:
            u=ease((t-left['t'])/(right['t']-left['t']));out={'t':t,'name':left['name']+'_'+right['name']}
            for role in ('eva','angel'):out[role]=mix(left[role],right[role],u)
            for channel in ('hr','ar'):out[channel]=left[channel]*(1-u)+right[channel]*u
            return out
    return copy.deepcopy(keys[-1])

class Preview:
    def __init__(self,assets,size=(960,720)):
        self.assets=assets;self.size=size
        self.fov=41
        self.textures={n:np.asarray(Image.open(assets/'textures/entity'/f'{n}.png').convert('RGB')) for n in ('eva_unit01','sachiel')}
        self.set_camera([102,76,133],[-12,24,49])
    def set_camera(self,eye,target):
        self.eye=vec(eye);self.target=vec(target);self.forward=self.target-self.eye;self.forward/=np.linalg.norm(self.forward)
        self.right=np.cross(self.forward,[0,1,0]);self.right/=np.linalg.norm(self.right);self.up=np.cross(self.right,self.forward)
    def render(self,item,label,axes=False):
        tris=[];colors=[]
        for role,root,texture in [('eva',item['hr'],'eva_unit01'),('angel',item['ar'],'sachiel')]:
            if role=='angel' and item['t']>=18.6:continue
            p=item[role];rig=p.rig
            chosen=[n for n in rig.parts if n in p.q and not n.startswith('finger_') and n not in ['dorsal_liner','r37_red_upper','r37_red_lower','r37_lining']]
            v=p.surface(chosen) if not rig.angel else p.surface()
            uv=np.vstack([rig.uv[n] for n in chosen]) if not rig.angel else rig.uv['root']
            v=v*(np.ones(3) if rig.angel else MIRROR)*UNIT+root
            tr=v.reshape(-1,3,3);uv=uv.reshape(-1,3,2).mean(1);tex=self.textures[texture]
            c=tex[np.clip((uv[:,1]*tex.shape[0]).astype(int),0,tex.shape[0]-1),np.clip((uv[:,0]*tex.shape[1]).astype(int),0,tex.shape[1]-1)]
            normal=np.cross(tr[:,1]-tr[:,0],tr[:,2]-tr[:,0]);normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-8)
            c=np.clip(c*(.62+.38*np.abs(normal@vec([.3,.8,-.45])))[:,None],0,255).astype(np.uint8)
            tris.append(tr);colors.append(c)
        tr=np.concatenate(tris);col=np.concatenate(colors);points=tr-self.eye
        z=points@self.forward;x=points@self.right;y=points@self.up
        focal=self.size[1]/(2*np.tan(np.radians(self.fov)/2));screen=np.stack([self.size[0]/2+x/z*focal,self.size[1]/2-y/z*focal],axis=-1)
        im=Image.new('RGB',self.size,(38,46,57));draw=ImageDraw.Draw(im)
        # Identical ground grid in every frame exposes floating and slipping.
        def project(v):
            q=vec(v)-self.eye;zz=q@self.forward
            return (self.size[0]/2+q@self.right/zz*focal,self.size[1]/2-q@self.up/zz*focal)
        for k in range(-100,151,10):
            draw.line([project([k,0,-60]),project([k,0,150])],fill=(63,70,79))
            draw.line([project([-100,0,k]),project([100,0,k])],fill=(63,70,79))
        for i in np.argsort(-z.mean(1)):
            if z[i].min()>1:draw.polygon([tuple(v) for v in screen[i]],fill=tuple(int(c) for c in col[i]))
        if axes:
            for role,root,color in [('eva',item['hr'],(90,255,140)),('angel',item['ar'],(255,185,80))]:
                p=item[role];mir=np.ones(3) if p.rig.angel else MIRROR
                for n in ('head','torso_upper'):
                    origin=world(p,root,n);forward=(p.matrix(n)[:3,:3]@vec([0,0,-1]))*mir
                    start,end=project(origin),project(origin+forward*17)
                    draw.line([start,end],fill=color,width=4);draw.ellipse((end[0]-4,end[1]-4,end[0]+4,end[1]+4),fill=color)
                    draw.text((end[0]+6,end[1]),role+' '+n+' -Z bind forward',fill=color)
                for s in ('l','r'):
                    foot=world(p,root,'foot_'+s);point=project([foot[0],0,foot[2]])
                    draw.ellipse((point[0]-5,point[1]-3,point[0]+5,point[1]+3),outline=color,width=2)
        draw.rectangle((0,0,self.size[0],36),fill=(12,18,24));draw.text((12,10),f'R52 BLOCKING  {item["t"]:05.2f}s  {label}  |  actual selected mesh, fixed camera',fill=(230,236,239))
        draw.text((12,self.size[1]-26),'OFFLINE DRAFT - native game and user acceptance pending',fill=(216,225,230))
        return im

def main():
    ap=argparse.ArgumentParser()
    for key in ('body','assets','angel-rig','source','out'):ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--movie',action='store_true');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    body,hero,alien=selected(a.body,a.assets,a.angel_rig);keys=keyposes(hero,alien);source=read(a.source);records=[];preview=Preview(a.assets)
    for key in keys:
        preview.render(key,key['name']).save(a.out/(key['name']+'.png'))
        record={'second':key['t'],'name':key['name'],'eva':key['eva'].encode(source['eva']['bones']),'angel':key['angel'].encode(source['angel']['bones']),'eva_root_blocks':key['hr'].tolist(),'angel_root_blocks':key['ar'].tolist()}
        for role,root in [('eva',key['hr']),('angel',key['ar'])]:
            p=key[role];surface=p.surface()*(np.ones(3) if p.rig.angel else MIRROR)*UNIT+root
            record[role+'_surface_bounds']={'min':surface.min(0).tolist(),'max':surface.max(0).tolist()}
            record[role+'_joint_points']={n:world(p,root,n).tolist() for n in ['leg_l','shin_l','foot_l','leg_r','shin_r','foot_r','arm_l','forearm_l','hand_l','arm_r','forearm_r','hand_r']}
        record['arm_axial_guard_degrees']={role:{s:float(np.degrees(abs(__import__('calibrated_arm_r49').axial_twist(key[role].q['arm_'+s],key[role].rig.elbows[s]-key[role].rig.P['arm_'+s])))) for s in ('l','r')} for role in ('eva','angel')}
        if key['name'] in ('palms_and_feet','low_crouch'):
            record['palm_support_min_y_blocks']={s:float((angel_patch(alien,key['angel'],['hand_'+s],palm_side=s)*UNIT+key['ar'])[:,1].min()) for s in ('l','r')}
        records.append(record)
    for name,eye,target in [('front',[0,62,142],[0,25,25]),('side',[118,60,22],[0,27,22])]:
        preview.set_camera(eye,target)
        for key in keys[:2]:preview.render(key,key['name'],axes=True).save(a.out/(key['name']+'_axes_'+name+'.png'))
    (a.out/'KEY_POSES.json').write_text(json.dumps({'source':str(a.source),'source_sha256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'duration_ticks':460,'death_tick':372,'return_tick':432,'key_poses':records,'native_verified':False,'user_accepted':False,'interpolation_status':'coarse blocking; planted-foot and palm constraints re-solved during final bake'},indent=2),encoding='utf-8')
    sheet=Image.new('RGB',(2400,720))
    for j,key in enumerate(keys):
        im=Image.open(a.out/(key['name']+'.png')).resize((480,360));sheet.paste(im,((j%5)*480,(j//5)*360))
    sheet.save(a.out/'KEY_POSES_CONTACT_SHEET.jpg',quality=88)
    if a.movie:
        path=a.out/'continuous_low.mp4';fps=12;size=(640,480);preview=Preview(a.assets,size)
        proc=subprocess.Popen(['ffmpeg','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{size[0]}x{size[1]}','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','26','-pix_fmt','yuv420p',str(path)],stdin=subprocess.PIPE)
        for i in range(23*fps+1):
            item=sample(keys,i/fps);proc.stdin.write(preview.render(item,item['name']).tobytes())
            if i%60==0:print('preview frame',i,flush=True)
        proc.stdin.close();proc.wait();print(path,flush=True)
    print('Written 10 blocking poses, pending visual review',flush=True)
if __name__=='__main__':main()
