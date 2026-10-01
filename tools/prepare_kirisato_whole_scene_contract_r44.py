"""Current-state full landscape proof and exact additive construction protections."""
from pathlib import Path
from collections import Counter
import argparse,gzip,json,math,hashlib,shutil
import numpy as np
from scipy.spatial import cKDTree
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,AIR
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('--source-field',type=Path,required=True);a=p.parse_args()
    assert not (a.plan/'audit.json').exists()
    rows=[json.loads(s)for s in gzip.open(a.plan/'forward.jsonl.gz','rt',encoding='utf8')]
    inverse=[json.loads(s)for s in gzip.open(a.plan/'inverse.jsonl.gz','rt',encoding='utf8')]
    assert len(rows)==len(inverse)==len({tuple(r['pos'])for r in rows})
    for r,b in zip(rows,inverse):assert r['pos']==b['pos'] and r['before']==b['after'] and r['after']==b['before'] and r['before_nbt']==b['after_nbt'] and r['after_nbt']==b['before_nbt']
    w=MeasuredWorld(WORLD)
    for r in rows:w.box(tuple(r['pos']),tuple(r['pos']))
    district=json.loads((a.plan/'new_district.json').read_text('utf8'))
    for b in district['buildings']:
        x,z,X,Z=b['bounds'];w.box((x-3,b['floor']-4,z-4),(X+3,b['roof']+5,Z+5))
    w.load();lo=tuple(min(r['pos'][k]for r in rows)for k in range(3));hi=tuple(max(r['pos'][k]for r in rows)for k in range(3))
    tags=dict(iter_block_entities(WORLD,w.dimension,lo,hi,selected_chunks=set(w.selected)))
    errors=[]
    for r in rows:
        q=tuple(r['pos']);actual=w.block(q);nbt=tags[q].snbt()if q in tags else None
        if actual!=r['before']or nbt!=r['before_nbt']:errors.append(dict(pos=q,expected=r['before'],actual=actual,expected_nbt=r['before_nbt'],actual_nbt=nbt))
    assert not errors,errors[:5]
    assert not any(r['before'].startswith('minecraft:water')for r in rows)
    snapshot=ROOT/'artifacts/rebuild_r44/current_transport_geometry_20261001/native_snapshot.json';transport=json.loads(snapshot.read_text('utf8'))
    shapes={canonical_state(k):v for k,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    occupied=[];unknown=[]
    for r in rows:
        after=canonical_state(r['after']);before=canonical_state(r['before'])
        ab=[]if after in AIR else shapes.get(after);bb=[]if before in AIR else shapes.get(before)
        if ab is None:unknown.append(dict(state=after,pos=r['pos']));continue
        if bb is None:unknown.append(dict(state=before,pos=r['pos']));continue
        if ab and not bb:occupied.append(r['pos'])
    if unknown:
        missing=sorted({r['state']for r in unknown});request=a.plan/'missing_native_state_request.json'
        if not request.exists():request.write_text(json.dumps(dict(states=missing),indent=2),'utf8')
        proof=a.plan/'missing_native_state_negative.json'
        if not proof.exists():proof.write_text(json.dumps(dict(exact_current_and_inverse_passed_before_shape_gate=True,missing_state_cell_counts=dict(Counter(r['state']for r in unknown)),
            actual_native_state_capture_required=True,world_written=False,native_collision_passed=False),indent=2),'utf8')
        raise RuntimeError('Actual native shapes required: '+str(missing))
    xyz=np.array(occupied,dtype=float);conflicts=[];sampled=Counter()
    for mode,halo,below,above in [('TRAIN',6,3,10),('AIRPLANE',64,24,80)]:
        points=[];identities=[]
        for curve in transport['curves']:
            if curve['mode']!=mode:continue
            for q in curve['points']:
                if lo[0]-halo<=q[0]<=hi[0]+halo and lo[2]-halo<=q[2]<=hi[2]+halo and lo[1]-above<=q[1]<=hi[1]+below:
                    points.append(q);identities.append(curve['id'])
        sampled[mode]=len(points)
        if not points or not len(xyz):continue
        data=np.array(points);tree=cKDTree(data[:,[0,2]])
        for q in xyz:
            for i in tree.query_ball_point(q[[0,2]],halo*math.sqrt(2)+1):
                v=data[i]
                if abs(q[0]-v[0])<=halo and abs(q[2]-v[2])<=halo and v[1]-below<q[1]+1 and q[1]<v[1]+above:conflicts.append(dict(pos=q.tolist(),curve=identities[i],mode=mode,actual_curve_point=v.tolist()))
    assert not conflicts,conflicts[:5]
    base=ROOT/'artifacts/rebuild_r44/city_expansion/kirisato_full_service_garden_v13'
    reservations=json.loads((base/'ecology_reservations.json').read_text('utf8'))['reservations']
    for r in json.loads((a.plan/'road_authority.json').read_text('utf8'))['columns']:
        if 'retained_installed_three_metre_approach'not in r.get('source_id',''):continue
        x,z=r['pos'];f=r['native_feet'];reservations.append(dict(bounds=[x,math.floor(f)-4,z,x,math.ceil(f)+5,z],owner=r['source_id'],role='Complete installed actual three-metre entrance spine, surface and usable headroom'))
    for r in json.loads((a.plan/'parcel_components.json').read_text('utf8'))['full_court_columns']:
        x,z=r['pos'];f=r['native_feet'];reservations.append(dict(bounds=[x,math.floor(f)-4,z,x,math.ceil(f)+4,z],owner=r['owner'],role='Actual complete public pavement/apron; adjoining graded natural lawn remains eligible'))
    for r in rows:
        if '/whole_shore/'not in r['owner']:continue
        x,y,z=r['pos'];reservations.append(dict(bounds=[x,y,z,x,y+2,z],owner=r['owner'],role='Exact founded retaining/beam/guard geometry and its immediate fixture clearance'))
    (a.plan/'ecology_reservations.json').write_text(json.dumps(dict(reservations=reservations,all_old_installed_building_roof_street_reservations_inherited=True,
        new_natural_grading_columns_not_blanket_reserved=True,required_before_native_reseed=True,world_written=False),indent=2),'utf8')
    field=np.load(a.source_field/'whole_landscape_heightfield.npz');ox,oz=map(int,field['origin'])
    surfaces=[]
    for r in json.loads((a.plan/'parcel_ground_plan.json').read_text('utf8'))['columns']:
        if not r['role'].startswith('graded_'):continue
        x,z=r['pos'];surfaces.append([x,int(r['target_ground']),z])
    with gzip.open(a.plan/'exact_natural_surface_targets.json.gz','wt',encoding='utf8')as f:json.dump(dict(columns=surfaces,source_field=str(a.source_field.resolve()),source_heightfield_sha256=sha(a.source_field/'whole_landscape_heightfield.npz'),current_world_written=False,future_loader_verified=False,
        scope='Absolute surface soil targets of the whole accepted natural lawn/transition field. Root owns future surface loader integration; no road/building/tree/current water column is inferred from this resource.'),f)
    (a.plan/'retained_full_block_entities.json').write_text(json.dumps([dict(pos=q,full_snbt=tag.snbt())for q,tag in tags.items()],ensure_ascii=False,indent=2),'utf8')
    (a.plan/'delta_provenance.json').write_text(json.dumps(dict(installed=str(base.resolve()),installed_forward_sha256=sha(base/'forward.jsonl.gz'),
        exact_current_cells=len(rows),full_nbt_inverse=True,world_written=False,full_original_city_reapply_allowed=False,
        interpretation='Entire landscape delta measured against current installed K13; building bodies and actual three-metre approaches retained. Original K13 forward must never be replayed.'),indent=2),'utf8')
    outer=json.loads((a.plan/'whole_outer_grade_classification.json').read_text('utf8'));shore=json.loads((a.plan/'whole_waterfront_components.json').read_text('utf8'))
    audit=dict(changed_cells=len(rows),new_buildings=0,new_floor_planes=0,complete_installed_buildings_reviewed=14,held=shore['held']+outer['held'],rail_conflicts=conflicts,
        exact_current_preconditions_passed=True,retained_full_NBT_count=len(tags),current_transport_snapshot=str(snapshot.resolve()),current_transport_sha256=sha(snapshot),
        sampled_current_transport_points=dict(sampled),new_solid_cells_measured=len(occupied),complete_outer_edges=outer['whole_perimeter_edges'],
        natural_surface_columns=len(surfaces),world_written=False,native_passed=False,visual_passed=False,ready=False)
    (a.plan/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),'utf8')
    print('Whole current proof:',len(rows),'exact/inverse cells;',len(tags),'untouched full BE;',len(surfaces),'natural targets;',dict(sampled),'current curve points; no world write',flush=True)

if __name__=='__main__':main()
