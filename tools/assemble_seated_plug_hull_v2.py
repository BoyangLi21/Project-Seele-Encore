"""Replace the invalid identity plug component; preserve all valid current EVA/carrier/head components."""
from pathlib import Path
import sys,gzip,struct,json,hashlib,copy
import numpy as np
from build_current_launch_height_hulls import read_mesh
R=Path(__file__).resolve().parents[1];OLD=R/'.Codex/map_complete_20261013/route_audit/launch_hulls_current';OUT=R/'.Codex/map_complete_20261013/route_audit/launch_hulls_v2_seated_plug'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(path,parts):
 with gzip.open(path,'wb') as f:
  f.write(struct.pack('>i',len(parts)))
  for name,(family,a) in parts.items():
   for s in (name,family):b=s.encode('ascii');f.write(struct.pack('>H',len(b)));f.write(b)
   f.write(struct.pack('>i',a.size));f.write(np.asarray(a,dtype='>f8').tobytes())
def main():
 report=json.loads((OLD/'ACTUAL_CURRENT_ASSEMBLY_EXPORT.json').read_text('utf8'));receipt=json.loads((OUT/'ACTUAL_SEATED_PLUG_BINDING_RECEIPT.json').read_text('utf8'));assert receipt['lock_depth_m']==11
 for k in ('construction_hull_invalidated','invalid_reason','valid_for_complete_occupied_assembly'):report.pop(k,None)
 report['sources_sha256']={};sources={};comparison=[]
 for v in range(3):
  old=read_mesh(OLD/f'ACTUAL_FIXED_ASSEMBLY.variant{v}.bin.gz');plug=read_mesh(OUT/f'ACTUAL_SEATED_CLOSED_PLUG.variant{v}.bin.gz');assert set(plug)=={k for k,(_,_) in old.items() if k.startswith('plug/')};parts={k:value for k,value in old.items() if not k.startswith('plug/')};parts.update(plug);p=OUT/f'ACTUAL_FIXED_ASSEMBLY.variant{v}.bin.gz';save(p,parts)
  assert all(np.array_equal(parts[k][1],a) for k,(_,a) in old.items() if not k.startswith('plug/'))
  report['variants'][v]['binding']['plugInEva']=receipt['variants'][v]['plug_in_eva_local'];report['variants'][v]['actual_seated_plug_binding']=receipt['variants'][v];report['sources_sha256'][str(p)]=sha(p)
  comparison.append(dict(variant=v,unchanged_exact_nonplug_parts=len(old)-len(plug),replaced_plug_parts=len(plug),old_mesh_sha256=sha(OLD/f'ACTUAL_FIXED_ASSEMBLY.variant{v}.bin.gz'),new_mesh_sha256=sha(p),plug_triangles=sum(a.shape[0] for _,a in plug.values())))
 p=OUT/'ACTUAL_CURRENT_HEAD_TEMPLATES.bin.gz';p.write_bytes((OLD/p.name).read_bytes());report['sources_sha256'][str(p)]=sha(p);report['sources_sha256'][str(OUT/'ACTUAL_SEATED_PLUG_BINDING_RECEIPT.json')]=sha(OUT/'ACTUAL_SEATED_PLUG_BINDING_RECEIPT.json');design=Path('D:/eva/artifacts/map_complete_20261013/phased_routes/PHASED_MONOTONE_DESIGN.json');report['sources_sha256'][str(design)]=sha(design);assert sha(design)==report['root_design_sha256']
 report['complete_fixture_rule']='Occupied full-payload fixtures require selected dorsal profile + explicit posed-chest/canonical locked equivalence + LOCK_DEPTH11 nonidentity binding. Identity is permitted only for sole-only coordinate sampling, never occupied plug placement.';report['scope']='v2 replaces only the old falsely origin-bound PLUG component with the measured actual canonical seated closed plug. All original current-provider EVA, fresh current original carrier including actual three-bank ready shoe poses, and current48 head triangles remain exact unchanged. No World/native admission.'
 (OUT/'ACTUAL_CURRENT_ASSEMBLY_EXPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');(OUT/'EXACT_COMPONENT_REPLACEMENT.json').write_text(json.dumps(dict(world_written=False,source_script_sha256=sha(Path(__file__)),variants=comparison),indent=2),'utf8');print(comparison)
if __name__=='__main__':main()
