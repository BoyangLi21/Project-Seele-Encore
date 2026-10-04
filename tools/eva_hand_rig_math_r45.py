"""Shared native-coordinate FK for hand authoring and contact inspection."""
import numpy as np
from scipy.spatial.transform import Rotation as R

def controls(contract,pose_name,side):
    pose=contract['pose_controls'][pose_name];result={}
    for digit,d in contract['hands'][side]['digits'].items():
        for i,j in enumerate(d['joints']):
            if j['name']in pose.get('bone_angles',{}):v=pose['bone_angles'][j['name']]
            elif pose.get('source_rest'):v=[j['rest_flex_degrees'],0,0]
            elif digit=='thumb':v=pose['thumb'][i]
            else:v=[pose.get(digit,pose['fingers'])[i],0,pose.get('splay',{}).get(digit,0)if i==0 else 0]
            lim=np.asarray(j['anatomical_limits_degrees']);result[j['name']]=np.clip(np.asarray(v,dtype=float),lim[:,0],lim[:,1])
    return result

def matrices(geo,contract,side,values=None):
    bones={b['name']:b for b in geo['minecraft:geometry'][0]['bones']};joints={j['name']:j for d in contract['hands'][side]['digits'].values()for j in d['joints']};cache={};mirror=1 if side=='l'else -1
    def matrix(n):
        if n in cache:return cache[n]
        b=bones[n];p=np.asarray(b['pivot'])*[-1,1,1]/16;r=R.from_euler('xyz',np.radians(np.asarray(b.get('rotation',[0,0,0]))*[-1,-1,1])).as_matrix()
        if values is not None and n in values:
            v=values[n]
            if 'neutral_local_quaternion_xyzw'in joints[n]:r=R.from_quat(joints[n]['neutral_local_quaternion_xyzw']).as_matrix();delta=[-v[0],v[1]*mirror,v[2]*mirror]
            else:delta=[joints[n]['rest_flex_degrees']-v[0],v[1]*mirror,v[2]*mirror]
            r=r@R.from_euler('xyz',delta,degrees=True).as_matrix()
        m=np.eye(4);m[:3,:3]=r;m[:3,3]=p-r@p
        if b.get('parent'):m=matrix(b['parent'])@m
        cache[n]=m;return m
    for n in bones:matrix(n)
    return cache

def joint_points(geo,contract,side,values):
    ms=matrices(geo,contract,side,values);out={}
    for digit,d in contract['hands'][side]['digits'].items():
        points=[]
        for j in d['joints']:
            inv=np.asarray(j['inverse_bind_column_major']).reshape(4,4).T;points.append((ms[j['name']]@inv@np.r_[j['head_bind'],1])[:3])
        j=d['joints'][-1];inv=np.asarray(j['inverse_bind_column_major']).reshape(4,4).T;points.append((ms[j['name']]@inv@np.r_[j['tip_bind'],1])[:3]);out[digit]=np.asarray(points)
    return out


def contact_corrective(geo,skin,posed,ms,hand):
    """Mirror the optional native post-skin corrective for offline inspection."""
    corrective=skin.get('contactCorrectiveR45')
    if not corrective:return posed
    parents={b['name']:b.get('parent')for b in geo['minecraft:geometry'][0]['bones']}
    distance=0.
    for name,target in corrective['local_quaternion_xyzw'].items():
        q=R.from_matrix(ms[parents[name]][:3,:3].T@ms[name][:3,:3]).as_quat()
        distance=max(distance,2*np.arccos(np.clip(abs(q@np.asarray(target)),0,1)))
    weight=float(np.clip(1-distance/np.radians(corrective['activation_degrees']),0,1));weight=weight*weight*(3-2*weight)
    if weight<=0:return posed
    rows=np.asarray(corrective['vertex_index_position_normal_delta']);result=posed.copy()
    local=rows[:,1:4]*[-1,1,1]/16
    result[rows[:,0].astype(int)]+=weight*(local@ms[hand][:3,:3].T)
    return result
