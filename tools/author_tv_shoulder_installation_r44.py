"""Six accessible locked-pose shoulder contacts and solid green clevis connections."""
from pathlib import Path
import hashlib,json,math
import numpy as np
from scipy.spatial import ConvexHull

ROOT=Path(__file__).resolve().parents[1]
NATIVE=ROOT/'artifacts/rebuild_r44/space_photos/tv_cage_locked_lens_vanilla_v2/20261001_022427'
OUT=ROOT/'artifacts/rebuild_r44/facility_transit_r44/hangar_shoulder_contact_v3'
OLD=ROOT/'artifacts/rebuild_r44/facility_transit_r44/hangar_shoulder_contact_v2/contacts.json'


def inside(p,triangles):
    direction=np.array([1.,.013,.017]);direction/=np.linalg.norm(direction)
    hits=[]
    for a,b,c in triangles:
        e,f=b-a,c-a;h=np.cross(direction,f);det=np.dot(e,h)
        if abs(det)<1e-9:continue
        s=p-a;u=np.dot(s,h)/det
        if u<0 or u>1:continue
        q=np.cross(s,e);v=np.dot(direction,q)/det
        if v<0 or u+v>1:continue
        t=np.dot(f,q)/det
        if t>1e-6:hits.append(round(float(t),5))
    return len(set(hits))%2==1


def prism_hits_triangle(points,triangle,margin=.003):
    hull=ConvexHull(points)
    faces=hull.simplices
    edge_indices={tuple(sorted((int(t[i]),int(t[(i+1)%3])))) for t in faces for i in range(3)}
    edges=[points[b]-points[a] for a,b in edge_indices]
    tri_edges=[triangle[(i+1)%3]-triangle[i] for i in range(3)]
    axes=[np.cross(points[b]-points[a],points[c]-points[a]) for a,b,c in faces]
    axes.append(np.cross(tri_edges[0],tri_edges[1]))
    axes.extend(np.cross(a,b) for a in edges for b in tri_edges)
    for axis in axes:
        length=np.linalg.norm(axis)
        if length<1e-9:continue
        axis/=length;u=points@axis;v=triangle@axis
        if u.max()+margin<v.min() or v.max()+margin<u.min():return False
    return True


def mesh_conflicts(prism,triangles,margin=.003):
    lo,hi=prism.min(0),prism.max(0)
    mask=np.all((triangles.max(1)+margin>=lo)&(triangles.min(1)-margin<=hi),axis=1)
    hits=[int(i) for i in np.flatnonzero(mask) if prism_hits_triangle(prism,triangles[i],margin)]
    return hits or ([-1] if inside(prism.mean(0),triangles) else [])


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    path=NATIVE/'r44_hangar_body_surfaces.json';actors=json.loads(path.read_text(encoding='utf8'))['actors']
    old=json.loads(OLD.read_text(encoding='utf8'))['contacts'];rows=[];rejected=[]
    for prior in old:
        variant,side=prior['variant'],prior['side'];a=actors[str(variant)];suffix='l' if side<0 else 'r'
        origin=np.array([a['x'],-442.96,a['z']]);arm=a['parts']['arm_'+suffix];pylon=a['parts']['pylon_'+suffix]
        assert arm['top_band_depth_metres']>=20 and len(arm['top_band_triangles'])*3==arm['submitted_vertices']
        assert pylon['top_band_depth_metres']>=20 and len(pylon['top_band_triangles'])*3==pylon['submitted_vertices']
        armtri=np.array([r['world_vertices'] for r in arm['top_band_triangles']])-origin
        pylontri=np.array([r['world_vertices'] for r in pylon['top_band_triangles']])-origin
        candidates=[]
        for i,t in enumerate(armtri):
            n=np.cross(t[1]-t[0],t[2]-t[0]);area=np.linalg.norm(n)/2
            if area<.15:continue
            n/=np.linalg.norm(n)
            if n@np.array(arm['top_band_triangles'][i]['world_outward_normal'])<0:
                t=t[[0,2,1]];n=-n
            centre=t.mean(0)
            if not(n[1]>.45 and n[0]*side>.10 and centre[1]>50):continue
            points=centre+(t-centre)*.72+n*.006
            boot=np.concatenate([points,points+n*.16])
            end=points.copy();end[:,0]=side*7.80;end[:,1]=53.45+(points[:,1]-points[:,1].mean())*.20
            end[:,2]=centre[2]+(points[:,2]-centre[2])*.80
            clevis=np.concatenate([points+n*.16,end])
            boot_pylon=mesh_conflicts(boot,pylontri);clevis_pylon=mesh_conflicts(clevis,pylontri)
            boot_arm=mesh_conflicts(boot,armtri);clevis_arm=mesh_conflicts(clevis,armtri)
            if boot_pylon or clevis_pylon or boot_arm or clevis_arm:
                rejected.append({'variant':variant,'side':side,'triangle':i,'centre':centre.tolist(),
                    'boot_pylon':boot_pylon,'clevis_pylon':clevis_pylon,'boot_arm':boot_arm,'clevis_arm':clevis_arm})
                continue
            candidates.append((area*n[1],i,t,n,points,clevis,area))
        assert candidates,('No real accessible closed-pose shoulder facet',variant,side)
        score,i,t,n,points,clevis,area=max(candidates,key=lambda r:r[0])
        row=dict(prior)
        row.update({'source_triangle_index':i,'source_triangle_world':(t+origin).tolist(),'source_area_m2':float(area),
            'actual_submitted_tick':a['tick'],'actual_actor_uuid':a['uuid'],
            'exact_geometric_outward_normal_world':n.tolist(),
            'actual_render_normal_world':arm['top_band_triangles'][i]['world_outward_normal'],
            'pad_contact_fixed_gantry_local':points.tolist(),'pad_contact_world':(points+origin).tolist(),
            'contact_centre_fixed_gantry_local':points.mean(0).tolist(),
            'clevis_fixed_gantry_local':clevis.tolist(),'closed_exact_arm_and_pylon_prism_sat_conflicts':0,
            'anchors_override_fixed_gantry_local':[[side*17.4,53.65,float(points.mean(0)[2])+dz] for dz in (-.36,.36)],
            'native_pose_source':str(path),'source_pose_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'mounting':'Actual accessible upper/outboard arm facet; boot and green clevis checked against complete locked-pose arm/pylon triangles, no actor translation or air-chasing servo',
            'reference':'TV paired shoulder seats; source locked_cage sole pose owner must remain active until actual release'})
        rows.append(row)
    resource={'source':str(path),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'contacts':rows,
        'reject_inaccessible_faces':rejected,'status':'MEASURED_LOCKED_POSE_CONTACT_CANDIDATE; full operating sweep/native/artistic review required',
        'world_write_performed':False,'native_passed':False,'visual_passed':False}
    (OUT/'contacts.json').write_text(json.dumps(resource,indent=2),encoding='utf8')
    print(json.dumps({'contacts':len(rows),'rejected':len(rejected),'selected':[(r['variant'],r['side'],r['source_triangle_index'],r['contact_centre_fixed_gantry_local']) for r in rows]}))


if __name__=='__main__':main()
