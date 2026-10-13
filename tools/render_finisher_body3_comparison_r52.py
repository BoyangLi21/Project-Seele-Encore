"""Same-camera, actual selected mesh comparison of the fixed late-action window."""
from pathlib import Path
import argparse,json,io,zipfile,subprocess
import numpy as np
from PIL import Image
from r52_motion_core import selected,read
from author_finisher_r52 import Preview

parser=argparse.ArgumentParser(description=__doc__)
for name in ('body','assets','angel-rig','old','clip','material-jar','out'):
    parser.add_argument('--'+name,type=Path,required=True)
parser.add_argument('--movie',action='store_true')
parser.add_argument('--start',type=float,default=12)
parser.add_argument('--end',type=float,default=18.6)
parser.add_argument('--times',type=float,nargs='+')
args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
_,hero,angel=selected(args.body,args.assets,args.angel_rig);clips=[read(args.old),read(args.clip)]
with zipfile.ZipFile(args.material_jar) as archive:
    textures={name:np.asarray(Image.open(io.BytesIO(archive.read('assets/projectseele/textures/entity/'+name+'.png'))).convert('RGB')) for name in ('eva_unit01','sachiel')}
    mesh=json.loads(archive.read('assets/projectseele/mesh/eva_unit01_anatomical_hands_r45.mesh.json'))
    for name,part in mesh['parts'].items():
        original=np.asarray(hero.hand_mesh['parts'][name]['vertices']).reshape(-1,8);current=np.asarray(part['vertices']).reshape(-1,8)
        assert np.array_equal(original[:,[0,1,2,5,6,7]],current[:,[0,1,2,5,6,7]])
        hero.uv[name]=current[:,3:5]
def item(clip,index):
    return dict(t=index/60,name='actual authored source',eva=hero.decode(clip['eva']['frames'][index],clip['eva']['bones']),angel=angel.decode(clip['angel']['frames'][index],clip['angel']['bones']),hr=np.asarray(clip['eva']['root_blocks'][index]),ar=np.asarray(clip['angel']['root_blocks'][index]))
times=args.times or [12,12.5,13.2,13.8,14.4,14.8,15.2,15.6,16.1,16.6,17.2,17.9,18.5]
views={'side':([8,48,130],[-21,27,60]),'front':([-100,50,78],[-24,27,60])}
for name,(eye,target) in views.items():
    preview=Preview(args.assets,(640,360));preview.textures=textures;preview.set_camera(eye,target);preview.fov=65
    for page,start in enumerate(range(0,len(times),5)):
        selected_times=times[start:start+5];sheet=Image.new('RGB',(1280,len(selected_times)*360))
        for row,time in enumerate(selected_times):
            for version,clip in enumerate(clips):
                image=preview.render(item(clip,round(time*60)),('native5 source' if version==0 else 'body3 candidate')+' same camera')
                sheet.paste(image,(version*640,row*360))
        sheet.save(args.out/f'COMPARISON_{name}_{page:02d}.jpg',quality=93)
    if args.movie:
        label=f'{args.start:g}to{args.end:g}'.replace('.','_')
        movie=args.out/f'COMPARISON_{name}_{label}.mp4'
        process=subprocess.Popen(['ffmpeg','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1280x360','-r','12','-i','-','-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',str(movie)],stdin=subprocess.PIPE)
        for index in range(round(args.start*60),round(args.end*60),5):
            joined=Image.new('RGB',(1280,360))
            for version,clip in enumerate(clips):joined.paste(preview.render(item(clip,index),('native5 source' if version==0 else 'body3 candidate')+' same camera'),(version*640,0))
            process.stdin.write(joined.tobytes())
        process.stdin.close();assert process.wait()==0
    print('Compared exact source view',name,flush=True)
(args.out/'COMPARISON_RECEIPT.json').write_text(json.dumps(dict(old=str(args.old.resolve()),new=str(args.clip.resolve()),same_camera=views,source_fps=60,preview_fps=12 if args.movie else None,actual_selected_original_mesh=True,scale_changes=False,native_verified=False,user_accepted=False,material_jar=str(args.material_jar.resolve()),limits='Offline selected original body/hand/Sachiel skin and fixed grid. Native GPU shaders, eye policy, jaw lighting and additional runtime covers are not simulated.'),indent=2),'utf8')
