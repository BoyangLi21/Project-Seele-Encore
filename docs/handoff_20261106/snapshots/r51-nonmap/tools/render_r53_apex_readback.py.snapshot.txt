"""Render the measured old/candidate apex blocks; no invented game screenshot."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from query_blocks import read_box

BASE=Path('F:/eva/artifacts/r53_repair_20261015')
def render():
 scale=2;im=Image.new('RGB',(1100*scale,600*scale),'#101a25');draw=ImageDraw.Draw(im)
 font='C:/Windows/Fonts/msyh.ttc'
 title=ImageFont.truetype(font,26*scale);text=ImageFont.truetype(font,18*scale)
 draw.text((32*scale,22*scale),'金字塔顶部 · 实际方块模型',font=title,fill='#eff6fc')
 draw.text((32*scale,65*scale),'候选副本已写入；当前试玩存档尚未应用',font=text,fill='#afc3d5')
 for index,(name,label) in enumerate((('WORLD','原顶部'),('CANDIDATE','修改后：齐平金属顶盖'))):
  blocks=read_box(BASE/name,'projectseele:geofront',(20,-401,317),(40,-384,337))
  solid={p:s for p,s in blocks.items()if s!='minecraft:air'}
  centre=(280+index*540)*scale;bottom=535*scale;unit=11*scale
  def project(x,y,z):return centre+(x-z)*unit,bottom+(x+z)*unit*.42-y*unit*1.3
  def p3(p,dx,dy,dz):return project(p[0]-30+dx,p[1]+401+dy,p[2]-327+dz)
  def colour(state):
   if 'white_concrete' in state:return (197,205,212)
   if 'red_concrete' in state:return (153,30,45)
   if 'beacon' in state:return (146,231,236)
   if 'alert_light' in state:return (246,65,67)
   if 'machine_panel' in state:return (74,95,106)
   return (52,52,61)
  for p in sorted(solid,key=lambda p:(p[0]+p[2]+p[1]*.01,p[1])):
   base=colour(solid[p])
   for adjacent,verts,factor in [((0,0,1),[(0,0,1),(1,0,1),(1,1,1),(0,1,1)],.72),((1,0,0),[(1,0,0),(1,0,1),(1,1,1),(1,1,0)],.9),((0,1,0),[(0,1,0),(1,1,0),(1,1,1),(0,1,1)],1.18)]:
    if tuple(p[i]+adjacent[i]for i in range(3))in solid:continue
    fill=tuple(min(255,round(c*factor))for c in base)
    draw.polygon([p3(p,*v)for v in verts],fill=fill,outline=tuple(max(0,c-12)for c in fill),width=1)
  draw.text(((70+index*540)*scale,130*scale),label,font=text,fill='#f2f6fa')
 dest=BASE/'visual-clarification-20261016/APEX_ACTUAL_BLOCK_READBACK.png';dest.parent.mkdir(exist_ok=True)
 im.resize((1100,600),Image.Resampling.LANCZOS).save(dest);print(dest)
if __name__=='__main__':render()
