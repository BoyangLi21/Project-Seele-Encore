"""Render exact saved voxel faces from two 3-D directions, without launching Minecraft."""
import argparse,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from author_hakone_lakefront import Editor
from render_hakone_installed_map import color
from query_blocks import AIR

def render(e,bounds,out,title):
    x,y,z,X,Y,Z=bounds;shape=(Y-y+1,Z-z+1,X-x+1)
    palette=['minecraft:air'];lookup={palette[0]:0};blocks=np.zeros(shape,np.uint16);known=np.zeros(shape,bool)
    for rx in range(x//512,X//512+1):
        for rz in range(z//512,Z//512+1):
            try:r=e.region(rx*512,rz*512)
            except FileNotFoundError:continue
            for (cx,cz),v in zip(r['coords'],r['after']):
                cx,cz=int(cx),int(cz);l,t,R,B=max(x,cx*16),max(z,cz*16),min(X,cx*16+15),min(Z,cz*16+15)
                if l>R or t>B:continue
                codes=[]
                for s in r['names']:
                    if s not in lookup:lookup[s]=len(palette);palette.append(s)
                    codes.append(lookup[s])
                ar=np.s_[:,t-z:B-z+1,l-x:R-x+1]
                blocks[ar]=np.asarray(codes,np.uint16)[v[y+128:Y+129,t-cz*16:B-cz*16+1,l-cx*16:R-cx*16+1]]
                known[ar]=True
    visible=np.array([s.split('[')[0]not in AIR|{'minecraft:light','minecraft:barrier','minecraft:structure_void'}for s in palette])
    solid=visible[blocks]&known;colours=np.asarray([color(s)for s in palette])*255
    half=np.array([.5 if 'slab'in s and 'type=bottom'in s else 1.0 for s in palette])
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',21);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',15)
    out.parent.mkdir(parents=True,exist_ok=True)
    images=[]
    for sx,sz in ((1,1),(-1,-1)):
        faces=[]
        specs=[((1,0,0),[(0,1,0),(0,1,1),(1,1,1),(1,1,0)],1.0),
               ((0,0,sx),[(1 if sx>0 else 0,0,0),(1 if sx>0 else 0,1,0),(1 if sx>0 else 0,1,1),(1 if sx>0 else 0,0,1)],.75),
               ((0,sz,0),[(0,0,1 if sz>0 else 0),(0,1,1 if sz>0 else 0),(1,1,1 if sz>0 else 0),(1,0,1 if sz>0 else 0)],.87)]
        for (dy,dz,dx),verts,shade in specs:
            neighbor=np.roll(solid,(-dy,-dz,-dx),(0,1,2))
            neighbor_known=np.roll(known,(-dy,-dz,-dx),(0,1,2))
            keep=solid&~neighbor&neighbor_known
            if dx:keep[:,:,0 if dx<0 else -1]=False
            if dz:keep[:,0 if dz<0 else -1,:]=False
            if dy:keep[-1]=False
            iy,iz,ix=np.nonzero(keep)
            for cy,cz,cx in zip(iy,iz,ix):
                state=int(blocks[cy,cz,cx]);height=half[state];points=np.array([[cx+vx,cy+vy*height,cz+vz]for vx,vy,vz in verts],float)
                depth=float((sx*points[:,0]+sz*points[:,2]+points[:,1]*1.7).mean())
                faces.append((depth,points,tuple((colours[state]*shade).astype(int))))
        im=Image.new('RGB',(1300,980),'#edf0ed');draw=ImageDraw.Draw(im)
        def project(q):return np.column_stack(((sx*q[:,0]-sz*q[:,2])*.866,(sx*q[:,0]+sz*q[:,2])*.5-q[:,1]))
        if not faces:raise ValueError('Review crop contains no visible saved faces: '+str(bounds))
        limits=project(np.concatenate([f[1]for f in faces]));lo=limits.min(0);span=limits.max(0)-lo;scale=min(1220/span[0],820/span[1])
        for _,points,c in sorted(faces,key=lambda t:t[0]):
            pixels=(project(points)-lo)*scale+[40,92];draw.polygon([tuple(p)for p in pixels],fill=c)
        draw.text((30,15),title,fill='#18362d',font=font)
        draw.text((30,48),f'X {x}..{X} / Y {y}..{Y} / Z {z}..{Z} · camera ({sx}, {sz})',fill='#38564d',font=small)
        draw.text((30,945),'实际方块三维体积；裁切边和未知区块不生成假墙。简化材质，不代表游戏光影或模型。',fill='#38564d',font=small)
        images.append(im)
    canvas=Image.new('RGB',(2600,980),'white');canvas.paste(images[0],(0,0));canvas.paste(images[1],(1300,0));canvas.save(out)
    return dict(image=str(out),bounds=bounds,source='exact measured voxel faces',native_screenshot=False)

def main(a):
    cases=json.loads(a.cases.read_text('utf8'));e=Editor(a.source);rows=[]
    for i,row in enumerate(cases):
        rows.append(render(e,row['bounds'],a.out/(row['id']+'.png'),row['title']));e.regions.clear();print('Rendered 3D',i+1,len(cases),row['id'],flush=True)
    (a.out/'views.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','cases','out'):p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())

