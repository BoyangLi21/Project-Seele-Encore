"""Original game heat-shield geometry, with a rigid payload presentation of the same surface."""
from pathlib import Path
import json,math
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'artifacts/rebuild_r47/assets/assets/projectseele'
PIVOT=np.array([23.62074,110.64044,-3.68774])

def triangle(out,a,b,c,uv):
    normal=np.cross(b-a,c-a);normal/=max(np.linalg.norm(normal),1e-12)
    for point,(u,v) in zip((a,b,c),uv):out.extend([*point,u,v,*normal])

def main():
    vertices=[];rings=52;segments=96
    def point(r,t,back=False):
        y=58*r*math.cos(t);x=22*r*math.sin(t)*(1-.20*max(0,y/58))
        z=(1.5 if back else -5.5*math.sqrt(max(0,1-r*r))-1.5)
        return np.array([x,y,z])
    for back in (False,True):
        for ring in range(rings):
            a=ring/rings;b=(ring+1)/rings
            for n in range(segments):
                t0=n/segments*2*math.pi;t1=(n+1)/segments*2*math.pi
                p=[point(a,t0,back),point(b,t0,back),point(b,t1,back),point(a,t1,back)]
                uv=[(.5+q[0]/48,.5-q[1]/120) for q in p]
                if back:p=p[::-1];uv=uv[::-1]
                triangle(vertices,p[0],p[1],p[2],uv[:3]);triangle(vertices,p[0],p[2],p[3],[uv[0],uv[2],uv[3]])
    for n in range(segments):
        t0=n/segments*2*math.pi;t1=(n+1)/segments*2*math.pi
        p=[point(1,t0),point(1,t1),point(1,t1,True),point(1,t0,True)]
        uv=[(.5+q[0]/48,.5-q[1]/120) for q in p]
        triangle(vertices,p[0],p[1],p[2],uv[:3]);triangle(vertices,p[0],p[2],p[3],[uv[0],uv[2],uv[3]])
    common=dict(format_version=1,source='Original R47 heat shield; TV Episode 06 shuttle heat-shield reference, game adaptation',model_height=116,stride=8,triangle_count=len(vertices)//24)
    mesh=dict(common,parts={'shield':dict(pivot=PIVOT.tolist(),vertices=np.round(vertices,6).tolist())})
    (ASSETS/'mesh/yashima_shield.mesh.json').write_text(json.dumps(mesh,separators=(',',':')),encoding='utf-8')
    payload=np.asarray(vertices).reshape(-1,8);payload[:,1]+=58
    payload_doc=dict(common,parts={'shield':dict(pivot=[0,0,0],vertices=np.round(payload,6).reshape(-1).tolist())})
    (ASSETS/'mesh/yashima_shield_payload.mesh.json').write_text(json.dumps(payload_doc,separators=(',',':')),encoding='utf-8')
    image=Image.new('RGB',(512,1024),(49,51,52));draw=ImageDraw.Draw(image)
    for y in range(0,1024,32):
        for x in range(0,512,32):
            value=51+((x//32*17+y//32*11)%13)
            draw.rectangle((x+1,y+1,x+30,y+30),fill=(value,value+2,value+3))
    draw.rounded_rectangle((9,9,502,1014),radius=58,outline=(173,173,159),width=13)
    draw.line((26,927,486,927),fill=(191,96,59),width=15)
    image.save(ASSETS/'textures/entity/yashima_shield.png')
    model=ASSETS/'models/item/yashima_shield.json';model.parent.mkdir(parents=True,exist_ok=True)
    model.write_text(json.dumps({'parent':'minecraft:item/generated','textures':{'layer0':'projectseele:entity/yashima_shield'}}),encoding='utf-8')
    print(json.dumps({'triangles':common['triangle_count'],'original_weapon_geometry_changed':False}))

if __name__=='__main__':main()
