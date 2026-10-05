"""Fit the supplied connector's three contacts to measured original EVA port surfaces."""
from pathlib import Path
import json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
PIPE=ROOT/'artifacts/rebuild_r48/tripo_pipeline/charger'
ASSETS=ROOT/'artifacts/rebuild_r48/assets/assets/projectseele'

def unit(v):return v/np.linalg.norm(v)

def ray(vertices,camera,direction):
    tri=vertices.reshape(-1,3,3);a=tri[:,0];e=tri[:,1]-a;f=tri[:,2]-a
    h=np.cross(np.broadcast_to(direction,f.shape),f);det=np.sum(e*h,axis=1);safe=abs(det)>1e-10
    inv=np.divide(1,det,out=np.zeros_like(det),where=safe);s=camera-a;u=np.sum(s*h,axis=1)*inv
    q=np.cross(s,e);v=q@direction*inv;t=np.sum(f*q,axis=1)*inv
    valid=safe&(u>=-1e-6)&(v>=-1e-6)&(u+v<=1.000001)&(t>0)
    ids=np.flatnonzero(valid)
    if not len(ids):raise ValueError('Authored marker ray misses the actual mesh')
    i=ids[np.argmin(t[ids])]
    return camera+t[i]*direction

def camera_ray(vertices,pixel,size,scale,camera,target,reflected=False):
    camera=np.array(camera,float);forward=unit(np.array(target)-camera);up=np.array([0,1,0.])
    right=unit(np.cross(forward,up));right*=(-1 if reflected else 1)
    origin=camera+right*(pixel[0]/size-.5)*scale+up*(.5-pixel[1]/size)*scale
    return ray(vertices,origin,forward)

def kernel(vertices,controls,sigma):
    return np.exp(-np.sum((vertices[:,None,:]-controls[None,:,:])**2,axis=2)/(2*sigma*sigma))

