"""First actual authored triangle across worker lens, with exact sourceparts.

Frozen realcamera pose and currentresource identity are explicit. Includes
actual submitted body triangles/pad triangles, not block-only optical rays.
"""
from pathlib import Path
from collections import Counter
import argparse,json,hashlib,math,numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/hangar_machinery/worker_triangle_visibility_v1'
BASE=ROOT/'artifacts/rebuild_r44'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--resource',type=Path,default=ROOT/'src/main/resources/assets/projectseele/mesh/tv_shoulder_shells_r44.json')
    parser.add_argument('--views',type=Path,default=BASE/'hangar_machinery/tv_role_views_v1/worker_contact_cameras.json');parser.add_argument('--out',type=Path,default=OUT);args=parser.parse_args()
    out=args.out
    out.mkdir(parents=True,exist_ok=True)
    source=args.resource;cage=json.loads(source.read_text('utf8'))
    pad=json.loads((ROOT/'src/main/resources/assets/projectseele/mesh/hangar_shoulder_contacts_r44.json').read_text('utf8'))
    body_path=BASE/'space_photos/whole_tv_cage_and_native_maps_v1/20261001_075014/r44_hangar_body_surfaces.json'
    if not body_path.exists():body_path=BASE/'space_photos/installed_maps_hakone_and_tv_fullbody/20261001_045405/r44_hangar_body_surfaces.json'
    body=json.loads(body_path.read_text('utf8'))['actors'];views=json.loads(args.views.read_text('utf8'));report=[]
    for view_index,view in enumerate(views):
        variant=view_index if len(views)==3 else int(view['file'].split('_')[-2])
        origin=np.array([-11.5+variant*42,-442.96,-239.5]);triangles=[];owners=[];parts=[]
        for component in cage['components']:
            if component.get('variant',variant)!=variant or component['part'].startswith('thin_side_rails'):continue
            name=component['part'];t=np.array(cage['parts'][name]).reshape(-1,3,6)[:,:,:3]+origin
            triangles.extend(t);owners.extend([name]*len(t));parts.append({'part':name,'triangles':len(t),'source_bounds':component['closed_bounds_local']})
        for name,value in pad['parts'].items():
            if not name.startswith('shoulder_pad_'+str(variant)+'_'):continue
            t=np.array(value).reshape(-1,3,6)[:,:,:3]+origin;triangles.extend(t);owners.extend([name]*len(t))
        for name,part in body[str(variant)]['parts'].items():
            if not part.get('complete_submitted_part_triangles'):continue
            t=np.array([q['world_vertices'] for q in part['top_band_triangles']]);triangles.extend(t);owners.extend(['actual_body/'+name]*len(t))
        t=np.array(triangles);owners=np.array(owners);eye=np.array(view['position'])+[0,1.62,0];a=t[:,0];e=t[:,1]-a;f=t[:,2]-a;s=eye-a
        yaw,pitch=map(math.radians,(view['yaw'],view['pitch']));forward=np.array([-math.sin(yaw)*math.cos(pitch),-math.sin(pitch),math.cos(yaw)*math.cos(pitch)]);right=np.array([math.cos(yaw),0,math.sin(yaw)]);up=np.cross(forward,right)
        rows=[];counts=Counter();tangent=math.tan(math.radians(view['fovDegrees'])/2)
        for py in np.linspace(20,700,9):
            for px in np.linspace(20,1260,13):
                ray=forward+right*((px/1280)*2-1)*(16/9)*tangent+up*(1-(py/720)*2)*tangent;ray/=np.linalg.norm(ray)
                h=np.cross(np.broadcast_to(ray,f.shape),f);det=np.sum(e*h,1);safe=np.where(abs(det)>1e-10,det,1)
                u=np.sum(s*h,1)/safe;q=np.cross(s,e);v=np.sum(ray*q,1)/safe;distance=np.sum(f*q,1)/safe
                hit=(abs(det)>1e-10)&(u>=0)&(v>=0)&(u+v<=1)&(distance>.01)
                if hit.any():
                    indices=np.flatnonzero(hit);i=indices[np.argmin(distance[hit])];owner=str(owners[i]);counts[owner]+=1
                    rows.append({'pixel':[float(px),float(py)],'first_part':owner,'distance_m':float(distance[i]),'actual_first_triangle_world':t[i].tolist(),'first_world':(eye+ray*distance[i]).tolist()})
                else:counts['no_authored_mesh_hit']+=1
        report.append({'variant':variant,'real_camera':view,'first_triangle_counts':dict(counts),'sample_count':117,'first_hits':rows,
            'authored_fixed_parts':parts,'scope':'Actual submittedbody+current closed authoredcage/pads, two-sidedtriangle intersections. Fixedworld guard/window/door/otherentity and native backface/shader occlusion remain separate; screencoverage samples are not artisticpass.'})
    (out/'contract.json').write_text(json.dumps({'current_cage_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'actual_body_source':str(body_path),'views':report,'world_write_performed':False,'visual_passed':False},indent=2),encoding='utf8')
    print(json.dumps([{'variant':r['variant'],'first_triangles':r['first_triangle_counts']} for r in report]))


if __name__=='__main__':main()
