"""Flush public-approach finishes and the declared Hakone operating bench.
Uses named current routes, gate frames and old explicit landscape authority.
Only known full floor/soil cubes change material; elevation and equipment stay.
"""
from pathlib import Path
import argparse,json,gzip,math,collections
import numpy as np
from query_blocks import read_box,iter_block_entities,AIR

PUBLIC={'projectseele:nerv_floor_panel','minecraft:smooth_stone','minecraft:light_gray_concrete','minecraft:gray_concrete','minecraft:white_concrete','minecraft:polished_andesite'}
IDS=['r07/base/operations_walk','r07/base/workshop_walk','r07/base/power_walk','r07/base/terminal_walk','r07/port/warehouse/entry','r07/port/customs/entry','r07/port/naval_support/entry','r20/airport/bay/terminal_station','r20/airport/bay/station_boarding','r20/airport/hakone/terminal_station','r20/airport/hakone/station_boarding','r21/airport/un_terminal_boarding']

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();rows={};components=[];cases={r['id']:r for r in json.loads((a.world/'quality_walk_cases.json').read_text('utf8'))}
 for ident in IDS:
  path=cases[ident]['path'];assert all(p[1]==path[0][1]for p in path);y=int(path[0][1])-1;lo=(math.floor(min(p[0]for p in path))-2,y,math.floor(min(p[2]for p in path))-2);hi=(math.floor(max(p[0]for p in path))+2,y+2,math.floor(max(p[2]for p in path))+2);b=read_box(a.world,'projectseele:geofront',lo,hi);bes=dict(iter_block_entities(a.world,'projectseele:geofront',lo,hi));positions={};preserved=collections.Counter();start_count=len(rows)
  for aa,bb in zip(path,path[1:]):
   dx,dz=bb[0]-aa[0],bb[2]-aa[2];assert dx==0 or dz==0;length=math.hypot(dx,dz);nx,nz=(0,1)if dx else(1,0)
   for step in range(math.ceil(length)+1):
    t=min(1,step/max(length,1));x,z=math.floor(aa[0]+t*dx),math.floor(aa[2]+t*dz)
    if 'boarding'in ident and math.hypot(x-path[-1][0],z-path[-1][2])<8:continue
    for side in(-2,0,2):
     q=(x+nx*side,y,z+nz*side);old=b.get(q)
     if old not in PUBLIC or q in bes:preserved[(old or'unknown').split('[')[0]]+=1;continue
     if b.get((q[0],y+1,q[2]))not in AIR or b.get((q[0],y+2,q[2]))not in AIR:preserved['covered_floor']+=1;continue
     if side:after='minecraft:white_concrete'
     elif(x+z)%10<5:after='minecraft:light_blue_concrete'if 'port/'not in ident else'minecraft:orange_concrete'
     else:after='projectseele:nerv_floor_panel'
     positions[q]=after
  for q,after in positions.items():
   before=b[q]
   if before!=after:rows[q]=dict(pos=q,before=before,after=after,before_nbt=None,after_nbt=None,owner='r54/public_finish/'+ident,reason='Flush guidance stripe and edge lines within the original named public walkway; all heights, native boarding stairs and distinctive platform materials retained')
  components.append(dict(id=ident,path=path,cells=len(rows)-start_count,protected_current_states=dict(preserved)))
 # Exact current Yashima approaches, plus all three original same-height exit routes.
 site=json.loads((a.world/'tv_encounter_sites_r45.json').read_text('utf8'))['sites']['ramiel'];original=json.loads(Path('F:/eva/artifacts/map_complete_20261013/complete_hakone_ridge/natural_ridge_three_ports_and_ground_approaches/PLAN.json').read_text('utf8'));paths=list(site['eva_access_routes'].values())+[site['cover_after_supply_route']]+[original['eva_access_routes']['2']];gates=json.loads((a.world/'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))['gates'];ports=[g for g in gates if'bank_3_surface'in g['resource']]
 lo=(-1403,174,-1553);hi=(-1097,176,-1325);b=read_box(a.world,'projectseele:geofront',lo,hi);bes=dict(iter_block_entities(a.world,'projectseele:geofront',lo,hi));z,x=np.mgrid[lo[2]:hi[2]+1,lo[0]:hi[0]+1];distance=np.full(x.shape,np.inf);along=np.zeros(x.shape)
 for path in paths:
  for aa,bb in zip(path,path[1:]):
   dx,dz=bb[0]-aa[0],bb[2]-aa[2];length=math.hypot(dx,dz)
   if length<1e-8:continue
   t=np.clip(((x+.5-aa[0])*dx+(z+.5-aa[2])*dz)/(length*length),0,1);ds=np.hypot(x+.5-aa[0]-t*dx,z+.5-aa[2]-t*dz);near=ds<distance;along=np.where(near,t*length,along);distance=np.minimum(distance,ds)
 pad=np.full(x.shape,np.inf);gate_mask=np.zeros(x.shape,bool)
 for gate in ports:
  px,_,pz=gate['frame']['position'];pad=np.minimum(pad,np.hypot(x+.5-px,z+.5-pz));gate_mask|=(abs(x+.5-px)<=23)&(abs(z+.5-pz)<=18)
 active=((distance<=6.5)|(pad<=30))&~gate_mask;count_before=len(rows);preserved=collections.Counter()
 for iz,ix in np.argwhere(active):
  xx,zz=int(x[iz,ix]),int(z[iz,ix]);q=(xx,174,zz);before=b.get(q)
  if before not in ['minecraft:grass_block[snowy=false]','minecraft:dirt','minecraft:coarse_dirt']or q in bes or b.get((xx,175,zz))not in AIR:preserved[(before or'unknown').split('[')[0]]+=1;continue
  d,r=float(distance[iz,ix]),float(pad[iz,ix])
  if d<=6.5:
   after='minecraft:polished_deepslate'if 5.5<=d<=6.5 else'minecraft:white_concrete'if 4.5<=d<5.5 or d<.6 and int(along[iz,ix])%12<5 else'minecraft:light_gray_concrete'
  else:after='minecraft:white_concrete'if r>=29 else'projectseele:nerv_hazard_paving'if 23<=r<24 else'minecraft:gray_concrete'
  rows[q]=dict(pos=q,before=before,after=after,before_nbt=None,after_nbt=None,owner='r54/hakone_declared_access_finish',reason='Flush paved EVA service approaches and original exit operating aprons; dark drainage appearance is a full-height solid floor, never an actual trench')
 components.append(dict(id='hakone_declared_access_finish',cells=len(rows)-count_before,geometry_changed=False,full_floor_y=174,road_width=13,flat_port_radius=30,protected_current_states=dict(preserved),gate_leaves_and_source_supports_retained=True))
 a.out.mkdir(parents=True,exist_ok=True);forward=list(rows.values());inverse=[]
 for row in forward:
  r=row.copy();r['before'],r['after']=r['after'],r['before'];inverse.append(r)
 for name,rs in [('forward',forward),('inverse',inverse)]:
  with gzip.open(a.out/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
   for r in rs:f.write(json.dumps(r)+'\n')
 m=dict(schema='projectseele.r54.public-facility-finish.v1',world=str(a.world),dimension='projectseele:geofront',static_cells=len(rows),components=components,metadata_preconditions=[],world_tables=[],world_written=False,native_passed=False,visual_self_review='pending',scope='Named original public approaches and declared fixed Hakone working surface; no altitude, gate, payload, stair, rail or control change')
 for name,v in [('forwardPatch.json',forward),('inversePatch.json',inverse),('positiveEditMask.json',[r['pos']for r in forward]),('installation_manifest.json',m)]:
  (a.out/name).write_text(json.dumps(v,ensure_ascii=False,separators=(',',':')),encoding='utf8')
 print('Prepared',len(rows),'public facility floor cells; component counts',[(c['id'],c['cells'])for c in components])
if __name__=='__main__':main()
