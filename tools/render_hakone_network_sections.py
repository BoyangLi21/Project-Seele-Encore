"""Render actual saved/candidate voxel sections; no inferred solid height columns."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from author_hakone_lakefront import Editor

def colour(s):
    n=s.split('[')[0]
    if n in ('minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light'):return (218,232,240)
    if 'grass'in n or 'leaves'in n:return (95,127,62)
    if 'dirt'in n:return (125,94,66)
    if 'water'in n:return (50,112,178)
    if 'white_concrete'in n or 'marking'in n:return (247,246,234)
    if 'black_concrete'in n or 'asphalt'in n:return (45,46,50)
    if 'smooth_stone'in n:return (152,160,164)
    if 'glass'in n:return (97,163,183)
    if 'brick'in n:return (124,110,99)
    if 'plank'in n or 'wood'in n:return (139,91,54)
    if 'concrete'in n:return (181,184,188)
    return (112,116,119)

def render(a):
    e=Editor(a.candidate);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
    shots=[('east roads Z=330','x',330,900,1160,25,125),('cross-city Z=477','x',477,-370,-80,45,140),('podiums X=190','z',190,335,445,60,135)]
    out=Image.new('RGB',(1500,800),'white');draw=ImageDraw.Draw(out)
    for row,(title,axis,fixed,start,end,lo,hi)in enumerate(shots):
        for side,original in enumerate((True,False)):
            pixels=np.zeros((hi-lo+1,end-start+1,3),np.uint8)
            for u in range(start,end+1):
                x,z=(u,fixed)if axis=='x'else(fixed,u);r=e.region(x,z)
                b=r['before'if original else'after'][r['index'][x//16,z//16],lo+128:hi+129,z%16,x%16]
                pal=np.array([colour(s)for s in r['names']],np.uint8)
                pixels[:,u-start]=pal[b][::-1]
            im=Image.fromarray(pixels).resize((700,205),Image.Resampling.NEAREST)
            left,top=20+side*750,35+row*260;out.paste(im,(left,top))
            draw.text((left,top-24),title+(' | current'if original else' | candidate'),font=font,fill='black')
            draw.text((left,top+209),f'{start} .. {end}; Y {lo} .. {hi}; exact blocks',font=font,fill='black')
        e.regions.clear()
    a.out.parent.mkdir(parents=True,exist_ok=True);out.save(a.out)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);render(p.parse_args())
