"""Flat measured before/after projections for an authored regional facade patch."""
from pathlib import Path
import argparse,json,gzip,collections
from query_blocks import read_box
from PIL import Image,ImageDraw,ImageFont

def main():
 a=argparse.ArgumentParser();a.add_argument('--world',type=Path,required=True);a.add_argument('--patch',type=Path,required=True);a.add_argument('--catalogue',type=Path,required=True);args=a.parse_args()
 p=args.patch;records=json.loads(args.catalogue.read_text('utf8'))['buildings'];m=json.loads((p/'manifest.json').read_text('utf8'))
 ids={kind:next(r['id']for r in m['buildings']if r['palette']==kind)for kind in sorted(set(r['palette']for r in m['buildings']))};counts=collections.Counter();samples={}
 for r in map(json.loads,gzip.open(p/'forward.jsonl.gz','rt',encoding='utf8')):
  counts[r['after']]+=1
  if r['owner'].removeprefix('r54/facade/')in ids.values():samples.setdefault(r['owner'],[]).append(r)
 for owner,rows in samples.items():
  folder=p/'samples'/owner.removeprefix('r54/facade/').replace('/','_');folder.mkdir(parents=True,exist_ok=True)
  for name,inv in [('forward',False),('inverse',True)]:
   with gzip.open(folder/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
    for row in rows:
     r=row.copy()
     if inv:r['before'],r['after']=r['after'],r['before']
     f.write(json.dumps(r)+'\n')
 (p/'material_distribution.json').write_text(json.dumps(dict(counts),indent=2),encoding='utf8');(p/'samples.json').write_text(json.dumps(ids,indent=2),encoding='utf8')
 colors={'air':'#29333d','gray_concrete':'#53585d','white_concrete':'#d3d4ce','light_gray_concrete':'#adaeaa','smooth_sandstone':'#c8bd9b','white_terracotta':'#baa89a','light_gray_terracotta':'#8c7970','polished_andesite':'#777d7d','gray_stained_glass':'#486272','brown_terracotta':'#76594a','smooth_stone':'#929a9e','stone_brick_slab':'#747879','smooth_stone_slab':'#989f9f','chiseled_quartz_block':'#c7c4bb','birch_wall_sign':'#d7c295','store_door':'#a3b3b4','dark_oak_planks':'#554131'}
 font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20);small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15);im=Image.new('RGB',(1200,80+len(ids)*300),'#18212a');draw=ImageDraw.Draw(im);draw.text((20,15),'Measured facade material study | no game lighting | continuous wall fields',font=font,fill='white')
 for n,(kind,ident)in enumerate(ids.items()):
  r=next(v for v in records if v['id']==ident);lo,hi=r.get('actual_building_bounds',r['planned_bounds']);z=hi[2];b=read_box(args.world,'projectseele:geofront',(lo[0],lo[1],z),(hi[0],hi[1],z+1));patch={tuple(v['pos']):v['after']for v in samples['r54/facade/'+ident]};cell=min(11,260//(hi[1]-lo[1]+1));ox=30;oy=70+n*300
  draw.text((ox,oy),kind+' / '+ident+' / before',font=small,fill='#c7d5e0');draw.text((630,oy),kind+' / proposed',font=small,fill='#c7d5e0')
  for side in [0,1]:
   for x in range(lo[0],hi[0]+1):
    for y in range(lo[1],hi[1]+1):
     at=None
     for zz in[z+1,z]:
      q=(x,y,zz);st=patch.get(q,b.get(q))if side else b.get(q)
      if st and st.split(':')[-1]!='air':at=st;break
     name=(at or'minecraft:air').split(':')[-1].split('[')[0];color=colors.get(name,'#656b71');px=ox+side*600+(x-lo[0])*cell;py=oy+25+(hi[1]-y)*cell
     draw.rectangle((px,py,px+cell-1,py+cell-1),fill=color)
 im.save(p/'front_comparison.png')
 (p/'index.html').write_text('<meta charset="utf-8"><title>R54 Regional facade material study</title><style>body{background:#18212a;color:#c7d5e0;font:16px sans-serif;margin:24px}img{max-width:100%}a{color:#9bd}</style><h1>Regional facade material study</h1><p>Measured block projections. Material/layout comparison, not a game render. Original doors and glazing remain.</p><img src="front_comparison.png"><p><a href="material_distribution.json">Material distribution</a> | <a href="manifest.json">Building list</a></p>',encoding='utf8')
 print(p/'front_comparison.png')
if __name__=='__main__':main()