def main():
    source=np.load(PIPE/'lod0_geometry.npz');v=source['vertices'].astype(float);faces=source['triangles']
    triangles=v[faces].reshape(-1,3)
    # Pixel centres are selected on the actual orthographic model render,
    # not on the concept art. Surface depth comes from the original triangles.
    tips=np.array([camera_ray(triangles,p,1200,.30,(3,.87,-.70),(.23,.87,-.035))for p in [(448,518),(817,504),(675,726)]])
    centres=v[faces].mean(1);surface_normals=source['normals'].mean(1)
    # Contacts have different lengths: a plane through their tips is NOT the
    # insertion axis. Use the two small end faces, then remove the slight roll.
    cap_normals=[surface_normals[np.argsort(np.linalg.norm(centres-tip,axis=1))[:5]].mean(0)for tip in tips[:2]]
    axis=unit(np.mean(cap_normals,axis=0)*[1,0,1]);right=unit(np.cross([0,1,0],axis));up=unit(np.cross(axis,right))
    source_basis=np.stack([right,up,axis],axis=1)
    desired_basis=np.diag([-1,1,-1]);rotation=desired_basis@source_basis.T
    midpoint=tips.mean(0);flat=(tips-midpoint)@rotation.T
    report=dict(source_tip_centres=tips.tolist(),source_pin_direction=axis.tolist(),source_master_unchanged=True,variants={})
    profiles={}
    for variant,pixels in [(0,[(495,508),(605,508),(550,635)]),(1,[(482,503),(620,503),(550,629)]),(2,[(495,508),(605,508),(550,635)])]:
        native=np.load(PIPE/'power_ports'/f'eva_unit0{variant}_surface.npz')['vertices']
        ports=np.array([camera_ray(native,p,1100,.105,(0,.8,3),(0,.8,.04),True)for p in pixels])*60
        cavity_back=ports[2,2]
        rim=[camera_ray(native,(pixels[2][0]+dx,pixels[2][1]),1100,.105,(0,.8,3),(0,.8,.04),True)*60 for dx in (-68,68)]
        ports[2,2]=sum(p[2]for p in rim)/2
        origin=ports.mean(0);target=ports-origin
        scale=float(np.sum(flat[:,:2]*target[:,:2])/np.sum(flat[:,:2]**2))
        transformed=(v-midpoint)@rotation.T*scale
        # Recessed third socket has its own depth. Move the shell outward so
        # the mouth's outside rim remains outside the armour, then seat tips.
        standoff=.30
        transformed[:,2]+=standoff
        mapped_tips=flat*scale+[0,0,standoff]
        seated=target.copy();seated[:,2]-=.10
        delta=seated-mapped_tips
        # Each tip and its shaft root get the same correction; anchors below
        # the head preserve the original bent handle/cable silhouette.
        controls=np.concatenate([tips,tips-axis*.065,[[0,.64,0],[-.12,.66,.1],[.13,.68,-.05],[0,.70,.15]]])
        corrections=np.concatenate([delta,delta,np.zeros((4,3))])
        sigma=.080
        matrix=kernel(controls,controls,sigma);coeff=np.linalg.solve(matrix+np.eye(len(controls))*1e-9,corrections)
        corrected=transformed+kernel(v,controls,sigma)@coeff
        fit=mapped_tips+kernel(tips,controls,sigma)@coeff
        pin_vertices=np.zeros(len(v),bool);pin_radii=[]
        for index,(tip,radius) in enumerate(zip(tips,(.075,.075,.145))):
            local=v-tip;axial=local@axis;radial=local-axial[:,None]*axis
            extent=np.linalg.norm(radial,axis=1);limit=.024 if index<2 else .035
            selected=(axial>-.058)&(axial<.012)&(extent<limit)
            transformed_radial=radial@rotation.T*scale
            measured=np.quantile(np.linalg.norm(transformed_radial[selected,:2],axis=1),.99)
            radial_scale=min(1,radius/max(measured,1e-8))
            straight=np.zeros_like(corrected);straight[:,:2]=seated[index,:2]+transformed_radial[:,:2]*radial_scale
            straight[:,2]=seated[index,2]-np.minimum(axial,0)*scale
            blend=np.clip((axial+.058)/.022,0,1);blend=blend*blend*(3-2*blend)
            corrected[selected]=corrected[selected]*(1-blend[selected,None])+straight[selected]*blend[selected,None]
            pin_vertices|=selected
            pin_radii.append(dict(radius_m=radius,scale_of_supplied_contact=radial_scale,vertices=int(selected.sum())))
        normals=source['normals'].astype(float).reshape(-1,3)@rotation.T
        points=v[faces].reshape(-1,3)
        # Exact local Jacobian transforms normals through the smooth correction.
        minimum_jacobian=1e9
        for start in range(0,len(points),30000):
            p=points[start:start+30000];k=kernel(p,controls,sigma)
            derivative=-k[:,:,None]*(p[:,None,:]-controls[None,:,:])/(sigma*sigma)
            jac=np.broadcast_to(rotation*scale,(len(p),3,3)).copy()+np.einsum('nki,kj->nji',derivative,coeff)
            minimum_jacobian=min(minimum_jacobian,float(np.linalg.det(jac).min()/scale**3))
            original=source['normals'].reshape(-1,3)[start:start+len(p)]
            n=np.einsum('nij,nj->ni',np.linalg.inv(jac).transpose(0,2,1),original)
            normals[start:start+len(p)]=n/np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-12)
        # Recompute the altered contacts from their actual triangle geometry.
        cross=np.cross(corrected[faces[:,1]]-corrected[faces[:,0]],corrected[faces[:,2]]-corrected[faces[:,0]])
        accumulated=np.zeros_like(corrected)
        for corner in range(3):np.add.at(accumulated,faces[:,corner],cross)
        accumulated/=np.maximum(np.linalg.norm(accumulated,axis=1,keepdims=True),1e-12)
        pin_mask=pin_vertices[faces].reshape(-1)
        geometric=accumulated[faces].reshape(-1,3)
        if np.median(np.sum(geometric*normals,axis=1))<0:geometric=-geometric
        normals[pin_mask]=geometric[pin_mask]
        geo=json.loads((ASSETS/'geo'/f'eva_unit0{variant}.geo.json').read_text())['minecraft:geometry'][0]['bones']
        pivot=next(b['pivot']for b in geo if b['name']=='torso_upper')
        # LocalTriangleMeshLayer consumes reflected-X Bedrock pixels. The
        # existing torso deformation owns both the gun and these markers.
        body_points=(corrected+origin)*16/5
        stored=body_points[faces].reshape(-1,3)*[-1,1,1]-pivot
        uv=source['uv'].reshape(-1,2).copy();uv[:,1]=1-uv[:,1]
        raw=np.concatenate([stored,uv,normals*[-1,1,1]],axis=1)
        doc=dict(format_version=1,stride=8,source='Owner charger.glb; measured three-port fit R48',model_height=192,
                 parts={'torso_upper':dict(pivot=pivot,vertices=np.round(raw,6).ravel().tolist())},triangleCount=len(faces))
        out=ASSETS/'mesh'/f'eva_charger_unit0{variant}_r48.mesh.json';out.write_text(json.dumps(doc,separators=(',',':')),'utf8')
        cable=v[:,1]<.012;tail=corrected[cable].mean(0)+origin
        above=(v[:,1]>.04)&(v[:,1]<.065);tangent=unit(tail-(corrected[above].mean(0)+origin))
        profiles[str(variant)]=dict(origin_native_model_pixels=(origin*16/5).tolist(),
            cable_tail_native_model_pixels=(tail*16/5).tolist(),cable_tangent_native=tangent.tolist(),
            ports_native_model_pixels=(ports*16/5).tolist())
        np.savez_compressed(PIPE/f'charger_fitted_unit0{variant}.npz',vertices=corrected,triangles=faces,uv=source['uv'],normals=normals.reshape(-1,3,3),origin=origin)
        calibration=dict(rotation=rotation.tolist(),scale=scale,midpoint=midpoint.tolist(),controls=controls.tolist(),
            coefficients=coeff.tolist(),sigma=sigma,tips=tips.tolist(),axis=axis.tolist(),seated=seated.tolist(),
            pin_radius_scales=[p['scale_of_supplied_contact']for p in pin_radii],standoff=standoff)
        (PIPE/f'calibration_unit0{variant}.json').write_text(json.dumps(calibration,indent=2),'utf8')
        report['variants'][str(variant)]=dict(uniform_scale_metres=scale,ports_world_local=ports.tolist(),lower_cavity_back_z=cavity_back,
            maximum_tip_centre_error_m=float(np.linalg.norm(fit-seated,axis=1).max()),pin_corrections_m=delta.tolist(),
            contact_radius_adjustments=pin_radii,
            minimum_relative_jacobian_determinant=minimum_jacobian,
            bounds_relative_to_mount=[corrected.min(0).tolist(),corrected.max(0).tolist()],
            actual_render_and_shaft_clearance_verified=False)
    p=ASSETS/'motion/eva_power_ports_r48.json';p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(dict(schema=48,profiles=profiles),indent=2),'utf8')
    (PIPE/'fit_report.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
