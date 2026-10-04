"""Author a private shoulder storage chamber from the actual donor surface.

The fitting, pocket subtraction and panel separation are explicit mesh edits.
UVs are interpolated on retained surfaces. The hidden hinge and support are
game-authored mechanics, not a claim that TV shows their complete design.
"""
from pathlib import Path
import argparse,copy,hashlib,json,shutil
import numpy as np


def rod(out,a,b,radius,uv,segments=16):
    a=np.asarray(a,float);b=np.asarray(b,float);axis=b-a;axis/=np.linalg.norm(axis)
    across=np.cross(axis,[1,0,0]if abs(axis[0])<.9 else[0,0,1]);across/=np.linalg.norm(across);other=np.cross(axis,across)
    ring=[np.cos(t)*across+np.sin(t)*other for t in np.linspace(0,2*np.pi,segments,endpoint=False)]
    for i,n in enumerate(ring):
        q=ring[(i+1)%segments]
        for pts,norms in [([a+n*radius,b+n*radius,b+q*radius],[n,n,q]),([a+n*radius,b+q*radius,a+q*radius],[n,q,q]),([a,a+q*radius,a+n*radius],[-axis]*3),([b,b+n*radius,b+q*radius],[axis]*3)]:
            out.extend([np.r_[v,uv,normal]for v,normal in zip(pts,norms)])


def section_hulls(raw):
    from scipy.spatial import ConvexHull
    def cut(poly,bound,above):
        result=[]
        for a,b in zip(poly,np.roll(poly,-1,axis=0)):
            da=(a[1]-bound)*(1 if above else -1);db=(b[1]-bound)*(1 if above else -1)
            if da>=-1e-8:result.append(a)
            if (da>=0)!=(db>=0):result.append(a+(b-a)*(da/(da-db)))
        return result
    source=raw.reshape(-1,3,8);points=raw[:,:3]
    bands=np.linspace(points[:,1].min(),points[:,1].max(),9);sections=[]
    for low,high in zip(bands,bands[1:]):
        vertices=[]
        for tri in source[:,:,:3]:
            poly=cut(tri,low,True)
            if len(poly)>=3:vertices.extend(cut(np.asarray(poly),high,False))
        vertices=np.unique(np.round(vertices,7),axis=0);hull=ConvexHull(vertices)
        sections.append(dict(low=low,high=high,vertices=vertices,hull=hull))
    return sections


