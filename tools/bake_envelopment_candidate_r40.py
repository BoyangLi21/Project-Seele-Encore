"""Editable, isolated sagittal wrapping performance; never installs game files."""
from pathlib import Path
import argparse
import copy,json,struct,hashlib
import numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
from scipy.spatial import ConvexHull
import author_first_battle_r10 as b
import author_eva_rifle_stances_r06 as mesh
from preview_first_battle_r12 import angel_pose
from anatomical_hinge_r35 import solve as hinge_solve

ROOT=b.ROOT;OUT=ROOT/'artifacts/world_combat_r40/envelopment_candidate'
START=489;END=558;UNIT=b.UNIT


def rigid_fit(source,target):
    a=source.mean(0);c=target.mean(0);u,_,vt=np.linalg.svd((source-a).T@(target-c));rotation=vt.T@u.T
    if np.linalg.det(rotation)<0:vt[-1]*=-1;rotation=vt.T@u.T
    return R.from_matrix(rotation),c-rotation@a


def smooth(t):
    t=np.clip(t,0,1);return t*t*t*(10+t*(-15+6*t))


def write_hero(data,current,index,hero):
    original=b.eva.decode(data['eva']['frames'][index],data['eva']['bones']);root=np.asarray(data['eva']['root_blocks'][index])
    current['eva']['frames'][index]=b.eva.encode(hero,bone_names=data['eva']['bones'])
    for channel,bone in [('eye_blocks','head'),('look_blocks','head'),('socket_blocks','torso_upper'),
                         ('socket_outward_blocks','torso_upper'),('socket_up_blocks','torso_upper'),
                         ('rib_tip_blocks','hand_r'),('rib_side_blocks','hand_r')]:
        if channel not in data['eva']:continue
        point=(np.asarray(data['eva'][channel][index])-root)*b.HEROMIRROR/UNIT
        local=np.linalg.inv(original.matrix(bone))@np.r_[point,1]
        current['eva'][channel][index]=(root+(hero.matrix(bone)@local)[:3]*b.HEROMIRROR*UNIT).tolist()
    for side in ['l','r']:
        current['eva']['hand_'+side+'_blocks'][index]=b.hero_world(hero,root,'hand_'+side,b.eva.P['finger_middle_'+side]).tolist()
        current['eva']['foot_'+side+'_blocks'][index]=b.hero_world(hero,root,'foot_'+side,b.eva.P['foot_'+side]+b.SOLE[side]).tolist()


