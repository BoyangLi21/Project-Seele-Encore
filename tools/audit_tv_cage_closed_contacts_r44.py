"""Measure authored pad gaps against the newly submitted closed/parked arm triangles."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def closest(p,t):
    a,b,c=t;n=np.cross(b-a,c-a);n/=np.linalg.norm(n)
    projected=p-n*np.dot(p-a,n)
    uv=np.linalg.lstsq(np.stack([b-a,c-a],axis=1),projected-a,rcond=None)[0]
    if uv.min()>=0 and uv.sum()<=1:return projected
    candidates=[]
    for u,v in ((a,b),(b,c),(c,a)):
        d=v-u;s=np.clip(np.dot(p-u,d)/np.dot(d,d),0,1);candidates.append(u+s*d)
    return min(candidates,key=lambda q:np.linalg.norm(q-p))


def main():
    p=argparse.ArgumentParser();p.add_argument('--native',type=Path,default=ROOT/'artifacts/rebuild_r44/space_photos/tv_cage_final_gpu_shader_v1/20261001_012720')
    p.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r44/hangar_machinery/tv_shoulder_shells_v1/closed_contact_actual_v2')
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    body_path=args.native/'r44_hangar_body_surfaces.json';bodies=json.loads(body_path.read_text(encoding='utf8'))['actors']
    state=json.loads((args.native/'r44_hangar_contacts.json').read_text(encoding='utf8'))
    pads=json.loads((ROOT/'artifacts/rebuild_r44/facility_transit_r44/hangar_shoulder_contact_v2/contacts.json').read_text(encoding='utf8'))['contacts']
    rows=[]
    for pad in pads:
        variant,side=pad['variant'],pad['side'];a=bodies[str(variant)];suffix='l' if side<0 else 'r'
        gantry=next(r for r in state['actual_server_mechanics'] if r['variant']==variant and r['kind']=='fixed_wet_gantry')
        assert gantry['restraint_progress']==1 and state['units'][variant]['s20_phase']=='PARKED'
        triangles=np.array([t['world_vertices'] for t in a['parts']['arm_'+suffix]['top_band_triangles']])
        points=np.asarray(pad['pad_contact_fixed_gantry_local'])+gantry['position']
        records=[]
        for q in points:
            nearest=[closest(q,t) for t in triangles];distances=[float(np.linalg.norm(q-c)) for c in nearest]
            i=int(np.argmin(distances));t=triangles[i];n=np.cross(t[1]-t[0],t[2]-t[0]);n/=np.linalg.norm(n)
            records.append({'pad_world':q.tolist(),'closest_submitted_arm_world':nearest[i].tolist(),
                'distance_m':distances[i],'signed_actual_facet_gap_m':float(np.dot(q-t[0],n)),'actual_triangle_index':i})
        # The legacy arm guard is a different, retained moving assembly. Its
        # outboard inner face sits at x=9.4; distinguish it from six tiny pads.
        actor_x=float(a['x']);arm_box=np.asarray(a['parts']['arm_'+suffix]['world_bounds']).reshape(2,3)
        body_outer=actor_x-arm_box[0,0] if side<0 else arm_box[1,0]-actor_x
        legacy_gap=9.40-body_outer
        rows.append({'variant':variant,'side':side,'actual_body_tick':a['tick'],'actual_closed':gantry['restraint_progress'],
            'pad_vertices':records,'maximum_nearest_arm_gap_m':max(r['distance_m'] for r in records),
            'old_authored_surface_offset_m':pad['offset_from_actual_surface_m'],
            'legacy_arm_guard_minimum_outboard_gap_m':legacy_gap,
            'outer_C_housing_lower_plane_world_y':gantry['position'][1]+53.05,
            'actual_arm_highest_world_y':arm_box[1,1],
            'housing_above_actual_arm_top_m':gantry['position'][1]+53.05-arm_box[1,1],
            'source_truth':'Actual rendered arm triangles; closed server progress proves no opening, not contact or artistic success'})
    report={'source_native':str(args.native),'actual_body_sha256':hashlib.sha256(body_path.read_bytes()).hexdigest(),
        'rows':rows,'status':'CLOSED_ACTUAL_CONTACT_DIAGNOSTIC_NOT_PASS',
        'contact_passed':False,'visual_passed':False,'world_write_performed':False,
        'next':'Measure all pylon triangles through actual shoulder Y band before authoring an inward green clevis; preserve UUID/actor pose. Existing tiny facet pads and legacy outboard arm guards are separate objects.'}
    (args.out/'contact_gap_contract.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps([{k:v for k,v in r.items() if k!='pad_vertices'} for r in rows]))


if __name__=='__main__':main()
