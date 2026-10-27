"""Render measured height previews for the bounded Hakone landscape patch."""
from pathlib import Path
import argparse,numpy as np,json
from PIL import Image,ImageDraw,ImageFont

def main():
 ap=argparse.ArgumentParser();ap.add_argument('patch',type=Path);ap.add_argument('--original',type=Path,required=True);a=ap.parse_args();p=a.patch;d=np.load(p/'height_preview.npz');orig=np.load(a.original/'HEIGHTS.npz');x0,z0=d['origin']
 before=np.where(d['before']>-32768,d['before'],orig['after']);after=np.where(d['after']>-32768,d['after'],orig['after']);im=Image.new('RGB',(1360,1180),'#18212a');dr=ImageDraw.Draw(im);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22);small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
 dr.text((18,12),'Hakone mountain shoulder: measured height-model comparison, no game lighting',font=font,fill='white')
 for i,(label,h)in enumerate([('Before: broad cleared operating bench',before),('After: irregular shoulders, working areas retained',after)]):
  dy,dx=np.gradient(h.astype(float));normal=np.sqrt(dx*dx+dy*dy+1);shade=np.clip((-.5*dx+.6*dy+1.4)/normal,.45,1.5);t=np.clip((h-80)/140,0,1);rgb=np.stack((65+t*50,95+t*28,55+t*45),axis=-1);rgb=(rgb*shade[:,:,None]).clip(0,255).astype('uint8');im.paste(Image.fromarray(rgb).resize((640,620)),(20+i*680,75));dr.text((20+i*680,48),label,font=small,fill='#d3dfe7')
  for px in[-1370,-1250,-1130]:
   xx=20+i*680+(px-x0)*640/h.shape[1];zz=75+(-1520.5-z0)*620/h.shape[0];dr.rectangle((xx-3,zz-3,xx+3,zz+3),outline='white',width=1)
  k=6;h2=h[::k,::k];arr=[]
  def screen(xx,zz,yy):return(340+i*680+(xx-zz)*.53,800+(xx+zz)*.23-(yy-60)*1.05)
  for iz in range(h2.shape[0]-1):
   for ix in range(h2.shape[1]-1):
    pts=[screen((ix+dx)*k,(iz+dz)*k,float(h2[iz+dz,ix+dx]))for dx,dz in[(0,0),(1,0),(1,1),(0,1)]];arr.append((ix+iz,pts,tuple(rgb[iz*k,ix*k])))
  for _,pts,c in sorted(arr,key=lambda v:v[0]):dr.polygon(pts,fill=c)
  dr.text((20+i*680,1125),'White squares = unchanged exits. Only natural ground above Y144 is edited.',font=small,fill='#c1d0dc')
 im.save(p/'RIDGE_COMPARISON.png')
 valid=(d['before']>0)&(d['after']>0);inc=[]
 for axis in(0,1):
  old=np.abs(np.diff(d['before'].astype(int),axis=axis));new=np.abs(np.diff(d['after'].astype(int),axis=axis));v=valid[:-1,:]&valid[1:,:]if axis==0 else valid[:,:-1]&valid[:,1:];inc.append(int(np.max((new-old)[v])))
 report={'largest_added_adjacent_step':inc,'changed_protected_columns':int(np.sum((d['before']!=d['after'])&d['protected'])),'view':str(p/'RIDGE_COMPARISON.png')};(p/'terrain_edges.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(report)
if __name__=='__main__':main()
