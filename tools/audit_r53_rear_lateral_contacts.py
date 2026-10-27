"""Finite contact checks for the isolated transverse sleeve, from all source faces."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def box(part):
    tri=np.asarray(part['triangles_rgb']).reshape(-1,3,6)[:,:,:3]
    assert len(tri)==12,'Complete engineered twelve-triangle box required'
    lo,hi=tri.min((0,1)),tri.max((0,1))
    assert (hi>lo).all()
    for point in tri.reshape(-1,3):
        assert np.all(np.minimum(abs(point-lo),abs(point-hi))<1e-8)
    # Verify both finite faces on every axis, not merely the bounding box.
    for axis in range(3):
        face_area=np.prod(np.delete(hi-lo,axis))
        for plane in [lo[axis],hi[axis]]:
            faces=tri[np.all(abs(tri[:,:,axis]-plane)<1e-8,axis=1)]
            actual=np.linalg.norm(np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0]),axis=1).sum()/2
            assert len(faces)==2 and abs(actual-face_area)<1e-9
    return lo,hi


def contact(a,b,axis):
    lo,hi=a;L,H=b
    assert min(abs(hi[axis]-L[axis]),abs(H[axis]-lo[axis]))<1e-8
    overlap=np.minimum(hi,H)-np.maximum(lo,L)
    area=np.prod(np.delete(overlap,axis));assert area>1e-5
    return float(area)


def audit(hardware,baseline,diagnostic,output):
    doc=json.loads(hardware.read_text());old=json.loads(baseline.read_text());parts={p['name']:p for p in doc['parts']};checks=[]
    for p in old['parts']:
        if p['name'].endswith('/mount/5'):continue
        assert parts[p['name']]==p,'Original head, source facet or lift source changed'
    for side,name in [(-1,'rear_l'),(1,'rear_r')]:
        prefix=name+'/lateral/';rod=box(parts[prefix+'rod']);sleeves=[box(parts[prefix+'sleeve/'+str(i)]) for i in range(4)]
        for r in [0.,1.]:
            delta=np.asarray([-side*.65*r,0,0]);moving=tuple(x+delta for x in rod)
            areas=[contact(moving,b,1 if i<2 else 2) for i,b in enumerate(sleeves)]
            checks.append(dict(side=name,retraction=r,finite_contact_areas_m2=areas))
        # The contact planes are constant and the axial overlap is piecewise
        # affine with positive endpoint minima throughout the linear stroke.
        checks.append(dict(side=name,stator_support_face_m2=contact(box(parts[prefix+'support/2']),sleeves[0],1)))
    d=json.loads(diagnostic.read_text());actual=d['lateral_contact_or_intersection_pairs_require_classification'];expected={}
    for name in ['rear_l','rear_r']:
        p='rear/'+name+'/'
        def pair(a,b):expected[p+a+' | '+p+b]=41
        pair('ball','lateral/rod');pair('mount/4','lateral/support/0')
        for i in range(4):pair('lateral/sleeve/'+str(i),'lateral/tie/'+str(i))
        for i in range(2):pair('lateral/support/'+str(i),'lateral/support/'+str(i+1))
        for i in range(2):
            for j in range(2,4):pair('lateral/tie/'+str(i),'lateral/tie/'+str(j))
    assert actual==expected,'Unexpected intersecting pair or named weld lost during stroke'
    assert not d['source_attachment_hits'] and not d['column_hits']
    result=dict(installed=False,world_written=False,complete_original_source_preserved=True,
        hardware_sha256=hashlib.sha256(hardware.read_bytes()).hexdigest(),finite_sliding_contact_checks=checks,
        named_rigid_weld_pair_count=len(expected),unexpected_lateral_intersection_pairs=0,
        continuous_scope='Finite planar sleeve contact throughout the affine transverse stroke only; sampled collision checks are not continuous route clearance.')
    output.write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['hardware','baseline','diagnostic','output']:p.add_argument(n,type=Path)
    a=p.parse_args();audit(a.hardware,a.baseline,a.diagnostic,a.output)
