"""Bind inherited command-room shader masks to the same server-owned HQ frame."""
from pathlib import Path
import argparse,zipfile

def build(source,output):
 output.parent.mkdir(parents=True,exist_ok=True)
 changed=0
 with zipfile.ZipFile(source) as src,zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as dst:
  for info in src.infolist():
   data=src.read(info.filename)
   if info.filename=='shaders/lib/lighting/mainLighting.glsl':
    s=data.decode('utf8')
    assert 'seeleHqWorld' not in s and 'seeleRoomMask' in s
    s=s.replace('uniform int seeleCommandLights;','uniform int seeleCommandLights;\nuniform int seeleHeadquartersX;\nuniform int seeleHeadquartersY;\nuniform int seeleHeadquartersZ;',1)
    anchor='vec3 seeleWorld = playerPos + cameraPosition;'
    assert s.count(anchor)==1
    s=s.replace(anchor,anchor+'\n    vec3 seeleHqWorld = seeleWorld - vec3(seeleHeadquartersX, seeleHeadquartersY, seeleHeadquartersZ);',1)
    for name in ('seelePyramid','seeleRoom'):
     start=s.index('vec3 '+name+' =');end=s.index(';',start)
     section=s[start:end];assert section.count('seeleWorld')==2
     s=s[:start]+section.replace('seeleWorld','seeleHqWorld')+s[end:]
    data=s.encode('utf8');changed+=1
   dst.writestr(info,data)
 assert changed==1
 with zipfile.ZipFile(output) as z:
  t=z.read('shaders/lib/lighting/mainLighting.glsl').decode('utf8')
  assert 'seeleHeadquartersY' in t and t.count('seeleHqWorld')==5
 print('HQ shader frame and switch binding prepared; readback passed')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.source,a.output)
