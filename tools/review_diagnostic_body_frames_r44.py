"""Labeled whole-body diagnostic sheet, preserving the renderer's framing."""
from pathlib import Path
import argparse,json
from PIL import Image,ImageDraw,ImageFont

ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
out=args.out;receipt=json.loads((out/'diagnostic_review_receipt.json').read_text('utf8'))
font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',18)
rows=receipt['frames'];canvas=Image.new('RGB',(1440,((len(rows)+2)//3)*295+46),(18,20,24));draw=ImageDraw.Draw(canvas)
draw.text((12,10),'UNAPPROVED | fixed direction / scale | actual body AABB camera centre | world grid 10 m',font=font,fill=(255,195,110))
for i,row in enumerate(rows):
    x=(i%3)*480;y=(i//3)*295+46
    frame=Image.open(out/'diagnostic_review_frames'/f"{row['index']:04d}.png").convert('RGB');frame.thumbnail((480,270))
    canvas.paste(frame,(x,y))
    draw.text((x+5,y+270),f"F{row['source_frame']:04d} {row['time_seconds']:.2f}s  minZ {row['actual_mesh_bottom']:+.3f}m",font=font,fill=(225,225,225))
canvas.save(out/'diagnostic_full_body_sheet.png')
print(out/'diagnostic_full_body_sheet.png')
