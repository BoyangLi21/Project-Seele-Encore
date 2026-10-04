"""Direct BVH forward kinematics; retain native frames and channels for provenance."""
from pathlib import Path
import re
import numpy as np
from scipy.spatial.transform import Rotation

def load_bvh(path,translation_mode='replace'):
 if translation_mode not in ('replace','offset'):raise ValueError('Explicit BVH translation convention required')
 text=Path(path).read_text(encoding='utf-8-sig');hierarchy,motion=text.split('MOTION',1);tokens=re.findall(r'[^\s{}]+|[{}]',hierarchy);cursor=1;nodes=[];channels=0
 def node(parent,kind):
  nonlocal cursor,channels
  if kind=='End':
   assert tokens[cursor]=='Site';cursor+=1;name=nodes[parent]['name']+'_End'
  else:name=tokens[cursor];cursor+=1
  index=len(nodes);data=dict(name=name,parent=parent,offset=None,channels=[],start=channels);nodes.append(data)
  assert tokens[cursor]=='{';cursor+=1
  while tokens[cursor]!='}':
   command=tokens[cursor];cursor+=1
   if command=='OFFSET':data['offset']=list(map(float,tokens[cursor:cursor+3]));cursor+=3
   elif command=='CHANNELS':
    count=int(tokens[cursor]);cursor+=1;data['start']=channels;data['channels']=tokens[cursor:cursor+count];cursor+=count;channels+=count
   elif command in ['JOINT','End']:node(index,command)
   else:raise ValueError('Unknown BVH hierarchy token '+command)
  cursor+=1
  return index
 assert tokens[cursor]=='ROOT';cursor+=1;node(-1,'ROOT')
 match=re.search(r'Frames:\s*(\d+)\s*Frame Time:\s*([\d.eE+-]+)',motion);count=int(match[1]);dt=float(match[2]);raw=np.fromstring(motion[match.end():],sep=' ').reshape(count,channels)
 positions=np.empty((count,len(nodes),3));rotations=np.empty((count,len(nodes),4));ident=np.tile([0.,0,0,1],(count,1))
 for j,data in enumerate(nodes):
  shift=np.broadcast_to(data['offset'],(count,3)).copy();order=[];values=[]
  for i,channel in enumerate(data['channels']):
   # Six-channel joint exporters (including BNR) store the full local
   # translation. OFFSET is the fallback for axes without a position channel.
   if channel.endswith('position'):
    axis='XYZ'.index(channel[0]);value=raw[:,data['start']+i]
    shift[:,axis]=value+(data['offset'][axis] if translation_mode=='offset' else 0)
   else:order.append(channel[0]);values.append(raw[:,data['start']+i])
  local=Rotation.from_euler(''.join(order),np.array(values).T,degrees=True) if order else Rotation.from_quat(ident)
  if data['parent']<0:positions[:,j]=shift;rotations[:,j]=local.as_quat()
  else:
   parent=Rotation.from_quat(rotations[:,data['parent']]);positions[:,j]=positions[:,data['parent']]+parent.apply(shift);rotations[:,j]=(parent*local).as_quat()
 return dict(names=[x['name'] for x in nodes],parents=np.array([x['parent'] for x in nodes]),offsets=np.array([x['offset'] for x in nodes]),positions=positions,rotations=rotations,fps=1/dt,source=str(Path(path).resolve()),translation_mode=translation_mode)

def save_npz(path,motion):
 np.savez_compressed(path,**{k:np.array(v) for k,v in motion.items()})