def outer_shell(raw, padding=0, work=None):
    """A hollow outer enclosure, without the donor's intersecting inner fins.

    Each small face samples the nearest original surface UV; this is an
    explicit replacement surface, not exact preservation of donor triangles.
    """
    from scipy.spatial import cKDTree
    source=raw.reshape(-1,3,8);centres=source[:,:,:3].mean(1);tree=cKDTree(centres)
    output=[]
    surface_normals=source[:,:,5:8].mean(1);surface_normals/=np.maximum(np.linalg.norm(surface_normals,axis=1)[:,None],1e-12)
    def uv_at(point,normal):
        ids=np.atleast_1d(tree.query(point,k=min(32,len(source)))[1]);tri=source[ids];a,b,c=tri[:,0,:3],tri[:,1,:3],tri[:,2,:3]
        u=b-a;v=c-a;w=point-a;uu=(u*u).sum(1);uv=(u*v).sum(1);vv=(v*v).sum(1);wu=(w*u).sum(1);wv=(w*v).sum(1)
        den=np.maximum(uu*vv-uv*uv,1e-20);s=(wu*vv-wv*uv)/den;t=(wv*uu-wu*uv)/den
        bary=np.stack([1-s-t,s,t],axis=1);candidate=np.einsum('ij,ijk->ik',bary,tri[:,:,:3]);dist=((candidate-point)**2).sum(1)
        dist[(bary<0).any(1)]=np.inf;choices=[(dist,bary)]
        for i,j in [(0,1),(1,2),(2,0)]:
            start=tri[:,i,:3];delta=tri[:,j,:3]-start;f=np.clip(((point-start)*delta).sum(1)/np.maximum((delta*delta).sum(1),1e-20),0,1)
            weight=np.zeros_like(bary);weight[:,i]=1-f;weight[:,j]=f
            choices.append((((start+f[:,None]*delta-point)**2).sum(1),weight))
        alignment=surface_normals[ids]@normal
        penalty=np.where(alignment>.25,0,1000*(.25-alignment))
        best=min(((float((d+penalty).min()),int((d+penalty).argmin()),weight)for d,weight in choices),key=lambda row:row[0])
        return best[2][best[1]]@tri[best[1],:,3:5]
    sections=section_hulls(raw);facets=[]
    if padding:
        from scipy.spatial import HalfspaceIntersection,ConvexHull
        import subprocess
        parts=[]
        for section in sections:
            equations=section['hull'].equations.copy();equations[:,3]-=padding
            vertices=np.unique(np.round(HalfspaceIntersection(equations,section['vertices'].mean(0)).intersections,6),axis=0);hull=ConvexHull(vertices);faces=[]
            for ids,eq in zip(hull.simplices,hull.equations):
                ids=ids.copy();a,b,c=vertices[ids]
                if np.cross(b-a,c-a)@eq[:3]<0:ids=ids[[0,2,1]]
                faces.append(ids.tolist())
            parts.append(dict(vertices=vertices.tolist(),faces=faces))
        input_file=work/'shell_sections.json';output_file=work/'shell_union.json';input_file.write_text(json.dumps(parts))
        with (work/'shell_union.log').open('w') as log:
            subprocess.run(['C:/Program Files/Blender Foundation/Blender 5.1/blender.exe','-b','--python-exit-code','1','--python',str(Path(__file__).with_name('union_knife_cage_shell_r45.py')),'--','--input',str(input_file.resolve()),'--out',str(output_file.resolve())],check=True,stdout=log,stderr=subprocess.STDOUT)
        for face in json.loads(output_file.read_text())['triangles']:
            facets.append((np.asarray(face['vertices']),np.asarray(face['normal'])))
    else:
        for index,section in enumerate(sections):
            vertices=section['vertices'];hull=section['hull']
            for indices,equation in zip(hull.simplices,hull.equations):
                if index>0 and equation[1]<-.99999:continue
                if index<len(sections)-1 and equation[1]>.99999:continue
                facets.append((vertices[indices],equation[:3]))
    for vertices,normal in facets:
        a,b,c=vertices
        if np.cross(b-a,c-a)@normal<0:b,c=c,b
        n=4
        def point(i,j):return a+(b-a)*(i/n)+(c-a)*(j/n)
        for i in range(n):
            for j in range(n-i):
                pieces=[[point(i,j),point(i+1,j),point(i,j+1)]]
                if i+j<n-1:pieces.append([point(i+1,j),point(i+1,j+1),point(i,j+1)])
                for piece in pieces:
                    uv=uv_at(np.mean(piece,axis=0),normal);output.append(np.asarray([np.r_[p,uv,normal]for p in piece]))
    return output


