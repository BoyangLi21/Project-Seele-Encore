"""Render exact planned solid geometry for massing/facade self-review, never a native photo."""
from pathlib import Path
import argparse,gzip,json,math
import numpy as np
from PIL import Image,ImageDraw
from inspect_map_assets import state_colour


def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);a=p.parse_args();out=a.plan/'planned_geometry_isometric.png';assert not out.exists()
    rows=[json.loads(s) for s in gzip.open(a.plan/'forward.jsonl.gz','rt',encoding='utf8')]
    cells={tuple(r['pos']):r['after'] for r in rows if r['after'].split('[')[0] not in {'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light'}}
    district=json.loads((a.plan/'new_district.json').read_text('utf8'));allcoords=np.array(list(cells));lo=allcoords.min(0);hi=allcoords.max(0)
    def project(q):
        x,y,z=q;return np.array([(x-z)*.866,(x+z)*.5-y*1.2])
    projected=np.array([project(q) for q in allcoords[::max(1,len(allcoords)//10000)]]);mn=projected.min(0);mx=projected.max(0);scale=min(1700/(mx[0]-mn[0]),1050/(mx[1]-mn[1]))
    image=Image.new('RGB',(1800,1200),(232,236,233));draw=ImageDraw.Draw(image)
    def xy(q):v=(project(q)-mn)*scale;return (float(v[0])+50,float(v[1])+90)
    faces=[]
    face_specs=[((1,0,0),[(1,0,0),(1,1,0),(1,1,1),(1,0,1)],.8),((0,0,1),[(0,0,1),(1,0,1),(1,1,1),(0,1,1)],.65),((0,1,0),[(0,1,0),(1,1,0),(1,1,1),(0,1,1)],1.)]
    palette={}
    for q,st in cells.items():
        if st not in palette:
            c=state_colour(st.split('[')[0]);palette[st]=tuple(int(v) for v in c[:3])
        for delta,corners,shade in face_specs:
            other=tuple(q[i]+delta[i] for i in range(3))
            if other in cells:continue
            colour=tuple(round(v*shade) for v in palette[st]);corners=[tuple(q[i]+v[i] for i in range(3)) for v in corners]
            faces.append((sum(q),q[1],corners,colour))
    for depth,y,corners,colour in sorted(faces,key=lambda r:(r[0],r[1])):draw.polygon([xy(q) for q in corners],fill=colour)
    draw.text((30,22),district['id']+' | EXACT PLANNED BLOCK GEOMETRY | NOT MINECRAFT / NOT A VISUAL PASS',fill=(20,30,30))
    draw.text((30,1160),f"New buildings: {len(district['buildings'])} | Facades/roofs/real floor datums visible | Existing terrain outside patch not rendered",fill=(20,30,30))
    image.save(out);print(out,'solid cells',len(cells),'visible faces',len(faces),flush=True)


if __name__=='__main__':main()
