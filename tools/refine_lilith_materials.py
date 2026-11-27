"""Bake the R65 Lilith gallery materials from the installed, licensed local mesh.

The input geometry, UVs and textures stay in the installation. Only the three
derived resources need to be overlaid on the local client and its matching pack.
"""
import argparse
import io
import json
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = 'assets/projectseele/'


def mesh(archive, name):
    return json.loads(archive.read(ROOT + f'mesh/lilith_{name}.mesh.json'))


def soften_body(vertices):
    triangles = vertices.reshape(-1, 3, 8)
    normals = triangles[:, 0, 5:8]
    accum = {}
    for triangle, normal in zip(triangles, normals):
        for i in range(3):
            center = triangle[i, :3]
            a = triangle[(i+1) % 3, :3] - center
            b = triangle[(i+2) % 3, :3] - center
            angle = np.arctan2(np.linalg.norm(np.cross(a,b)), np.dot(a,b))
            accum.setdefault(tuple(center), []).append((normal.copy(), angle))
    result = vertices.copy().reshape(-1, 3, 8)
    for tri, normal in zip(result, normals):
        for corner in tri:
            weighted = sum((n*w for n,w in accum[tuple(corner[:3])] if n @ normal > .55), np.zeros(3))
            length = np.linalg.norm(weighted)
            if length > 1e-6:
                corner[5:8] = weighted / length
    return result.reshape(-1, 8)


def bake_face(mask, eyes, original):
    xyz = mask[:, :3]
    xmin, ymin = xyz.min(axis=0)[:2]
    xmax, ymax = xyz.max(axis=0)[:2]
    width, height = 512, 768
    def map_xy(x,y):
        return ((x-xmin)/(xmax-xmin)*(width-3)+1, (ymax-y)/(ymax-ymin)*(height-3)+1)
    u,v=map_xy(mask[:,0],mask[:,1])
    mask[:,3],mask[:,4]=u/(width-1),v/(height-1)
    canvas=original.resize((width,height),Image.Resampling.BICUBIC).convert('RGB')
    # Preserve the source's mineral texture under a lighter lavender face.
    canvas=Image.blend(canvas,Image.new('RGB',canvas.size,(159,143,181)),.54)
    draw=ImageDraw.Draw(canvas)
    pupils=np.unique(eyes[:,:3],axis=0)
    # The seven detached pupils occupy disjoint vertical ranges in the mesh.
    ordered=pupils[np.argsort(pupils[:,1])]
    groups=np.split(ordered, np.flatnonzero(np.diff(ordered[:,1])>1.32)+1)
    if len(groups)!=7:
        raise ValueError(f'Expected seven detached eye sockets, found {len(groups)}')
    centers=sorted([(g.min(0)+g.max(0))/2 for g in groups],key=lambda c:-c[1])
    left=sorted([p for p in centers if p[0]<0],key=lambda c:-c[1])
    right=sorted([p for p in centers if p[0]>0],key=lambda c:-c[1])
    if (len(left),len(right))!=(4,3):
        raise ValueError('Unexpected layout of seven eyes')
    # Extend both sloping rows to form the incised triangular SEELE mark.
    def x_at(row,y):
        a,b=row[0],row[-1]
        return a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1])
    top=max(c[1] for c in centers)+7
    lower=ymin+3
    outline=[map_xy(x_at(left,top),top),map_xy(x_at(right,top),top),
             map_xy((x_at(left,lower)+x_at(right,lower))/2,lower)]
    for offset,col,w in [(2,(174,157,194),5),(0,(62,52,80),5),(-1,(90,75,108),2)]:
        pts=[(round(x),round(y)+offset) for x,y in outline];draw.line(pts+pts[:1],col,width=w,joint='curve')
    for i,(cx,cy,_) in enumerate(centers):
        span=(6.1-.31*i);half_height=(2.15-.085*i)
        def almond(w,h):
            t=np.linspace(-1,1,20)
            return [map_xy(cx+w*q,cy+h*(1-q*q)) for q in t]+[map_xy(cx+w*q,cy-h*.78*(1-q*q)) for q in reversed(t)]
        draw.polygon(almond(span,half_height),(48,43,61))
        draw.polygon(almond(span*.85,half_height*.68),(222,219,218))
        a=map_xy(cx-span*.125,cy+half_height*.69);b=map_xy(cx+span*.125,cy-half_height*.57)
        draw.ellipse([a,b],(32,28,38))
    return canvas.filter(ImageFilter.GaussianBlur(.30))


def bake(source,out):
    with zipfile.ZipFile(source) as archive:
        body=mesh(archive,'body')
        mask=mesh(archive,'mask')
        eyes=mesh(archive,'eyes')
        texture=Image.open(io.BytesIO(archive.read(ROOT+'textures/entity/lilith_mask.png')))
        if texture.size==(512,768):
            raise ValueError('Select the original local mesh archive, before the gallery rework')
        def vertices(d):
            return np.asarray(d['parts']['root']['vertices'],dtype=float).reshape(-1,8)
        data=vertices(mask)
        image=bake_face(data,vertices(eyes),texture)
        mask['parts']['root']['vertices']=data.round(6).ravel().tolist()
        body['parts']['root']['vertices']=soften_body(vertices(body)).round(6).ravel().tolist()
    dest=out/ROOT
    (dest/'mesh').mkdir(parents=True,exist_ok=True)
    (dest/'textures/entity').mkdir(parents=True,exist_ok=True)
    for name,d in [('body',body),('mask',mask)]:
        (dest/f'mesh/lilith_{name}.mesh.json').write_text(json.dumps(d,separators=(',',':')),'utf8')
    image.save(dest/'textures/entity/lilith_mask.png')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    bake(args.archive,args.output)
