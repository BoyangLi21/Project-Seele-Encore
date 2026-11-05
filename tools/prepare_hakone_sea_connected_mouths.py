"""Restore finite sea-level lower reaches, leaving upper river work explicit.

The complete sea-level part of each independently fitted river is required.
Every new water face must meet current solid banks or measured sea water;
regional clipping or an exposed upstream water wall is never accepted.
This is authored bed geometry, not measured bathymetry or a tidal simulation.
"""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt,label
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import NATURAL,SOIL
from query_blocks import AIR
from install_r53_carrier_trays import stopped_world
from map_pipeline.launch_protection import load,check_candidate

YY=np.arange(-128,320)[:,None,None]
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')

def prepare(a):
 cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);x,z,X,Z=cap['bounds_xz']
 if cap['actors']or cap['unavailable_chunks']:raise ValueError('Complete unoccupied current source required')
 with np.load(a.source/'measured.npz')as f:g=f['top'];full=f['full']
 if not full.all():raise ValueError('Unknown source columns')
 wet=np.zeros(g.shape,bool);selected=[];sea=None
 for path in a.profile:
  report=json.loads((path/'river-profile.json').read_text('utf8'));level=int(report['measured_sea_datum'])
  if sea is not None and sea!=level:raise ValueError('Different sea datums')
  sea=level
  with np.load(path/'river-profile.npz')as f:d={k:f[k]for k in f.files}
  use=d['wet']&(d['level']==sea);j,i=np.where(use);ox,oz,oX,oZ=map(int,d['bounds'])
  if not len(i)or np.any(use&d['ports']):raise ValueError('Sea-level reach is empty or meets an unbuilt regional boundary')
  if not(x+24<=ox+i.min()<=ox+i.max()<=X-24 and z+24<=oz+j.min()<=oz+j.max()<=Z-24):raise ValueError('Entire lower reach and bank margin must be captured')
  q=np.s_[z-oz:Z-oz+1,x-ox:X-ox+1];part=use[q]
  if np.any(wet&part)or int(part.sum())!=int(use.sum()):raise ValueError('Overlapping or clipped river profiles')
  wet|=part;selected.append(dict(profile=str(path),component=report['component'],columns=int(part.sum())))
 with np.load(a.programme/'watercourse-reference.npz')as f:
  ox,oz,oX,oZ=map(int,f['bounds']);q=np.s_[z-oz:Z-oz+1,x-ox:X-ox+1];sea_reference=f['sea'][q];river_reference=f['river'][q]
 if np.any(wet&~river_reference):raise ValueError('Profile no longer matches geographical river footprint')
 water=np.full(g.shape,-32768,np.int16)
 for path in sorted((a.source/'source').glob('*.npz')):
  with np.load(path)as f:coords=f['coordinates'];blocks=f['blocks'];names=[s.split('[')[0]for s in map(str,f['palette'])]
  iswater=np.asarray([s=='minecraft:water'for s in names])
  for(cx,cz),v in zip(coords,blocks):
   q=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16];water[q]=np.where(iswater[v]&(YY>g[q]),YY,-32768).max(0)
 if np.any(wet&(water!=-32768)&(water!=sea)):raise ValueError('Lower reach would overwrite retained non-sea water')
 existing_labels,_=label((water==sea)&(g<sea));marine_ids=np.unique(existing_labels[sea_reference&(existing_labels>0)])
 marine=np.isin(existing_labels,marine_ids)&(existing_labels>0)
 distance=distance_transform_edt(wet);depth=np.clip(1+np.floor(distance/4).astype(int),1,4)
 target=g.copy();target[wet]=np.minimum(g[wet],sea-depth[wet])
 away=distance_transform_edt(~wet);bank=(away>0)&(away<=20)&(water==-32768)
 bank_level=sea+1-np.floor(np.maximum(0,away-1)/2).astype(np.int16)
 target[bank]=np.maximum(target[bank],bank_level[bank])
 # The old river exclusion also left low dry ground beside the marine edge.
 # Join each side of the mouth to the already authored natural beach crest.
 shore=(distance_transform_edt(~marine)<=1)&~wet&(water==-32768)&(g<sea+1)&(away<=32)
 if shore.any():
  distance_to_shore=distance_transform_edt(~shore)
  collar=(distance_to_shore<=20)&~wet&(water==-32768)
  crest=sea+1-np.floor(distance_to_shore/2).astype(np.int16)
  target[collar]=np.maximum(target[collar],crest[collar]);bank|=collar
 bank&=target!=g
 active=wet|bank
 with np.load(a.authority/'network.npz')as f:
  ox,oz,oX,oZ=map(int,f['bounds'])
  if not(ox<=x<X<=oX and oz<=z<Z<=oZ):raise ValueError('Source exceeds authority')
  public=f['walk'][z-oz:Z-oz+1,x-ox:X-ox+1].copy()
 if np.any(active&public):raise ValueError('Mouth earthworks overlap declared public surfaces')
 for row in json.loads((a.authority/'catalog.json').read_text('utf8')):
  b=row['occupied_bounds'];l,t,r,B=max(x,b[0]),max(z,b[2]),min(X,b[3]),min(Z,b[5])
  if l<=r and t<=B and active[t-z:B-z+1,l-x:r-x+1].any():raise ValueError('Mouth overlaps retained building')
 labels,n=label(wet);contacts=[]
 for k in range(1,n+1):
  part=labels==k;edge=distance_transform_edt(~part)<=1
  contact=edge&~part&marine
  if not contact.any():raise ValueError('Lower reach has no measured marine connection')
  contacts.append(dict(component=k,columns=int(part.sum()),marine_contacts=int(contact.sum())))
 # Confirm containment against the current surface before touching voxels.
 # The independent verifier additionally checks every actual side block.
 boundary=(distance_transform_edt(~wet)<=1)&~wet
 if np.any(boundary&(target<sea)&(water<sea)):raise ValueError('Lower reach lacks a dry bank or same-level sea neighbour')
 a.out.mkdir(parents=True,exist_ok=False)
 for name in('source','delta'):(a.out/name).mkdir()
 for p in(a.source/'source').glob('*.npz'):os.link(p,a.out/'source'/p.name)
 shutil.copy2(a.source/'capture.json',a.out/'capture.json')
 with stopped_world(world):
  shutil.copytree(world/'mtr',a.out/'preserved-native');guard=load(world)
 e=Editor(a.out)
 for path in sorted((a.out/'source').glob('*.npz')):
  rx,rz=map(int,path.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
  materials=('minecraft:air','minecraft:stone','minecraft:gravel','minecraft:water[level=0]')
  for name in materials:
   if name not in r['ids']:r['ids'][name]=len(r['names']);r['names'].append(name)
  air,stone,gravel,waterid=(r['ids'][name]for name in materials);base=[s.split('[')[0]for s in r['names']]
  natural=np.asarray([s in NATURAL for s in base]);empty=np.asarray([s in AIR for s in base])
  for(cx,cz),v in zip(r['coords'],r['after']):
   q=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16]
   if not active[q].any():continue
   highest=np.where(~empty[v],YY,-129).max(0);bottom=np.minimum(g[q],target[q])-2
   band=active[q]&(YY>=bottom)&(YY<=np.maximum(np.maximum(highest,target[q]),sea))
   desired=np.where(YY<=target[q],np.where(YY>=target[q]-1,gravel,stone),np.where(wet[q]&(YY<=sea),waterid,air))
   delta=band&(v!=desired)
   if np.any(delta&(~natural[v]|guard.chunk_mask(int(cx),int(cz)))):raise ValueError('Mouth reaches retained structure or launch volume')
   v[delta]=desired[delta]
  e.save();e.regions.clear();print('Prepared lower river region',path.name,flush=True)
 records=e.save();np.savez_compressed(a.out/'mouth-design.npz',bounds=cap['bounds_xz'],wet=wet,bank=bank,active=active,old_ground=g,ground=target,original_water=water,sea=sea,public=public,sea_reference=sea_reference)
 save(a.out/'manifest.json',dict(world=str(world),bounds_xz=cap['bounds_xz'],regions=records,cells=sum(r['cells']for r in records),preserve_native_members=True,
  sea_connected_mouths=dict(source=str(a.source),authority=str(a.authority),programme=str(a.programme),profiles=selected,water_columns=int(wet.sum()),bank_columns=int(bank.sum()),sea=sea,full_chunks=cap['chunk_statuses']['full'],
  measured_marine_connections=contacts,upper_rivers_complete=False,regional_height_field_unchanged=True,exact_future_recipes_required=True),world_written=False))
 save(a.out/'functional-check.json',dict(errors=['Independent lower-river verification pending'],visual_verified=False,world_written=False))
 save(a.out/'launch-protection.json',check_candidate(guard,a.out))
 print('Prepared lower river pools:',int(wet.sum()),'water columns;',sum(r['cells']for r in records),'changes; upper rivers remain incomplete.',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(__doc__)
 for n in('source','authority','programme','out'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--profile',action='append',type=Path,required=True);prepare(p.parse_args())
