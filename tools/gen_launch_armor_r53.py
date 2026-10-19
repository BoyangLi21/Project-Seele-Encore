"""Original industrial plate artwork, authored from geometric primitives."""
from pathlib import Path
import json
import numpy as np
from PIL import Image,ImageDraw

root=Path(__file__).resolve().parents[1]/'src/main/resources/assets/projectseele'
rng=np.random.default_rng(53)
base=np.zeros((256,128,3),dtype=np.uint8)
for channel,value in enumerate((155,164,147)):
    base[:,:,channel]=np.clip(value+rng.integers(-2,3,(256,128)),0,255)
plate=Image.fromarray(base);draw=ImageDraw.Draw(plate)
draw.rectangle((0,0,127,255),outline=(56,66,57),width=1)
draw.line((1,254,126,254),fill=(188,193,174),width=1)
draw.line((126,1,126,253),fill=(185,192,174),width=1)
for x in (5,122):
    for y in (6,249):
        draw.ellipse((x-1,y-1,x+1,y+1),fill=(64,72,62))
draw.rounded_rectangle((10,202,35,235),radius=2,outline=(91,103,88),width=1)
draw.line((13,204,13,232),fill=(180,185,167),width=1)
draw.rectangle((27,218,30,219),fill=(61,72,62))
texture=root/'textures/block/nerv_launch_armor.png';texture.parent.mkdir(parents=True,exist_ok=True);plate.save(texture)
Image.new('RGB',(128,256),(36,0,0)).save(root/'textures/block/nerv_launch_armor_s.png')
variants={}
for row in range(16):
    for col in range(8):
        name=f'nerv_launch_armor_{col}_{row}'
        # Vertical faces have a continuous plate coordinate rather than a tile seam.
        uv=[col*2,(15-row),col*2+2,(16-row)]
        faces={side:dict(uv=uv,texture='#all',cullface=side)for side in ('north','south','east','west')}
        faces.update({side:dict(uv=[2,2,3,3],texture='#all',cullface=side)for side in ('up','down')})
        model=dict(textures={'all':'projectseele:block/nerv_launch_armor','particle':'projectseele:block/nerv_launch_armor'},elements=[{'from':[0,0,0],'to':[16,16,16],'faces':faces}])
        (root/f'models/block/{name}.json').write_text(json.dumps(model,separators=(',',':')),'utf8')
        variants[f'column={col},row={row}']={'model':'projectseele:block/'+name}
(root/'blockstates/nerv_launch_armor.json').write_text(json.dumps({'variants':variants},separators=(',',':')),'utf8')
print('Original plate texture and 128 seamless block fragments generated')
