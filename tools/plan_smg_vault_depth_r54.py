"""Measured R54 SMG vault depth correction within the declared R21 vault parcel.

No world writes, entity edits, stock changes, mesh scaling or decoder copies.
"""
import argparse,json,sys
from pathlib import Path
from collections import Counter
sys.path.append(str(Path(__file__).resolve().parents[1]/'.Codex/map-deps'))
import nbtlib
from query_blocks import read_box,iter_block_entities
DIM='projectseele:geofront'

def main():
 p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists()
 lo=(109,35,-47);hi=(131,81,-25);old=read_box(a.world,DIM,lo,hi);tags=dict(iter_block_entities(a.world,DIM,lo,hi));desired={}
 for x in range(116,125):
  for y in range(37,80):
   for z in range(-44,-27):
    q=x,y,z;assert old[q] in ('minecraft:air','projectseele:nerv_structural_panel'),('Unexpected authored interface',q,old[q]);desired[q]='minecraft:air'
 for x in range(115,126):
  for z in range(-45,-26):
   q=x,80,z;assert old[q] in ('minecraft:barrier','projectseele:nerv_floor_panel'),('Unexpected lid/interface',q,old[q]);desired[q]='minecraft:barrier'
 assert not set(tags)&set(desired),'Do not change any original block entity'
 rows=[dict(pos=q,before=old[q],after=s,before_nbt=None,after_nbt=None,owner='r54/original_rifle_vault_depth',reason='Full-scale SMG 12.9516 m depth requires 15 m clear pod; enlarge original reinforced vault interior and retained invisible support lid within its existing R21 parcel') for q,s in sorted(desired.items()) if old[q]!=s]
 # Query only actual maintained-static rows overlapping this authorized finite component.
 maintained=[]
 for cx,cz in sorted({(x>>4,z>>4) for x,y,z in desired}):
  path=a.world/'dimensions/projectseele/geofront/data/city_rigid_generation_r45/chunks'/f'{cx}_{cz}.dat'
  if not path.exists():continue
  for e in nbtlib.load(path)['Static']:
   n=int(e['Pos']);q=(n>>38,((n&4095)+2048)%4096-2048,(((n>>12)&67108863)+33554432)%67108864-33554432)
   if q in desired:maintained.append(q)
 assert not maintained,('Update actual generation owner before install',maintained)
 after=dict(old);after.update(desired)
 assert all(after[x,y,z]=='minecraft:air' for x in range(116,125) for y in range(37,80) for z in range(-44,-27))
 assert all(after[x,80,z]=='minecraft:barrier' for x in range(115,126) for z in range(-45,-26))
 assert all(after[q]==s for q,s in old.items() if q not in desired)
 # renderStandalone centers X/Z and bottoms Y, then applies the existing 0.5/1/0.5 translation.
 payload=[.5-2.6795/2,1,.5-12.9516/2,.5+2.6795/2,1+36.007,.5+12.9516/2]
 chamber=[-3.5,1,-7.5,3.5,42,7.5]
 assert all(payload[i]>=chamber[i] and payload[i+3]<=chamber[i+3] for i in range(3))
 a.out.mkdir(parents=True)
 def write(n,v):(a.out/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')
 write('forwardPatch.json',rows);write('inversePatch.json',[dict(r,before=r['after'],after=r['before']) for r in rows]);write('positiveEditMask.json',[r['pos'] for r in rows])
 write('installation_manifest.json',dict(schema='projectseele.r54.original-smg-vault-depth.v1',world=str(a.world.resolve()),dimension=DIM,static_cells=len(rows),metadata_preconditions=[],world_tables=[],source_parcel=[lo,hi],preserved_original_block_entities=len(tags),maintained_static_overlap=maintained,world_written=False,native_passed=False,visual_review='pending root actual deployed stock',old_inner_pod=[7,41,7],new_inner_pod=[7,41,15],unchanged_mesh_triangles=9136,unchanged_scale=5,payload=4,other_payload_profiles_unchanged=True))
 write('clearance_report.json',dict(payload_local_bounds=payload,pod_clear_bounds=chamber,side_clearance=min(payload[0]-chamber[0],chamber[3]-payload[3]),front_back_clearance=min(payload[2]-chamber[2],chamber[5]-payload[5]),ceiling_clearance=chamber[4]-payload[4],retained_floor_support=True,full_descent_sweep_clear_cells=9*17*43,complete_supported_lid_cells=11*19,changed_states=dict(Counter(r['before'] for r in rows)),native_mechanical_cycle_pending=True))
 print(json.dumps(dict(cells=len(rows),blocks=dict(Counter(r['before'] for r in rows)),maintained_static_overlaps=0,new_interior=[9,43,17],new_lid=[11,19],full_mesh_front_back_clearance=chamber[5]-payload[5])))
if __name__=='__main__':main()
