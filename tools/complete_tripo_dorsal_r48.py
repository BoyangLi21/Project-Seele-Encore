"""Fit working rear capsule hatches and measured jet sockets on the supplied UN surface."""
from pathlib import Path
import copy,json
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r48'
OUT=BASE/'un_native_candidate'

def recessed_liner(centre,axis,radius,texture):
    image=np.asarray(Image.open(texture).convert('RGB'));neutral=(image.max(2)-image.min(2)<12)&(image.mean(2)>25)&(image.mean(2)<85)
    ys,xs=np.nonzero(neutral);uv=[(float(xs[0])+.5)/image.shape[1],(float(ys[0])+.5)/image.shape[0]]if len(xs)else[.5,.5]
    tangent=np.array([0,axis[2],-axis[1]]);across=np.cross(tangent,axis);rows=[]
    def point(r,t,depth):return across*r*np.cos(t)+tangent*r*np.sin(t)+axis*depth
    def triangle(a,b,c):
        normal=np.cross(b-a,c-a);normal/=np.linalg.norm(normal)
        for v in (a,b,c):rows.extend([*(v*[-1,1,1]),*uv,*(normal*[-1,1,1])])
    # A shallow receiver lip stays in the new faceted shell. The old UN
    # liner carried a twelve-metre tube from a different torso.
    n=96;outer=radius+.7;inner=radius-.3;depth=1.4
    for i in range(n):
        a=i*2*np.pi/n;b=(i+1)*2*np.pi/n
        p=[point(outer,a,.08),point(outer,b,.08),point(inner,b,.08),point(inner,a,.08)]
        triangle(p[0],p[1],p[2]);triangle(p[0],p[2],p[3])
        p=[point(inner,a,.08),point(inner,b,.08),point(inner,b,-depth),point(inner,a,-depth)]
        triangle(p[0],p[2],p[1]);triangle(p[0],p[3],p[2])
        triangle(point(0,0,-depth),point(inner,b,-depth),point(inner,a,-depth))
    return dict(pivot=(centre*[-1,1,1]).tolist(),vertices=rows)

