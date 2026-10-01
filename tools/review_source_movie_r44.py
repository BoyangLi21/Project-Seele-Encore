from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import argparse,json,math,subprocess
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();p=args.out.resolve()
receipt=json.loads((p/'source_segment_receipt.json').read_text('utf8'));rows=receipt['frames'];label=receipt['segment']['label'];font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',13)
canvas=Image.new('RGB',(1440,math.ceil(len(rows)/8)*145+35),(18,20,24));draw=ImageDraw.Draw(canvas)
draw.text((8,8),f'Actual ACCAD {label} source joints; all{len(rows)}frames /30Hz; tubes are visualization, not skin',font=font,fill='white')
images=[]
for i,row in enumerate(rows):
    picture=Image.open(p/'frames'/f"{row['render_index']:04d}.png").convert('RGB');images.append(picture)
    x=(i%8)*180;y=(i//8)*145+35;canvas.paste(picture.resize((180,120)),(x,y))
    draw.text((x+3,y+122),f"SourceF{row['original_take_frame']:02d} {row['seconds']:.2f}s",font=font,fill=(255,100,80)if row['original_take_frame']in(44,45)else'white')
canvas.save(p/f'all{len(rows)}_source_frames.png')
images[0].save(p/f'source_{label}_normal.gif',save_all=True,append_images=images[1:],duration=[33 if i%3!=2 else 34 for i in range(len(images))],loop=0)
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','30','-i',str(p/'frames/%04d.png'),'-c:v','libx264','-preset','veryfast','-crf','20','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(p/f'source_{label}_original_normal_30fps.mp4')],check=True)
print('Saved all source frames and normal30Hz movie',p)
