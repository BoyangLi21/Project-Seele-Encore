"""Diagram the actual installed manifest; this is not a game screenshot."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
BASE=Path('F:/eva/artifacts/r53_repair_20261015')
def main():
 m=json.loads((BASE/'client/saves/SEELE_R53_WORLD/personnel_lifts_r52.json').read_text('utf8'))
 im=Image.new('RGB',(1200,730),'#0d1722');d=ImageDraw.Draw(im)
 font='C:/Windows/Fonts/msyh.ttc';big=ImageFont.truetype(font,27);normal=ImageFont.truetype(font,19);small=ImageFont.truetype(font,16)
 d.text((30,22),'原电梯延伸到机库 · 已安装坐标示意',font=big,fill='#edf6ff')
 d.text((30,65),'保留原井口、原楼层和同一节轿厢；平移段运行待实测。此图不是游戏截图。',font=normal,fill='#a9bfce')
 for i,identity in enumerate(('s20-command-rear-x12-z253-v4','r25-east-command-gallery')):
  l=next(v for v in m['lifts']if v['id']==identity);t=l['horizontal_transfer'];ox=30+i*590
  d.rounded_rectangle((ox,110,ox+560,690),radius=14,fill='#152534',outline='#365263',width=2)
  d.text((ox+20,128),'主电梯'if i==0 else'东侧电梯',font=big,fill='#e5f5fc')
  a=ox+85;b=ox+310;top=205;cut=335;bottom=615
  d.line((a,top,a,cut,b,cut,b,bottom),fill='#66dfcb',width=9,joint='curve')
  d.rounded_rectangle((a-20,235,a+20,277),radius=4,fill='#dbe6eb',outline='#0e171e',width=3)
  d.text((ox+135,235),'原轿厢',font=normal,fill='#e8f4fc')
  d.text((ox+22,180),'原总部井道',font=normal,fill='#e8f4fc')
  d.text((ox+22,284),'原楼层全部保留',font=normal,fill='#c1d4df')
  d.text((ox+140,355),f"Y={t['transfer_y']} 平移",font=normal,fill='#76e2cf')
  d.text((ox+20,390),f"上段轴线：{t['upper_controller_axis'][0]+3}, {t['upper_controller_axis'][1]}",font=small,fill='#adbfcb')
  d.text((ox+20,417),f"深段轴线：{t['lower_controller_axis'][0]+3}, {t['lower_controller_axis'][1]}",font=small,fill='#adbfcb')
  for y,label,py in ((-987,'观察层',470),(-1014,'登机层',525),(-1030,'发射层',580)):
   assert any(f['cabin'][1]==y for f in l['floors'])
   d.ellipse((b-8,py-8,b+8,py+8),fill='#f1c777');d.line((b+10,py,b+30,py),fill='#f1c777',width=2)
   d.text((b+39,py-13),f'{y} {label}',font=normal,fill='#f1dfad')
  d.text((ox+20,648),'主梯另保留 Dogma -1230'if i==0 else'B1 -554 接驳层继续保留',font=small,fill='#b4cbd9')
 dest=BASE/'visual-clarification-20261016/ORIGINAL_LIFTS_INSTALLED_PLAN.png';dest.parent.mkdir(exist_ok=True);im.save(dest);print(dest)
if __name__=='__main__':main()
