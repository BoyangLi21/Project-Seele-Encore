"""Offline evaluation of the same anatomical hand contract and inverse binds.

Use the selected runtime surface, not the legacy body-mesh fingers. Pixel
coordinates are maintained until the normal model-to-world scale is applied.
"""
import numpy as np
from scipy.spatial.transform import Rotation as R
from author_eva_rifle_stances_r06 import multiply


def extend_body(body,contract):
    names={n['name']for n in body['rigs']['1']}
    body['rigs']['1'] += [b for b in contract['new_bones'] if b['name']not in names]


def natural_carry(pose,contract,elbows,P,sides=('l','r')):
    for side in sides:
        hand='hand_'+side;frame=contract['hands'][side]
        along=pose.point(hand)-pose.point('forearm_'+side,elbows[side]);along/=np.linalg.norm(along)
        inward=pose.matrix('torso_upper')[:3,:3]@np.array([1 if side=='l'else -1,0.,0.])
        inward-=along*(inward@along);inward/=np.linalg.norm(inward)
        along=along*np.cos(np.radians(5))+inward*np.sin(np.radians(5));along/=np.linalg.norm(along)
        inward-=along*(inward@along);inward/=np.linalg.norm(inward)
        source_along=np.asarray(frame['longitudinal_bind']);source_along/=np.linalg.norm(source_along)
        source_normal=np.asarray(frame['palmar_normal_bind']);source_normal-=source_along*(source_normal@source_along);source_normal/=np.linalg.norm(source_normal)
        source=np.column_stack([source_normal,source_along,np.cross(source_normal,source_along)])
        target=np.column_stack([inward,along,np.cross(inward,along)])
        rotation=R.from_matrix(target@source.T)
        pose.setq(hand,R.from_matrix(pose.parent(hand)[:3,:3]).inv()*rotation)


def apply_controls(pose,contract,left,right):
    definitions={b['name']:b for b in contract['new_bones']}
    for side in ('l','r'):
        choice=contract['pose_controls'][left if side=='l'else right]
        for digit,data in contract['hands'][side]['digits'].items():
            for j in data['joints']:
                name=j['name'];index=j['index']
                if name in choice.get('bone_angles',{}):angles=np.asarray(choice['bone_angles'][name],float)
                elif digit=='thumb':angles=np.asarray(choice['thumb'][index],float)
                else:
                    angles=np.array([choice.get(digit,choice['fingers'])[index],0,0.],float)
                    if index==0:angles[2]=choice.get('splay',{}).get(digit,0)
                limits=np.asarray(j['anatomical_limits_degrees']);angles=np.clip(angles,limits[:,0],limits[:,1])
                sign=1 if side=='l'else -1
                neutral=R.from_quat(j['neutral_local_quaternion_xyzw'])
                local=R.from_euler('ZYX',[sign*angles[2],sign*angles[1],-angles[0]],degrees=True)
                pose.setq(name,neutral*local);pose.setp(name,[0,0,0])


def surface(pose,mesh,part):
    data=mesh['parts'][part];raw=np.asarray(data['vertices']).reshape(-1,8)
    rest=(raw[:,:3]+data['pivot'])*[-1,1,1]
    skin=mesh['jointSkins'][part];names=list(skin['influences'])
    weights=np.column_stack([skin['influences'][n]for n in names])
    matrices=[]
    for name in names:
        inverse=np.asarray(skin['inverseBindColumnMajor'][name]).reshape(4,4).T.copy()
        inverse[:3,3]*=16
        matrices.append(pose.matrix(name)@inverse)
    matrices=np.asarray(matrices);q=R.from_matrix(matrices[:,:3,:3]).as_quat()
    d=.5*multiply(np.c_[matrices[:,:3,3],np.zeros(len(names))],q)
    reference=np.argmax(weights,axis=1)
    sign=np.where((q[None,:,:]*q[reference,None,:]).sum(2)<0,-1,1)
    w=weights*sign
    real=w@q;dual=w@d;norm=np.linalg.norm(real,axis=1,keepdims=True)
    real/=norm;dual/=norm;dual-=real*(real*dual).sum(1,keepdims=True)
    points=R.from_quat(real).apply(rest)+2*multiply(dual,real*[-1,-1,-1,1])[:,:3]
    return points,raw[:,3:5]
