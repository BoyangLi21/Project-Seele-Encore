"""Every rendered frame in numbered sheets; no unseen-frame approval."""
from pathlib import Path
import argparse,json,math
from PIL import Image,ImageDraw,ImageFont

ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
out=args.out;receipt=json.loads((out/'complete_review_receipt.json').read_text('utf8'))
font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',14)
for page in range(math.ceil(len(receipt['frames'])/96)):
    canvas=Image.new('RGB',(1600,12*112),(18,20,24));draw=ImageDraw.Draw(canvas)
    for i,row in enumerate(receipt['frames'][page*96:(page+1)*96]):
        x=(i%8)*200;y=(i//8)*112
        frame=Image.open(out/'complete_review_frames'/f"{row['index']:04d}.png").convert('RGB');frame.thumbnail((200,92))
        canvas.paste(frame,(x,y));draw.text((x+3,y+92),f"F{row['source_frame']:04d}  {row['time_seconds']:.2f}s",font=font,fill=(225,225,225))
    canvas.save(out/f'complete_sheet_{page+1:02d}.png')
print('Saved',math.ceil(len(receipt['frames'])/96),'sheets covering',len(receipt['frames']),'actual frames')
