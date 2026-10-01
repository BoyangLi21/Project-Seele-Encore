"""Actual rig/mesh calibration for a newly authored paired scene, no BVH poses."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44/combat/tv_exchange'
ASSETS=ROOT/'artifacts/rebuild_r44/network_runtime/private_resources/assets/projectseele'
C=np.array([[1.,0,0],[0,0,-1],[0,1,0]]);S=5/16
MAP=np.eye(4);MAP[:3,:3]=C*S;INV=np.linalg.inv(MAP)
EXCLUDE={'knife','lance','cannon','n2','entry_plug','rifle'}


def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()


def raw_rig(asset):
    path=ASSETS/'geo'/(asset+'.geo.json');data=json.loads(path.read_text('utf8'));rows=data['minecraft:geometry'][0]['bones'];rig={row['name']:row for row in rows};pivots={n:np.asarray(b['pivot'],float)*[-1,1,1] for n,b in rig.items()};matrices={}
    def matrix(name):
        if name in matrices:return matrices[name]
        p=pivots[name];q=R.from_euler('xyz',np.asarray(rig[name].get('rotation',[0,0,0]))*[-1,-1,1],degrees=True).as_matrix();m=np.eye(4);m[:3,:3]=q;m[:3,3]=p-q@p
        parent=rig[name].get('parent');matrices[name]=matrix(parent)@m if parent else m;return matrices[name]
    for name in rig:matrix(name)
    return rig,pivots,matrices,path


def fixture(asset,key,physical):
    rig,pivots,neutral,geo=raw_rig(asset);names=list(rig);path=ASSETS/'mesh'/(asset+'.mesh.json');mesh=json.loads(path.read_text('utf8'));vertices=[];uv=[];ids=[];weights=[];parts={}
    for name,part in mesh['parts'].items():
        if name in EXCLUDE or name not in rig:continue
        rows=np.asarray(part['vertices'],float).reshape(-1,mesh['stride']);source=(rows[:,:3]+part['pivot'])*[-1,1,1]
        start=len(vertices)
        if key=='sachiel':
            source_ids=np.asarray(mesh['skin']['indices']).reshape(-1,4);source_weights=np.asarray(mesh['skin']['weights']).reshape(-1,4)
            skin_names=mesh['skin']['bones'];palette=np.asarray([neutral[n] for n in skin_names]);homogeneous=np.c_[source,np.ones(len(source))]
            transformed=np.einsum('vkij,vj->vki',palette[source_ids],homogeneous)*source_weights[:,:,None];posed=transformed.sum(1)[:,:3]
            ids.extend(np.vectorize(lambda i:names.index(skin_names[i]))(source_ids).tolist());weights.extend(source_weights.tolist())
        else:
            posed=(np.c_[source,np.ones(len(source))]@neutral[name].T)[:,:3];ids.extend([[names.index(name),0,0,0]]*len(source));weights.extend([[1.,0,0,0]]*len(source))
        vertices.extend((posed@(C*S).T).tolist());uv.extend(rows[:,3:5].tolist());parts[name]=dict(begin=start,end=len(vertices))
    vertices=np.asarray(vertices);ids=np.asarray(ids);weights=np.asarray(weights);heads={n:((neutral[n]@np.r_[pivots[n],1])[:3]@(C*S).T) for n in names}
    joints={}
    for side in ('l','r'):
        for family,upper,lower,end,marker,fallback in [
            ('arm','arm_','forearm_','hand_','r30_elbow_socket_',np.array([-23.489652 if side=='l' else 23.489652,123.435069,7.737214])),
            ('leg','leg_','shin_','foot_','r30_knee_socket_',pivots['shin_'+side]+[0,11.4,0])]:
            point=pivots.get(marker+side,fallback if key!='sachiel' else pivots[lower+side])
            joint=(neutral[upper+side]@np.r_[point,1])[:3]@(C*S).T
            joints[family+'_'+side]=dict(upper=heads[upper+side].tolist(),joint=joint.tolist(),end=heads[end+side].tolist(),
                lengths=[float(np.linalg.norm(heads[upper+side]-joint)),float(np.linalg.norm(heads[end+side]-joint))],
                measured_axis=(C@np.array([1.,0,0])).tolist(),game_joint_model=point.tolist())
    toe={};hand={}
    for side in ('l','r'):
        if key=='sachiel':
            foot_bone=names.index('foot_'+side);mask=(np.where(ids==foot_bone,weights,0).sum(1)>.8);foot=vertices[mask]
        else:
            part=parts['foot_'+side];foot=vertices[part['begin']:part['end']]
        low=foot[:,2].min();front=foot[foot[:,1]>=np.percentile(foot[:,1],85)];patch=front[front[:,2]<=front[:,2].min()+.35]
        toe[side]=dict(rest=patch.mean(0).tolist(),offset=(patch.mean(0)-heads['foot_'+side]).tolist(),rest_floor=float(low),vertices=foot.tolist())
        if key=='sachiel':
            hand_bone=names.index('hand_'+side);mask=(np.where(ids==hand_bone,weights,0).sum(1)>.8);points=vertices[mask]
        else:
            part=parts['hand_'+side];points=vertices[part['begin']:part['end']]
        center=points.mean(0);hand[side]=dict(pivot=heads['hand_'+side].tolist(),surface=center.tolist(),offset=(center-heads['hand_'+side]).tolist())
    masses={row['name']:float(row['mass']) for row in physical['bodies']};centres={}
    for name in masses:
        if key=='sachiel':mask=np.where(ids==names.index(name),weights,0).sum(1)>.65;points=vertices[mask]
        else:
            part=parts.get(name);points=vertices[part['begin']:part['end']] if part else np.asarray([heads[name]])
        centres[name]=(points.mean(0) if len(points) else heads[name]).tolist()
    surface=None
    if key=='sachiel':
        chest=names.index('torso_upper');mask=np.where(ids==chest,weights,0).sum(1)>.95;eligible=np.flatnonzero(mask)
        pool=vertices[eligible];height=heads['torso_upper'][2];front=pool[:,1].max();target=np.array([0,front,height])
        selected=int(eligible[np.argmin(np.sum((pool-target)**2,axis=1))]);surface=dict(vertex=selected,rest=vertices[selected].tolist(),bone='torso_upper')
    bones=[dict(name=n,parent=rig[n].get('parent'),head=heads[n].tolist(),pivot_model=pivots[n].tolist(),neutral_model=neutral[n].tolist()) for n in names]
    return dict(name=asset,key=key,bones=bones,vertices=vertices.tolist(),faces=np.arange(len(vertices)).reshape(-1,3).tolist(),uv=uv,
        influences=ids.tolist(),weights=weights.tolist(),joints=joints,toes=toe,hands=hand,masses=masses,mass_centres=centres,chest_surface=surface,
        texture=str((ASSETS/'textures/entity'/(asset+'.png')).resolve()),geo_sha256=sha(geo),mesh_sha256=sha(path),
        skin_scope='Native four-weight indices used; Blender preserve-volume evaluator for paired scene' if key=='sachiel' else 'Exact rigid parts; late native seam stitching remains a separate runtime check')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ART/'blocking_v1');args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    physics_path=ROOT/'.Codex/r44-combat-query-server/projectseele-local-maps/articulated_bodies_r35.json';physics=json.loads(physics_path.read_text('utf8'))['models']
    actors=[fixture('eva_unit01','1',physics['1']),fixture('sachiel','sachiel',physics['sachiel'])]
    document=dict(schema='projectseele.tv-exchange-fixture.r44',units='Minecraft blocks, Blender Z up, +Y forward',fps=30,duration=8,
        actors=actors,physics_sha256=sha(physics_path),source='Current original rig/mesh proportions and measured sockets. Newly authored world targets; no BVH rotations loaded.',
        quality='OLD_MOTION_VISUAL_FAIL. This is a new scene calibration fixture, not an accepted performance.',
        controls=['root/COM','chest','head','left/right toe','left/right palm/fist','independent elbow/knee pole','paired parry/chest surface'])
    (args.out/'fixture.json').write_text(json.dumps(document,separators=(',',':')),'utf8')
    summary=[dict(actor=a['name'],bones=len(a['bones']),vertices=len(a['vertices']),joints=a['joints'],toes=a['toes']) for a in actors]
    for actor in summary:
        for toe in actor['toes'].values():toe.pop('vertices',None)
    (args.out/'calibration_summary.json').write_text(json.dumps(summary,indent=2),'utf8');print(json.dumps([dict(actor=a['name'],bones=len(a['bones']),vertices=len(a['vertices']))for a in actors]))


if __name__=='__main__':main()
