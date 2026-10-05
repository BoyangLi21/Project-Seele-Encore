"""Detailed fixed support frames for the two independent synchronization plugs."""
from pathlib import Path
import json,math
import numpy as np
from PIL import Image,ImageDraw
from build_yashima_shield_r47 import triangle

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r47/assets/assets/projectseele'

def main():
    vertices=[];angle=math.radians(25);axis=np.array([0,math.sin(angle),math.cos(angle)]);up=np.array([0,math.cos(angle),-math.sin(angle)])
    def rod(a,b,radius,colour=0):
        a,b=np.asarray(a,dtype=float),np.asarray(b,dtype=float);direction=b-a;direction/=np.linalg.norm(direction)
        tangent=np.cross(direction,[0,1,0] if abs(direction[1])<.95 else [1,0,0]);tangent/=np.linalg.norm(tangent);across=np.cross(direction,tangent)
        uv=[(.15+.25*colour,.2)]*3
        for i in range(16):
            t=i/16*math.tau;n=(i+1)/16*math.tau
            x=radius*(tangent*math.cos(t)+across*math.sin(t));y=radius*(tangent*math.cos(n)+across*math.sin(n))
            # The runtime mesh importer uses 1/16 units, then a 3.2 plug scale.
            p,q,r,s=(a+x)*5,(a+y)*5,(b+y)*5,(b+x)*5
            triangle(vertices,p,q,r,uv);triangle(vertices,p,r,s,uv)
            triangle(vertices,a*5,q,p,uv);triangle(vertices,b*5,s,r,uv)
    for distance in (2.5,7.):
        centre=axis*distance
        for i in range(48):
            a=i/48*math.tau;b=(i+1)/48*math.tau
            p=centre+1.32*(np.array([1,0,0])*math.cos(a)+up*math.sin(a))
            q=centre+1.32*(np.array([1,0,0])*math.cos(b)+up*math.sin(b))
            rod(p,q,.07,1)
        for x in (-1.65,1.65):
            top=np.array([x,centre[1]-.35,centre[2]]);foot=np.array([x,-1.5,centre[2]])
            rod(foot,top,.13);rod(foot+[-.3,0,0],foot+[.3,0,0],.16)
            rod(top,centre+[np.sign(x)*1.15,0,0],.1,1)
        rod([-1.65,centre[1]-.35,centre[2]],[1.65,centre[1]-.35,centre[2]],.11)
    for x in (-1.65,1.65):
        rod([x,-1.27,axis[2]*2.5],[x,-1.27,axis[2]*7],.10)
        rod([x,-1.5,axis[2]*2.5],[x,axis[1]*7-.35,axis[2]*7],.06,2)
    # Hydraulic guide and hose bundles are attached to the rear crossbeam.
    for x in (-.55,.55):
        rod([x,axis[1]*7-.15,axis[2]*7],[x,axis[1]*2.5-.15,axis[2]*2.5],.08)
        rod([x,axis[1]*7-.2,axis[2]*7],[x,-1.35,axis[2]*7],.045,2)
    mesh=dict(format_version=1,source='Original R47 synchronization fixture; dry deck and 25 degree capsule axis',model_height=48,stride=8,triangle_count=len(vertices)//24,parts={'fixture':dict(pivot=[0,0,0],vertices=np.round(vertices,7).tolist())})
    (OUT/'mesh/synch_cradle_r47.mesh.json').write_text(json.dumps(mesh,separators=(',',':')),encoding='utf-8')
    image=Image.new('RGB',(256,256),(70,81,77));draw=ImageDraw.Draw(image)
    draw.rectangle((64,0,127,255),fill=(89,116,102));draw.rectangle((128,0,191,255),fill=(32,35,36));draw.rectangle((192,0,255,255),fill=(178,131,54))
    image.save(OUT/'textures/entity/synch_cradle_r47.png');print(mesh['triangle_count'],'fixture triangles')

if __name__=='__main__':main()
