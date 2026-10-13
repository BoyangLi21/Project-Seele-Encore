"""Actual paired selected skin checks over the action window, with explicit sampling limits."""
from pathlib import Path
import argparse,hashlib,json,time
import numpy as np
from r52_motion_core import selected,read,MIRROR,UNIT
from audit_finisher_leg_clearance_r52 import intersections

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ('body','assets','angel-rig','clip','out'):ap.add_argument('--'+name,type=Path,required=True)
 ap.add_argument('--start',type=int,default=945);ap.add_argument('--end',type=int,default=1116);ap.add_argument('--step',type=int,default=6)
 ap.add_argument('--arms',action='store_true');args=ap.parse_args();_,hero,angel=selected(args.body,args.assets,args.angel_rig)
 raw=args.clip.read_bytes();clip=json.loads(raw);rows=[]
 groups={'head':['head'],'torso':['torso_lower','torso_upper','neck'],'legs':['leg_l','shin_l','foot_l','leg_r','shin_r','foot_r']}
 if args.arms:groups['arms']=['arm_l','forearm_l','hand_l','arm_r','forearm_r','hand_r']
 report={'clip_sha256':hashlib.sha256(raw).hexdigest(),'frames':[args.start,args.end],'frame_step':args.step,'samples':rows,'native_verified':False,'user_accepted':False,'scope':'Actual non-coplanar selected triangle intersections at the recorded frames. Does not prove continuous swept clearance or artistic acceptance.'}
 for index in range(args.start,args.end+1,args.step):
  start=time.perf_counter();h=hero.decode(clip['eva']['frames'][index],clip['eva']['bones']);a=angel.decode(clip['angel']['frames'][index],clip['angel']['bones'])
  hr=np.asarray(clip['eva']['root_blocks'][index]);ar=np.asarray(clip['angel']['root_blocks'][index]);enemy=(a.surface()*UNIT+ar).reshape(-1,3,3)
  row={'frame':index,'seconds':index/60,'groups':{}}
  for name,parts in groups.items():
   surface=h.surface([p for p in parts if p in hero.parts])*MIRROR*UNIT+hr
   hits=intersections(surface.reshape(-1,3,3),enemy);dominant={}
   for hit in hits:
    vi=angel.inverse[hit['angel_triangle']*3];bone=angel.names[int(angel.ids[vi,np.argmax(angel.weights[vi])])];dominant[bone]=dominant.get(bone,0)+1
   row['groups'][name]={'pairs':len(hits),'hits':hits[:12],'dominant_enemy_bones':dominant}
  rows.append(row);args.out.write_text(json.dumps(report,indent=2),'utf8')
  print(index,{name:group['pairs'] for name,group in row['groups'].items()},'seconds',round(time.perf_counter()-start,2),flush=True)

if __name__=='__main__':main()