def main():
    p=argparse.ArgumentParser();p.add_argument('--hand',type=Path,required=True);p.add_argument('--body-mesh',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--width-scale',type=float,default=1.4);p.add_argument('--yz-scale',type=float,default=1.0)
    p.add_argument('--storage-fit',type=Path,required=True)
    p.add_argument('--shell-padding',type=float,default=0)
    p.add_argument('--carrier-lift',type=float,default=2.)
    a=p.parse_args()
    for directory in (a.hand,a.hand.parent):
        assert not (directory/'REJECTED_BY_USER.json').exists(),'Rejected model input cannot be reused'
        assert not (directory/'INVALID_PIPELINE.json').exists(),'Incomplete model input cannot be reused'
    source_contract=json.loads((a.hand/'hand_rig_contract.json').read_text())
    assert source_contract['rig']==1,'This authored shoulder mechanism is currently Unit01-only'
    fit=json.loads(a.storage_fit.read_text())
    knife_path=Path(source_contract['knife_attachment_r45']['source_mesh'].replace('\\','/'))
    if not knife_path.is_absolute():knife_path=Path(__file__).resolve().parents[1]/knife_path
    assert fit['knife_sha256']==hashlib.sha256(knife_path.read_bytes()).hexdigest(),'Storage fit belongs to another knife'
    assert fit['body_sha256']==hashlib.sha256(a.body_mesh.read_bytes()).hexdigest(),'Storage fit belongs to another body'
    assert abs(fit['width_scale']-a.width_scale)<1e-5 and abs(fit['yz_scale']-a.yz_scale)<1e-5,'Storage fit and shell dimensions differ'
    shutil.copytree(a.hand,a.out)
    cp=a.out/'hand_rig_contract.json';c=json.loads(cp.read_text());name=f"eva_unit0{c['rig']}";gp=a.out/(name+'.geo.json');g=json.loads(gp.read_text());mesh=json.loads(a.body_mesh.read_text());part=mesh['parts']['pylon_l'];assert 'pylon_l'not in mesh.get('jointSkins',{}),'Weighted pylon needs its own partition adapter'
    # The donor upper pylons are thin fins. Give both shells equal internal
    # width before cutting the door; the measured hilt otherwise breaks
    # through their sides. Preserve the lower mounting and the Y/Z outline.
    for side,centre in [('l',19.24322),('r',-19.24322)]:
        shell=mesh['parts']['pylon_'+side];v=np.array(shell['vertices']).reshape(-1,8);v[:,:3]+=shell['pivot']
        sx=np.full(len(v),a.width_scale);derivative=np.zeros(len(v))
        nx=v[:,5]/sx;v[:,6]-=derivative*nx;v[:,5]=nx;v[:,5:8]/=np.linalg.norm(v[:,5:8],axis=1)[:,None]
        v[:,0]=centre+(v[:,0]-centre)*sx;v[:,:3]-=shell['pivot'];shell['vertices']=np.round(v,7).reshape(-1).tolist()
        v[:,:3]+=shell['pivot']
        v[:,1:3]=[168.,0.]+(v[:,1:3]-[168.,0.])*a.yz_scale
        v[:,6:8]/=a.yz_scale;v[:,5:8]/=np.linalg.norm(v[:,5:8],axis=1)[:,None]
        v[:,:3]-=shell['pivot'];shell['vertices']=np.round(v,7).reshape(-1).tolist()
    raw=np.array(part['vertices']).reshape(-1,8);raw[:,:3]+=part['pivot'];remaining=[];cover=[]
    exterior=raw.reshape(-1,3,8)
    carved=outer_shell(raw,a.shell_padding,a.out)
    for tri in carved:
        front=tri[0,7]<-.25 or (tri[0,6]>.8 and tri[0,7]<0)
        (cover if front else remaining).append(tri)
    assert len(cover)>6 and len(remaining)>6
    # Preserve exact area of the original exterior through both clip planes.
    def area(tris):
        pts=np.asarray(tris)[:,:,:3]
        return float(np.linalg.norm(np.cross(pts[:,1]-pts[:,0],pts[:,2]-pts[:,0]),axis=1).sum()/2)
    original_area=area(exterior);before=area(carved);after=area(cover+remaining);assert abs(after-before)<1e-6
    pivot=np.array([22.7,169.,25.]);bone='r45_knife_hatch_l'
    spec=dict(name=bone,parent='pylon_l',pivot=pivot.tolist())
    assert fit['maximum_convex_hull_violation']<a.shell_padding,'Closed knife does not fit the proposed shell envelope'
    storage=fit['parameters'][:3]
    stored_pitch = float(-np.degrees(fit['parameters'][3]))
    carriage=dict(name='r45_knife_carriage_l',parent='pylon_l',pivot=storage)
    actuator=dict(name='r45_knife_actuator_l',parent='pylon_l',pivot=[21.4,169.,18.])
    g['minecraft:geometry'][0]['bones'].extend([spec,carriage,actuator])
    original_cover=np.asarray(cover).reshape(-1,8);inner=original_cover.copy();inner[:,:3]-=inner[:,5:8]*.03;inner[:,5:8]*=-1;inner=inner.reshape(-1,3,8)[:,[0,2,1]].reshape(-1,8)
    # Add side walls only along the cut edges; UV seams do not create extra walls.
    edges={}
    for tri in np.asarray(cover):
        for u,v in zip(tri,np.roll(tri,-1,axis=0)):
            ku=tuple(np.round(u[:3],6));kv=tuple(np.round(v[:3],6));key=tuple(sorted((ku,kv)))
            edges.setdefault(key,[]).append((u,v))
    walls=[]
    for matches in edges.values():
        if len(matches)!=1:continue
        u,v=matches[0];ui=u.copy();vi=v.copy();ui[:3]-=u[5:8]*.03;vi[:3]-=v[5:8]*.03
        for t in [np.array([u,v,vi]),np.array([u,vi,ui])]:
            n=np.cross(t[1,:3]-t[0,:3],t[2,:3]-t[0,:3]);length=np.linalg.norm(n)
            if length<1e-9:continue
            t[:,5:8]=n/length;walls.extend(t)
    cover_vertices=np.vstack([original_cover,inner,np.asarray(walls)]);cover_vertices[:,:3]-=pivot
    base=np.asarray(remaining).reshape(-1,8);base[:,:3]-=part['pivot'];part['vertices']=np.round(base,7).reshape(-1).tolist()
    mesh['parts'][bone]=dict(pivot=pivot.tolist(),vertices=np.round(cover_vertices,7).reshape(-1).tolist())
    # Dark metal uses an existing opaque dark pixel in the body's own atlas.
    # No official photograph or new texture is embedded in the asset.
    from PIL import Image
    texture=a.body_mesh.parent.parent/'textures/entity'/f'{name}.png'
    pixels=np.asarray(Image.open(texture).convert('RGBA'));height,width=pixels.shape[:2]
    candidates=raw[:,3:5];samples=pixels[np.clip((candidates[:,1]*height).astype(int),0,height-1),np.clip((candidates[:,0]*width).astype(int),0,width-1)]
    score=samples[:,:3].mean(1).astype(float);score[samples[:,3]<250]=1000;uv=candidates[np.argmin(score)]
    fixed=[]
    rod(fixed,[22.7,159,25],[22.7,179,25],.35,uv)
    fixed_surface=np.asarray(remaining).reshape(-1,8)[:,:3]
    for y in [159,179]:
        at=np.array([22.7,y,25.]);points=fixed_surface[abs(fixed_surface[:,1]-y)<3]
        anchor=points[np.argmin(np.linalg.norm(points-at,axis=1))]
        rod(fixed,anchor,at,.25,uv)
    for x in [15.9,19.5]:rod(fixed,[x,169,18.5],[x,189,18.5],.20,uv)
    for y in [169,178,188]:rod(fixed,[15.9,y,18.5],[19.5,y,18.5],.22,uv)
    rod(fixed,[19.5,169,18],[21.4,169,18],.35,uv)
    fixed=np.asarray(fixed);fixed[:,:3]-=part['pivot'];part['vertices']+=np.round(fixed,7).reshape(-1).tolist()
    links=[]
    for y in [163,181]:
        at=np.array([22.7,y,25.]);points=original_cover[abs(original_cover[:,1]-y)<3,:3]
        anchor=points[np.argmin(np.linalg.norm(points-at,axis=1))]
        corner=np.array([23.2,y,anchor[2]])
        rod(links,at,corner,.28,uv);rod(links,corner,anchor,.28,uv)
        rod(links,at+[0,-.7,0],at+[0,.7,0],.6,uv,24)
    links=np.asarray(links);links[:,:3]-=pivot;mesh['parts'][bone]['vertices']+=np.round(links,7).reshape(-1).tolist()
    fork=[];at=np.asarray(carriage['pivot'])
    for x in [-1.6,1.6]:
        rod(fork,at+[x,-5,6],at+[x,4,6],.27,uv)
        rod(fork,at+[x,4,6],at+[x,4,3.2],.27,uv)
    rod(fork,at+[-1.6,-5,6],at+[2.6,-5,6],.40,uv)
    fork=np.asarray(fork);fork[:,:3]-=at;mesh['parts'][carriage['name']]=dict(pivot=at.tolist(),vertices=np.round(fork,7).reshape(-1).tolist())
    shaft=[];at=np.asarray(actuator['pivot']);rod(shaft,at,at+[0,12,0],.27,uv)
    shaft=np.asarray(shaft);shaft[:,:3]-=at;mesh['parts'][actuator['name']]=dict(pivot=at.tolist(),vertices=np.round(shaft,7).reshape(-1).tolist())
    filename=name+'_knife_cage_r45.mesh.json';(a.out/filename).write_text(json.dumps(mesh,separators=(',',':')),encoding='utf8')
    c['knife_mechanism_r45']=dict(bones=[spec,carriage,actuator],body_mesh=filename,source_sha256=hashlib.sha256(a.body_mesh.read_bytes()).hexdigest(),
        exterior_area_before=before,exterior_area_after=after,hinge_native_degrees=35,hinge_axis_native=[0,1,0],reference='https://shop.kotobukiya.co.jp/shop/g/g4934054018925/',
        presented_authored=[18.8,178.,-34.],actuator_length=12.,carriage_actuator_offset_authored=[2.6,-5,6],
        carriage_stored_pitch_degrees=stored_pitch,carriage_lift_model=a.carrier_lift,storage_envelope_fit=fit,
        original_shell_area=original_area,outer_surface_rebuilt=True,uv_sampling='nearest donor surface per tessellated plane',
        upper_shell_width_scale=a.width_scale,shell_yz_scale=a.yz_scale,shell_normal_padding=a.shell_padding,inner_lining_complete=False,clearance_verified=False,visual_accepted=False)
    approach=copy.deepcopy(c['pose_controls']['knife'])
    for digit in ['index','middle','ring','little']:
        approach[digit]=(np.asarray(approach[digit])*[.45,.55,.40]).tolist()
    approach['cup_ring']=[2.];approach['cup_little']=[5.]
    c['pose_controls']['knife_approach']=approach
    cp.write_text(json.dumps(c,indent=2),encoding='utf8');gp.write_text(json.dumps(g,indent=2),encoding='utf8')
    print(json.dumps(c['knife_mechanism_r45']))


if __name__=='__main__':main()
