"""Expose every encoded 12fps source-comparison frame, without selecting poses."""
from pathlib import Path
import argparse,json,subprocess
from PIL import Image,ImageDraw

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--comparison',type=Path,required=True)
parser.add_argument('--basename',default='12to18_6')
parser.add_argument('--start',type=float,default=12)
parser.add_argument('--expected-frames',type=int,default=80)
parser.add_argument('--views',choices=('side','front'),nargs='+',default=['side','front'])
args=parser.parse_args();receipt=[]
for view in args.views:
    movie=args.comparison/f'COMPARISON_{view}_{args.basename}.mp4'
    process=subprocess.Popen(['ffmpeg','-v','error','-i',str(movie),'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
    frames=[];stride=1280*360*3
    while True:
        data=process.stdout.read(stride)
        if not data:break
        assert len(data)==stride
        frames.append(Image.frombytes('RGB',(1280,360),data).crop((640,0,1280,360)))
    assert process.wait()==0 and len(frames)==args.expected_frames
    for start in range(0,len(frames),12):
        sheet=Image.new('RGB',(1600,744),(12,18,24));draw=ImageDraw.Draw(sheet)
        for tile,frame in enumerate(frames[start:start+12]):
            xx=tile%4*400;yy=tile//4*248
            index=round(args.start*60)+(start+tile)*5
            draw.text((xx+8,yy+4),f'body3f authored {index/60:.3f}s / frame {index}',fill='white')
            sheet.paste(frame.resize((400,225)),(xx,yy+23))
        sheet.save(args.comparison/f'CONTIGUOUS_NEW_{view}_{start//12:02d}.jpg',quality=95)
    first=round(args.start*60);last=first+(len(frames)-1)*5
    receipt.append(dict(view=view,encoded_frames=len(frames),first_source_frame=first,last_source_frame=last,source_stride=5,first_seconds=args.start,last_seconds=last/60))
(args.comparison/'CONTIGUOUS_PAGES_RECEIPT.json').write_text(json.dumps(dict(frames=receipt,scope='Every encoded offline 12fps comparison frame. Source authoring remains 60fps; no native or between-sample acceptance inferred.'),indent=2),'utf8')
