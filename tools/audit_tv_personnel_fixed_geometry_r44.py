"""Native authored deck/guards vs every actual moving cage state interval.

Monotone coordinate endpoint unions bound all motion between the121 samples.
The registered primitives are used, never full-cube approximations.
"""
from pathlib import Path
import argparse,json,hashlib,numpy as np
from audit_tv_cage_space_r44 import motion
from build_tv_shoulder_shells_r44 import box_vertices
from author_tv_shoulder_installation_r44 import prism_hits_triangle

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44/hangar_machinery'


def hits(a,b):
    return np.all((a[:,1]>b[0]+1e-6)&(a[:,0]<b[1]-1e-6),axis=1)


def main(asset,operations,body,out):
    out=Path(out)
    if out.exists():raise ValueError('Fresh proof epoch required')
    d=json.loads(Path(asset).read_text('utf8'));ops=json.loads(Path(operations).read_text('utf8'))
    actors=json.loads(Path(body).read_text('utf8'))['actors']
    native=json.loads((ART/'tv_personnel_deck_native_v1/native_union_readback/full_native_collision_shapes.json').read_text())
    native.update(json.loads((ART/'tv_personnel_guard_native_v1/native_union_readback/native64.json').read_text()))
    permanent=[];owners=[]
    for op in ops:
        if 'personnel_entry_gate' in op['role']:continue
        for b in native[op['after']]:
            permanent.append(np.array(b).reshape(2,3)+op['position']);owners.append(op['position'])
    permanent=np.array(permanent);motion_hits=[];body_hits=[];capsule_hits=[];checks=[]
    frames=json.loads((ROOT/'artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2/semantic_frame.json').read_text('utf8'))['bays']
    changed={'platform_r','platform_l','platform_2_r','fixed_support_2_r','staff_deck_bearings_l','staff_deck_bearings_r'}
    for variant in range(3):
        origin=np.array([-11.5+42*variant,-442.96,-239.5]);actor=actors[str(variant)]
        triangles=np.concatenate([np.array([t['world_vertices'] for t in p['top_band_triangles']]) for p in actor['parts'].values()])
        tri_lo,tri_hi=triangles.min(1),triangles.max(1)
        if not all(p['complete_submitted_part_triangles'] for p in actor['parts'].values()):raise ValueError('Incomplete actor triangles')
        for name,p in actor['parts'].items():
            part_tri=np.array([t['world_vertices'] for t in p['top_band_triangles']])
            part_bound=np.array(p['world_bounds']).reshape(2,3)
            for i in np.flatnonzero(hits(permanent,part_bound)):
                b=permanent[i];possible=np.flatnonzero(np.all((part_tri.max(1)>=b[0]-.003)&(part_tri.min(1)<=b[1]+.003),axis=1))
                for t in possible:
                    if prism_hits_triangle(box_vertices(b),part_tri[t],.003):
                        body_hits.append({'variant':variant,'new_world_owner':owners[int(i)],'actual_body_part':name,'triangle':int(t)})
        plug=np.array(frames[variant]['capsule_sweep_negative'])
        for i in np.flatnonzero(hits(permanent,plug)):
            capsule_hits.append({'variant':variant,'new_world_owner':owners[int(i)]})
        for c in d['components']:
            if c.get('variant',variant)!=variant or c['part'].startswith('thin_side_rails'):continue
            local=np.array(d['collision_parts'][c['part']]);name=c['part']
            if c['motion']=='fixed' and name in changed:
                world=local+origin;near=0
                for b in world:
                    possible=np.flatnonzero(np.all((tri_hi>=b[0]-.003)&(tri_lo<=b[1]+.003),axis=1));near+=len(possible)
                    for i in possible:
                        if prism_hits_triangle(box_vertices(b),triangles[i],.003):body_hits.append({'variant':variant,'part':name,'triangle':int(i)})
                    plug=np.array(frames[variant]['capsule_sweep_negative'])
                    if np.all((b[1]>plug[0])&(b[0]<plug[1])):capsule_hits.append({'variant':variant,'part':name,'bounds':b.tolist()})
                checks.append({'variant':variant,'changed_fixed_part':name,'physical_boxes':len(world),'actual_body_triangles':len(triangles),'broad_triangle_pairs':near})
            if c['motion']=='fixed':continue
            for first,last in zip(np.linspace(0,1,121)[:-1],np.linspace(0,1,121)[1:]):
                start=local+origin+motion(c,float(first));end=local+origin+motion(c,float(last))
                swept=np.stack((np.minimum(start[:,0],end[:,0]),np.maximum(start[:,1],end[:,1])),axis=1)
                broad=np.stack((swept[:,0].min(0),swept[:,1].max(0)))
                candidates=np.flatnonzero(hits(permanent,broad))
                for i in candidates:
                    matches=np.flatnonzero(hits(swept,permanent[i]))
                    if len(matches):motion_hits.append({'variant':variant,'part':name,'interval':[float(first),float(last)],'new_world_owner':owners[int(i)],'box_count':len(matches)})
    out.mkdir(parents=True)
    report={'inputs':{str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (asset,operations,body)},
            'native_permanent_boxes':len(permanent),'changed_fixed_actual_body_checks':checks,'actual_triangle_hits':body_hits,
            'complete_capsule_envelope_hits':capsule_hits,'moving_vs_permanent_interval_hits':motion_hits,
            'intervals_per_moving_part':120,'continuous_bound':'Every translation coordinate is monotone; union of each physical box endpoints contains every intermediate position.',
            'native_passed':False,'preapply_ready':False,'remaining':['whole player standing/headroom coverage','complete current world and carrier/crane/ram interfaces','green inspection access and valid support joints','producer parity/source/BEs/actual entities','real native occupancy/door/prepare and motion']}
    (out/'contract.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({'actual_body_hits':len(body_hits),'capsule_envelope_hits':len(capsule_hits),'motion_interval_hits':len(motion_hits),'first_motion':motion_hits[:1]}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('asset','operations','body','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();main(a.asset,a.operations,a.body,a.out)
