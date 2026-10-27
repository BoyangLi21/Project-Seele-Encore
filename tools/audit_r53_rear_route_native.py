"""Read-only sampled rear hardware versus measured native block shapes.

Barrier intersections are recorded independently, never silently treated as
air or accepted as open doors. Native gate movement remains a separate test.
"""
import argparse
import collections
import hashlib
import gzip
import itertools
import json
import re
from pathlib import Path

import numpy as np
from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry
from audit_r53_rear_guide_space import overlaps
from project_upright_gate_collisions_r52 import matrix


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(world,hardware,frames,output,pattern,first_hit_per_part=False,bridge_state=None,owner_tables=None):
    source=json.loads(hardware.read_text('utf8'));doc=json.loads(frames.read_text('utf8'))
    assert sha(hardware)==doc['hardware_sha256']
    parts=[]
    for p,declared in zip(source['parts'],doc['parts']):
        assert source.get('source_name_prefix','rear/')+p['name']==declared['name'] and p['frame']==declared['frame']
        tri=np.asarray(p['triangles_rgb']).reshape(-1,3,6)[:,:,:3]
        lo,hi=tri.min((0,1)),tri.max((0,1))
        corners=np.asarray(list(itertools.product(*zip(lo,hi))))
        parts.append((declared,tri,corners))
    assert len(parts)==len(source['parts'])==len(doc['parts'])
    poses=[p for p in doc['poses'] if re.search(pattern,p['leg'])]
    measured=MeasuredWorld(world);prepared=[]
    for row in poses:
        assert len(row['frames'])==len(parts)
        bounds=[]
        scales=row.get('scales',[[1,1,1]]*len(parts))
        assert len(scales)==len(parts)
        for (_,_,corners),frame,scale in zip(parts,row['frames'],scales):
            scale=np.asarray(scale);assert scale.shape==(3,) and np.isfinite(scale).all() and (scale>0).all()
            rotation=matrix(frame[3:]);origin=np.asarray(frame[:3]);v=(corners*scale)@rotation.T+origin
            lo,hi=v.min(0),v.max(0)
            cells_lo=np.floor(lo+1e-8).astype(int);cells_hi=np.floor(hi-1e-8).astype(int)
            measured.box(tuple(cells_lo-1),tuple(cells_hi+1))
            bounds.append((rotation,origin,lo,hi,cells_lo,cells_hi,scale))
        prepared.append((row,bounds))
    measured.load();bridge_scenario=None
    if bridge_state is not None:
        assert owner_tables is not None and 0<=bridge_state<=9
        owner_path=world/'ROOT_MECHANICAL_OWNER.json';owner=json.loads(owner_path.read_text('utf8'))
        overlay={};receipts=[]
        for unit in owner['units']:
            ref=unit['bridge_states'];path=owner_tables/ref['cells_file']
            assert sha(path)==ref['sha256'],'Declared original bridge state table changed'
            states=json.loads(gzip.decompress(path.read_bytes()));assert len(states)==10
            for cell in states[bridge_state]:
                q=tuple(cell['position']);state=cell['state'] if 'state' in cell else cell['expected']
                assert q not in overlay or overlay[q]==state
                overlay[q]=state
            receipts.append(dict(variant=unit['variant'],file=str(path),sha256=sha(path)))
        original_block=measured.block
        measured.block=lambda q:overlay.get(tuple(q),original_block(q))
        bridge_scenario=dict(actual_frozen_state=False,declared_bridge_state=bridge_state,
            owner_sha256=sha(owner_path),tables=receipts,read_only_overlay_cells=len(overlay),
            condition='Only after the original bridge controller has physically completed this declared state; no world edits performed.')
    geometry=ActualGeometry(measured)
    collisions=[];barriers=[];unknown=[];counts=collections.Counter();by_leg=collections.Counter();shape_cache={}
    for pose,(row,bounds) in enumerate(prepared):
        for (part,tri,_),(rotation,origin,lo,hi,L,H,scale) in zip(parts,bounds):
            transformed=None;solid_found=False
            for cell in itertools.product(*(range(int(L[k]),int(H[k])+1) for k in range(3))):
                if cell not in shape_cache:shape_cache[cell]=(measured.block(cell),geometry.boxes(cell))
                state,boxes=shape_cache[cell]
                if boxes is None:
                    unknown.append(dict(leg=row['leg'],metres=row['metres'],part=part['name'],cell=cell,state=state));continue
                for raw in boxes:
                    box=np.asarray(raw)+np.tile(cell,2)
                    if np.any(box[3:]<=lo+1e-6) or np.any(box[:3]>=hi-1e-6):continue
                    if transformed is None:transformed=(tri*scale)@rotation.T+origin
                    tlo,thi=transformed.min(1),transformed.max(1)
                    nearby=transformed[np.all(thi>box[:3]+1e-6,axis=1)&np.all(tlo<box[3:]-1e-6,axis=1)]
                    if len(nearby) and overlaps(nearby,box[:3],box[3:]):
                        hit=dict(leg=row['leg'],metres=row['metres'],part=part['name'],frame=part['frame'],
                            cell=cell,state=state,root=row['root'][:3],relative_top=float(box[4]-row['root'][1]))
                        if state=='minecraft:barrier':barriers.append(hit)
                        else:collisions.append(hit);counts[state]+=1;by_leg[row['leg']]+=1;solid_found=True
                        break
                if first_hit_per_part and solid_found:break
        if pose%100==0:print('pose',pose,'/',len(poses),'solid',len(collisions),'barrier',len(barriers),'unknown',len(unknown),flush=True)
    report=dict(schema='projectseele.r53.rear-native-sampled-diagnostic.v1',world_written=False,continuous_proof=False,
        frozen_world=str(world),hardware_sha256=sha(hardware),frames_sha256=sha(frames),leg_filter=pattern,
        original_bridge_scenario=bridge_scenario,
        poses=len(poses),legs=len(set(p['leg'] for p in poses)),parts=len(parts),first_solid_hit_per_part_only=first_hit_per_part,
        solid_collision_count=len(collisions),solid_counts=dict(counts),solid_counts_by_leg=dict(by_leg),solid_collisions=collisions,
        barrier_collision_count=len(barriers),barrier_collisions=barriers,
        barrier_disposition='Unresolved closed-proxy intersections; each owning gate must open normally in the native run.',
        unknown_count=len(unknown),unknown=unknown,native_shape_unknown_states=sorted(geometry.unknown))
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('poses',len(poses),'solids',len(collisions),'barriers',len(barriers),'unknown',len(unknown),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('world','hardware','frames','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--leg-filter',default='unit1/(original_incline|bank1_to_2|bank2_to_3)$')
    p.add_argument('--first-hit-per-part',action='store_true',help='Reject-only diagnostic; stop each posed part after its first solid hit.')
    p.add_argument('--bridge-state',type=int,choices=range(10),help='Conditional read-only use of a hash-bound original owner bridge state.')
    p.add_argument('--owner-tables',type=Path,help='Original bridge table root; hashes must match the frozen owner manifest.')
    a=p.parse_args();audit(a.world,a.hardware,a.frames,a.output,a.leg_filter,a.first_hit_per_part,a.bridge_state,a.owner_tables)
