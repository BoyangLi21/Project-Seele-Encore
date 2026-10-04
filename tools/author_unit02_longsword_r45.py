"""A separate long-blade candidate; original knife and twin-blade assets stay intact."""
from pathlib import Path
import argparse,hashlib,json,shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    source=ROOT/'run/resourcepacks/eva_real_model/assets/projectseele/mesh/eva02_special_weapon.mesh.json'
    texture=ROOT/'run/resourcepacks/eva_real_model/assets/projectseele/textures/entity/eva02_weapons.png'
    original=json.loads(source.read_text());part=original['parts']['lance'];tri=np.array(part['vertices']).reshape(-1,3,8)
    blade=tri[tri[:,:,:3].mean(axis=1)[:,1]<-11].copy()
    blade[:,:,1]=-10+(blade[:,:,1]+10)*2.2
    blade[:,:,6]/=2.2;blade[:,:,5:8]/=np.linalg.norm(blade[:,:,5:8],axis=2,keepdims=True)
    rows=blade.reshape(-1,8).tolist()
    def triangle(x,y,z,uv):
        n=np.cross(np.asarray(y)-x,np.asarray(z)-x);n/=np.linalg.norm(n)
        for p in (x,y,z):rows.append([*p,*uv,*n])
    def lathe(profile,uv,segments=32):
        rings=[]
        for y,rx,rz in profile:
            rings.append([np.array([rx*np.cos(t),y,rz*np.sin(t)])for t in np.linspace(0,2*np.pi,segments,endpoint=False)])
        for first,last in zip(rings,rings[1:]):
            for i in range(segments):
                j=(i+1)%segments;triangle(first[i],last[i],last[j],uv);triangle(first[i],last[j],first[j],uv)
        for ring,sign in [(rings[0],-1),(rings[-1],1)]:
            centre=np.array([0,ring[0][1],0])
            for i in range(segments):
                j=(i+1)%segments;triangle(centre,ring[j if sign<0 else i],ring[i if sign<0 else j],uv)
    dark=[.9,.5];silver=[.7,.5];red=[.1,.5]
    # Bevelled load-bearing collar and guard, then a straight ergonomic grip.
    lathe([(-12,3.7,1.8),(-11.6,4.2,2.1),(-9.3,4.2,2.1),(-8.9,3.7,1.8)],silver,8)
    lathe([(-9.2,5.2,1.6),(-8.7,6.2,2.0),(-7.5,6.2,2.0),(-7,5.2,1.6)],dark,8)
    grip=[(-7,1.0,1.2),(-6.3,1.1,1.45)]
    for y in np.linspace(-5.7,12.3,13):
        grip.extend([(y,1.1,1.45),(y+.15,1.2,1.56),(y+.4,1.2,1.56),(y+.55,1.1,1.45)])
    grip.extend([(13.5,1.1,1.45),(14.2,1.0,1.2)]);lathe(grip,dark)
    lathe([(13.5,1.6,1.4),(14,2.2,1.8),(16.2,2.2,1.8),(16.8,1.5,1.3)],silver,12)
    lathe([(-6.5,1.15,1.55),(-6.1,1.22,1.62),(-5.6,1.22,1.62)],red)
    mesh=dict(format_version=original['format_version'],source='R45 original separate longsword with adapted CC-BY Rainbow_Slakot EVA-02 blade; new straight grip/collar/pommel by Project SEELE',model_height=original.get('model_height',100),stride=8,
              parts={'lance':dict(pivot=part['pivot'],vertices=np.asarray(rows).reshape(-1).tolist())},triangle_count=len(rows)//3)
    (a.out/'eva02_longsword.mesh.json').write_text(json.dumps(mesh,separators=(',',':')))
    shutil.copy2(texture,a.out/'eva02_longsword.png')
    v=np.asarray(rows);points=v[:,:3]*[-1,1,1]*5/16;points[:,1]-=points[:,1].min();height=points[:,1].max()
    np.savez_compressed(a.out/'sword_preview.npz',vertices=points,uv=v[:,3:5])
    (a.out/'manifest.json').write_text(json.dumps([dict(file='sword_preview',model='eva02_weapons',camera_target=[0,0,float(height*.5)],camera_offset=[12,60,8],scale=float(height*1.18))]))
    (a.out/'grip_and_source.json').write_text(json.dumps(dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),texture_source_sha256=hashlib.sha256(texture.read_bytes()).hexdigest(),
        source_attribution='Rainbow_Slakot, EVA-02 (rebuild version, not rigged), CC Attribution; see docs/ASSETS.md',original_files_changed=False,part='lance',source_pivot=part['pivot'],
        handle_centre_local=[0,3.5,0],handle_axis_local=[0,1,0],blade_direction_local=[0,-1,0],intended_variant=2,intended_weapon_id=6,
        original_knife_replaced=False,game_attachment_installed=False,visual_accepted=False,triangles=mesh['triangle_count']),indent=2))
    print('Separate sword candidate:',mesh['triangle_count'],'triangles; original files unchanged')

if __name__=='__main__':main()