def main():
    profile=json.loads((BASE/'runtime/projectseele-local-maps/eva_dorsal_r30.json').read_text())
    body=json.loads((OUT/'projectseele-local-maps/eva_body_r44.json').read_text())
    report=[]
    for key,name,short,y,z in [(3,'eva_prototype','un00',.80,.052093954),(4,'eva_un01','un01',.80,.088510725)]:
        asset=OUT/'assets/projectseele';mesh_path=asset/'mesh'/f'{name}.mesh.json'
        mesh=json.loads(mesh_path.read_text());geo_path=asset/'geo'/f'{name}.geo.json';geo=json.loads(geo_path.read_text())
        original=json.loads((BASE/'assets/assets/projectseele/mesh'/f'{name}.mesh.json').read_text())
        source=np.load(BASE/'tripo_pipeline'/short/'lod0_geometry.npz')['vertices'];scale=192/np.ptp(source[:,1])
        centre=np.array([0,y,z])*scale;axis=np.array([0,.939692621762824,.3420201406416154]);tangent=np.array([0,axis[2],-axis[1]])
        radius=4.6;hinge=centre-np.array([radius+1,0,0]);cover=[];removed=0
        # Cut the actual outer back skin. Closed state uses those exact faces;
        # no solid old plate remains beneath the animated lid.
        for part_name,part in list(mesh['parts'].items()):
            owner=part_name.removeprefix('tripo_blend_')
            if owner not in ('torso_upper','torso_lower'):continue
            a=np.asarray(part['vertices']).reshape(-1,3,8);p=(a[:,:,:3]+part['pivot'])*[-1,1,1]
            mid=p.mean(1);delta=mid-centre;depth=delta@axis;radial=delta-depth[:,None]*axis
            normal=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-12)
            keep=(np.linalg.norm(radial,axis=1)<radius)&(abs(depth)<7)&(mid[:,2]>centre[2]-3)&(normal[:,2]>.1)
            if not np.any(keep):continue
            moving=a[keep].copy();moving[:,:,:3]=(p[keep]-hinge)*[-1,1,1];cover.append(moving);removed+=int(keep.sum())
            part['vertices']=a[~keep].ravel().tolist()
            if part_name in mesh['jointSkins']:
                for influence,values in mesh['jointSkins'][part_name]['influences'].items():
                    mesh['jointSkins'][part_name]['influences'][influence]=np.asarray(values).reshape(-1,3)[~keep].ravel().tolist()
        if removed<20:raise ValueError(f'{name}: no actual back skin was cut')
        mesh['parts']['dorsal_cover']=dict(pivot=(hinge*[-1,1,1]).tolist(),vertices=np.concatenate(cover).ravel().tolist())
        # Retain the existing recessed mechanical bore, relocated to the new
        # measured shell. UVs remain on the same original user texture atlas.
        liner=recessed_liner(centre,axis,radius,asset/'textures/entity'/f'{name}.png')
        mesh['parts']['dorsal_liner']=liner
        spec=dict(centre=(centre*[-1,1,1]).tolist(),outward=axis.tolist(),hinge=(hinge*[-1,1,1]).tolist(),hinge_axis=tangent.tolist(),open_angle_degrees=-105,radius_model=radius)
        profile['profiles'][name]={k:v for k,v in spec.items()if k!='radius_model'};mesh['r13_dorsal_socket']=spec
        bones=geo['minecraft:geometry'][0]['bones'];by_name={b['name']:b for b in bones}
        for n,point in [('dorsal_cover',hinge),('dorsal_liner',centre)]:
            bone=by_name.get(n)
            if bone is None:bone=dict(name=n,parent='torso_upper');bones.append(bone);by_name[n]=bone
            bone.update(parent='torso_upper',pivot=(point*[-1,1,1]).tolist())
        if key==4:
            # Nozzles belong to the supplied shoulder pods, not phantom sole
            # thrusters. Their complete imported shell remains on the pylon.
            for side,sign in [('l',-1),('r',1)]:
                point=np.array([sign*.136,.779,.109])*scale
                n='r30_thruster_'+side;by_name[n].update(parent='pylon_'+side,pivot=(point*[-1,1,1]).tolist())
                spec.setdefault('jet_sockets',{})[side]=point.tolist()
            bones.append(dict(name='tripo_thruster_measured_r48',parent='root',pivot=[0,0,0]))
        mesh['triangleCount']=sum(len(p['vertices'])//24 for p in mesh['parts'].values())
        mesh['tripo_r48_candidate']=False;mesh['asset_revision']=48
        mesh_path.write_text(json.dumps(mesh,separators=(',',':')),'utf8');geo_path.write_text(json.dumps(geo,indent=2),'utf8')
        body['rigs'][str(key)]=[{k:v for k,v in b.items()if k in ('name','parent','pivot','rotation')}for b in bones]
        gameplay_path=OUT/'projectseele-local-maps'/f'eva_gameplay_r44_{key}.json';gameplay=json.loads(gameplay_path.read_text())
        gameplay['rig_contract_r44']=body['rigs'][str(key)];gameplay_path.write_text(json.dumps(gameplay,separators=(',',':')),'utf8')
        report.append(dict(model=name,removed_actual_back_faces=removed,closed_cover_same_source_faces=True,profile=spec,native_verified=False))
    (OUT/'projectseele-local-maps/eva_body_r44.json').write_text(json.dumps(body,separators=(',',':')),'utf8')
    (OUT/'projectseele-local-maps/eva_dorsal_r30.json').write_text(json.dumps(profile,indent=2),'utf8')
    physics_path=OUT/'projectseele-local-maps/articulated_bodies_r35.json';physics=json.loads(physics_path.read_text())
    for key in (3,4):physics['models'][str(key)]['render_rig']=body['rigs'][str(key)]
    physics_path.write_text(json.dumps(physics,separators=(',',':')),'utf8')
    (OUT/'dorsal_integration.json').write_text(json.dumps(report,indent=2),'utf8')
    print([(r['model'],r['removed_actual_back_faces'])for r in report])

if __name__=='__main__':main()
