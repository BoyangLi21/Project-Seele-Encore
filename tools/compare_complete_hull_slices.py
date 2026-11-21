"""Explicit every-band convex set inclusion, never source-hash substitution for geometry."""
from pathlib import Path
import argparse,json,hashlib,collections
import numpy as np
from scipy.spatial import ConvexHull
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def outside(points,container):
 if len(points)==0:return float('-inf')
 if len(container)<3:return float('inf')
 e=ConvexHull(container).equations
 return float((points@e[:,:2].T+e[:,2]).max())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--old',type=Path,required=True);ap.add_argument('--new',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();old=json.loads(a.old.read_text('utf8'));new=json.loads(a.new.read_text('utf8'));rows=[]
 for v in range(3):
  A={tuple(r['height_band_m']):np.array(r['actual_clipped_XZ_convex_hull_m']) for r in old['variants'][v]['height_slices_1m']};B={tuple(r['height_band_m']):np.array(r['actual_clipped_XZ_convex_hull_m']) for r in new['variants'][v]['height_slices_1m']}
  for band in sorted(A.keys()|B.keys()):
   x=A.get(band,np.empty((0,2)));y=B.get(band,np.empty((0,2)));no=outside(y,x);on=outside(x,y);same=no<=1e-9 and on<=1e-9;relation='geometrically_equal' if same else 'new_contained_in_old' if no<=1e-9 else 'new_expands_outside_old';rows.append(dict(variant=v,height_band_m=band,relation=relation,old_vertices=len(x),new_vertices=len(y),exact_vertex_arrays_equal=bool(np.array_equal(x,y)),new_max_signed_distance_outside_old_m=no,old_max_signed_distance_outside_new_m=on))
 counts=dict(collections.Counter(r['relation'] for r in rows));report=dict(world_written=False,game_started=False,old_hull=str(a.old.resolve()),old_hull_sha256=sha(a.old),new_hull=str(a.new.resolve()),new_hull_sha256=sha(a.new),old_directory_sha256=old['root_design_sha256'],new_directory_sha256=new['root_design_sha256'],geometric_inclusion_tolerance_m=1e-9,counts=counts,new_complete_contained_in_old=all(r['relation']!='new_expands_outside_old' for r in rows),rows=rows,scope='All vertices of each convex one-metre height-band polygon are tested against every normalized half-space of the opposite polygon. This proves hull-set inclusion; it does not reinstate the old wrong plug-binding fixture or constitute gate/native clearance.')
 a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf8');print(counts);print('NEW_COMPLETE_CONTAINED',report['new_complete_contained_in_old'])
if __name__=='__main__':main()
