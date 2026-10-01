"""Explain conservative tree reservations in real three-dimensional geometry."""
from pathlib import Path
from collections import Counter
import json,math
import numpy as np
from scipy.spatial import cKDTree

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/ecology/legacy_tree_components'

def intersects(lo,hi,r):return lo[0]<=r[2] and hi[0]>=r[0] and lo[2]<=r[3] and hi[2]>=r[1]

def main():
    a=json.loads((OUT/'reserved_complete_inspection/audit.json').read_text('utf8'));configuration=json.loads((OUT.parent/'biome_source.completed.json').read_text('utf8'))
    native=json.loads((ROOT/'artifacts/repair_r43/transit_resolved/native_snapshot.json').read_text('utf8'))
    points=[];owners=[]
    for r in native['curves']:
        if r['mode']!='TRAIN':continue
        points.extend(r['points']);owners.extend([r['id']]*len(r['points']))
    rail=np.asarray(points,float);tree=cKDTree(rail[:,[0,2]])
    records=[]
    for r in a['objects']:
        if r['status']!='PRESERVE_VERIFIED_COMPLETE_TEMPLATE_IN_RESERVATION':continue
        lo,hi=r['bounds'];surface=[b for b in configuration['reserved_bounds'] if intersects(lo,hi,b)];below=[b for b in configuration['underground_reserved_bounds'] if intersects(lo,hi,b)]
        centre=[(lo[0]+hi[0])/2,(lo[2]+hi[2])/2];radius=math.hypot(hi[0]-lo[0],hi[2]-lo[2])/2+6;hits=[]
        for i in tree.query_ball_point(centre,radius):
            x,y,z=rail[i]
            if lo[0]-4<=x<=hi[0]+4 and lo[2]-4<=z<=hi[2]+4 and y-3<hi[1]+1 and y+8>lo[1]:hits.append(dict(curve=owners[i],point=[x,y,z],status='WHOLE_TREE_BOUNDING_ENVELOPE_INTERSECTION_REQUIRES_EXACT_MEMBER_REVIEW'))
        if hits:status='NATIVE_RAILWAY_3D_ENVELOPE_REVIEW'
        elif below:status='DECLARED_UNDERGROUND_FACILITY_OR_CORRIDOR_REVIEW'
        elif surface and hi[1]<0:status='SURFACE_RESERVATION_ONLY_DIFFERENT_ALTITUDE'
        else:status='RESERVATION_ROLE_REVIEW'
        records.append(dict(id=r['id'],roots=r['roots'],bounds=r['bounds'],whole_original_template_verified=True,no_member_block_entity=True,
            status=status,surface_reservation_intersections=len(surface),below_reservation_intersections=len(below),native_rail_hits=hits,
            retirement_or_reseed_authorized_by_this_report=False,quality_passed=False))
    result=dict(full_component_objects=len(records),classification=dict(Counter(r['status'] for r in records)),objects=records,world_written=False,
        source='Complete geometry/state/NBT inspection plus the resolved installed native curves; registry/world/source guard unchanged',
        generator_followup='A surface-only same-XY reserve cannot establish a subterranean physical obstacle. Root must decide exact vertical facility protections before changing the current conservative feature mask; no mask is silently disabled here.')
    (OUT/'reserved_three_dimensional_relationships.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');print({k:v for k,v in result.items() if k!='objects'},flush=True)

if __name__=='__main__':main()