def main(arap=True,contacts=False):
    global OUT
    if arap:OUT=ROOT/'artifacts/world_combat_r40/envelopment_arap'
    OUT.mkdir(parents=True,exist_ok=True);study=OUT.parent/'envelopment_study'
    sourcefile=ROOT/'artifacts/world_combat_r40/envelopment_native/baseline_first_battle_r24.json'
    if not sourcefile.exists():sourcefile=ROOT/'run/projectseele-local-maps/first_battle_r24.json'
    data=json.loads(sourcefile.read_text())
    if 'r40_envelopment' in data:raise ValueError('Re-authoring requires the preserved pre-R40 clip')
    current=copy.deepcopy(data);cachefile=np.load(study/'target_unique.npz');target=cachefile['angel'];inverse=cachefile['inverse']
    target_hero=b.eva.decode(json.loads((study/'target_hero_pose.json').read_text()),data['eva']['bones'])
    initial_hero=b.eva.decode(data['eva']['frames'][START],data['eva']['bones'])
    initial_root=np.array(data['eva']['root_blocks'][START])
    a0=angel_pose(data['angel']['frames'][START],data['angel']['bones']);ar=np.array(data['angel']['root_blocks'][START]);source=a0.skin()*UNIT+ar
    final_root=np.array(data['eva']['root_blocks'][END]);axis=b.hero_world(target_hero,final_root,'torso_upper')
    rest=b.ANGEL.vertices;distance=np.linalg.norm((rest-b.ANGEL.core)*[1,1,.8],axis=1)
    head_weight=np.where(b.ANGEL.ids==b.ANGEL.names.index('head'),b.ANGEL.weights,0).sum(1)
    core_weight=smooth((16-distance)/5)
    rigid=[]
    for weight in [head_weight,core_weight]:
        keep=weight>.99;rotation,translation=rigid_fit(source[keep],target[keep]);rigid.append((weight,rotation,translation))
    hero_parts=[n for n in mesh.MESH if n not in ['cannon','knife','lance','n2','entry_plug']]
    hero_uv=np.vstack([np.array(b.eva.mesh['parts'][n]['vertices']).reshape(-1,8)[:,3:5] for n in hero_parts])
    angel_file=b.eva.PACK/'mesh/sachiel.mesh.json';angel_data=json.loads(angel_file.read_text());av=np.array(angel_data['parts']['root']['vertices']).reshape(-1,8)
    v0=source-axis;v1=target-axis;angle0=np.arctan2(v0[:,1],v0[:,2]);angle1=np.arctan2(v1[:,1],v1[:,2]);delta=(angle1-angle0+np.pi)%(2*np.pi)-np.pi
    radius0=np.linalg.norm(v0[:,1:],axis=1);radius1=np.linalg.norm(v1[:,1:],axis=1)
    solved=None;attachments=[]
    if arap:
        from arap_envelopment_r40 import sequence
        solved,attachments=sequence(source,target,inverse,b.ANGEL,END-START+1)
    curves=[];hero_curves=[];records=[];penetration=[];contact_corrections=[]
    for index in range(START,END+1):
        t=(index-START)/(END-START);u=smooth(t);angle=angle0+delta*u;radius=radius0*(1-u)+radius1*u+3*np.sin(np.pi*u)
        posed=axis+np.c_[v0[:,0]*(1-u)+v1[:,0]*u,radius*np.sin(angle),radius*np.cos(angle)]
        for weight,rotation,translation in ([] if arap else rigid):
            q=Slerp([0,1],R.concatenate([R.identity(),rotation]))([u])[0]
            centres=source[weight>.99].mean(0);end=rotation.apply(centres)+translation
            moved=q.apply(source-centres)+centres*(1-u)+end*u
            posed=posed*(1-weight[:,None])+moved*weight[:,None]
        if arap:posed=solved[index-START]
        hero=b.eva.decode(data['eva']['frames'][index],data['eva']['bones']);root=np.array(data['eva']['root_blocks'][index]);grip=smooth(t/.50)
        continuation=smooth((index-START)/8)
        for name in data['eva']['bones']:
            hero.setq(name,b.qmix(initial_hero.q[name],hero.q[name],continuation));hero.setp(name,initial_hero.p[name]*(1-continuation)+hero.p[name]*continuation)
        for n in data['eva']['bones']:
            if n.startswith(('arm_','forearm_','wrist_','hand_','finger_')):
                hero.setq(n,b.qmix(hero.q[n],target_hero.q[n],grip));hero.setp(n,hero.p[n]*(1-grip)+target_hero.p[n]*grip)
        original=b.hero_copy(hero);goals={};orientations={}
        for side,start,end in [('l',.15,.50),('r',.55,.84)]:
            step=smooth((t-start)/(end-start));qa=R.from_matrix(initial_hero.matrix('foot_'+side)[:3,:3]);qb=R.from_matrix(target_hero.matrix('foot_'+side)[:3,:3]);q=b.qmix(qa,qb,step)
            first=b.hero_world(initial_hero,initial_root,'foot_'+side);last=b.hero_world(target_hero,final_root,'foot_'+side)
            goal=first*(1-step)+last*step;goal[1]=-q.apply(b.eva.feet[side])[:,1].min()*UNIT+1.2*np.sin(np.pi*step)
            goals[side]=(goal-root)*b.HEROMIRROR/UNIT;orientations[side]=q
        for _ in range(12):
            for side in ['l','r']:
                hip=hero.point('leg_'+side);joint=b.eva.K[side]
                reach=(np.linalg.norm(joint-b.eva.P['leg_'+side])+np.linalg.norm(b.eva.P['foot_'+side]-joint))*.985
                reach_delta=hip-goals[side];distance=np.linalg.norm(reach_delta)
                if distance>reach:hero.setp('root',hero.p['root']-reach_delta*(1-reach/distance))
        for side in ['l','r']:
            pole=orientations[side].apply([0,0,-1]);pole[1]=0
            hinge_solve(hero,b.eva.P,'leg_'+side,'shin_'+side,'foot_'+side,b.eva.K[side],goals[side],pole,[-1,0,0],orientations[side])
        support=smooth((index-START)/8)
        for name in data['eva']['bones']:
            hero.setq(name,b.qmix(original.q[name],hero.q[name],support));hero.setp(name,original.p[name]*(1-support)+hero.p[name]*support)
        h=np.vstack([mesh.vertices(hero,n) for n in hero_parts])*b.HEROMIRROR*UNIT+root
        hero_curves.append(h.astype(np.float32))
        if arap and contacts:
            from arap_envelopment_r40 import contact_corrective
            posed,count=contact_corrective(posed,inverse,h,np.arange(len(h)).reshape(-1,3),attachments)
            contact_corrections.append(dict(frame=index,adjusted_vertices=count))
        write_hero(data,current,index,hero)
        for label,marker in [('core',b.ANGEL.core),('eye',b.ANGEL.eye),('hand_l',b.ANGEL.P['hand_l']),('hand_r',b.ANGEL.P['hand_r'])]:
            nearest=np.argmin(np.sum((rest-marker)**2,axis=1));current['angel'][label+'_blocks'][index]=posed[nearest].tolist()
        inside={}
        for name in ['torso_lower','torso_upper','head']:
            points=mesh.vertices(hero,name)*b.HEROMIRROR*UNIT+root;eq=ConvexHull(points).equations;depth=(posed@eq[:,:3].T+eq[:,3]).max(1)
            inside[name]=dict(vertices=int(sum(depth<-.1)),depth=float(depth.min()))
        penetration.append(dict(frame=index,parts=inside));curves.append(posed)
        if index in [489,505,520,538,558]:
            name=str(index);np.savez_compressed(OUT/(name+'.npz'),hero=h,hero_uv=hero_uv,angel=posed[inverse],angel_uv=av[:,3:5])
            records.append(dict(name=name,time=index/30,target=[float(axis[0]),float(-axis[2]),32],scale=93))
    held=b.hero_copy(hero)
    for index in range(END+1,min(584,len(data['eva']['frames']))):
        destination=b.eva.decode(data['eva']['frames'][index],data['eva']['bones']);weight=smooth((index-END)/25)
        for name in data['eva']['bones']:
            destination.setq(name,b.qmix(held.q[name],destination.q[name],weight));destination.setp(name,held.p[name]*(1-weight)+destination.p[name]*weight)
        write_hero(data,current,index,destination)
    curves=np.asarray(curves);binary=OUT/'sachiel_wrap_r14.bin'
    with binary.open('wb') as f:
        f.write(b'SW14');f.write(struct.pack('>6i',START,len(curves),30,curves.shape[1],len(inverse),len(inverse)))
        f.write(hashlib.sha256(angel_file.read_bytes()).digest());f.write(np.asarray(inverse,dtype='>i4').tobytes());f.write(np.asarray(av[:,3:5],dtype='>f4').tobytes());f.write(np.asarray(curves,dtype='>f4').tobytes())
    current['surface_deformation_r14']=hashlib.sha256(binary.read_bytes()).hexdigest()
    current['r40_envelopment']={'status':'isolated candidate, pending collision/art review','source_sha256':hashlib.sha256(sourcefile.read_bytes()).hexdigest(),
        'reference':'TV episode 02, visible C-shaped fold and pressure against the core; source footage is not embedded'}
    (OUT/'first_battle_r24.json').write_text(json.dumps(current,separators=(',',':')))
    (OUT/'manifest.json').write_text(json.dumps(records))
    np.savez_compressed(OUT/'surface_frames.npz',positions=curves,indices=inverse,uv=av[:,3:5])
    np.savez_compressed(OUT/'hero_frames.npz',positions=np.asarray(hero_curves),uv=hero_uv)
    report=dict(status='candidate only',start_continuity=float(np.max(np.linalg.norm(curves[0]-source,axis=1))),
                maximum_vertex_step=float(np.max(np.linalg.norm(np.diff(curves,axis=0),axis=2))),penetration=penetration,contact_corrections=contact_corrections)
    (OUT/'audit.json').write_text(json.dumps(report,indent=2));print({k:v for k,v in report.items() if k not in ('penetration','contact_corrections')},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--arap',action='store_true',default=True);parser.add_argument('--contacts',action='store_true',help='Research only; the published motion uses authored clearance routes');args=parser.parse_args();main(args.arap,args.contacts)
