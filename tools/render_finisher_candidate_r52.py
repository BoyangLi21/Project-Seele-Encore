"""Preview exact candidate frames and selected actual surfaces with authored camera."""
from pathlib import Path
import argparse,json,subprocess,hashlib,zipfile,io
from PIL import Image
import numpy as np
from r52_motion_core import selected,read
from author_finisher_r52 import Preview

def main():
    ap=argparse.ArgumentParser()
    for key in ('body','assets','angel-rig','clip','out'):ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--aspect',choices=('4:3','16:9'),default='4:3')
    ap.add_argument('--movie',action='store_true');ap.add_argument('--material-jar',type=Path);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    body,hero,alien=selected(a.body,a.assets,a.angel_rig);clip_bytes=a.clip.read_bytes();clip=json.loads(clip_bytes);clip_sha=hashlib.sha256(clip_bytes).hexdigest()
    textures=None;material_sha=None
    if a.material_jar:
        material_sha=hashlib.sha256(a.material_jar.read_bytes()).hexdigest();textures={}
        with zipfile.ZipFile(a.material_jar) as archive:
            mesh=json.loads(archive.read('assets/projectseele/mesh/eva_unit01_anatomical_hands_r45.mesh.json'))
            for name,part in mesh['parts'].items():
                actual=np.asarray(part['vertices']).reshape(-1,8);original=np.asarray(hero.hand_mesh['parts'][name]['vertices']).reshape(-1,8)
                assert np.array_equal(actual[:,[0,1,2,5,6,7]],original[:,[0,1,2,5,6,7]])
                assert part['pivot']==hero.hand_mesh['parts'][name]['pivot']
                hero.uv[name]=actual[:,3:5]
            for name in ('eva_unit01','sachiel'):
                textures[name]=np.asarray(Image.open(io.BytesIO(archive.read('assets/projectseele/textures/entity/'+name+'.png'))).convert('RGB'))
    def visual(size):
        view=Preview(a.assets,size)
        if textures is not None:view.textures=textures
        return view
    def item(i):
        return dict(t=i/clip['fps'],name='exact candidate frame '+str(i),eva=hero.decode(clip['eva']['frames'][i],clip['eva']['bones']),angel=alien.decode(clip['angel']['frames'][i],clip['angel']['bones']),hr=np.asarray(clip['eva']['root_blocks'][i]),ar=np.asarray(clip['angel']['root_blocks'][i]))
    shots=[('guard',0),('wrist_pressure',3.2),('landed',5.5),('core_chamber',7.9),('core_contact',8.35),('palms_and_feet',13),('low_crouch',14),('standing_turn',15.4),('embrace',18.25),('natural_arms',22.8)]
    full_size=(960,540) if a.aspect=='16:9' else (960,720);cell_size=(480,270) if a.aspect=='16:9' else (480,360)
    preview=visual(full_size);sheet=Image.new('RGB',(cell_size[0]*5,cell_size[1]*2))
    for j,(name,seconds) in enumerate(shots):
        index=round(seconds*clip['fps']);preview.set_camera(clip['camera']['position'][index],clip['camera']['target'][index]);preview.fov=clip['camera']['fov'][index]
        p=item(index);im=preview.render(p,name);im.save(a.out/(name+'_candidate.png'));sheet.paste(im.resize(cell_size),((j%5)*cell_size[0],(j//5)*cell_size[1]))
    sheet.save(a.out/'CANDIDATE_CONTACT_SHEET.jpg',quality=88)
    for name,eye in [('front',[-110,66,60]),('side',[-29,64,166])]:
        view=visual(full_size);view.set_camera(eye,[-24,28,60]);view.render(item(1095),'embrace '+name).save(a.out/('embrace_'+name+'.png'))
    for label,times in [('IMPACT_SEQUENCE',[7.9,8.12,8.35,8.65,8.90]),('SUPPORT_SEQUENCE',[12,13,13.2,13.6,14,15.4]),('APPROACH_SEQUENCE',[15.4,16.1,16.8,17.5,18.1,18.25])]:
        strip=Image.new('RGB',(cell_size[0]*len(times),cell_size[1]))
        for j,t in enumerate(times):
            index=round(t*clip['fps']);preview.set_camera(clip['camera']['position'][index],clip['camera']['target'][index]);preview.fov=clip['camera']['fov'][index]
            strip.paste(preview.render(item(index),label).resize(cell_size),(cell_size[0]*j,0))
        strip.save(a.out/(label+'.jpg'),quality=90)
    if a.movie:
        movie_size=(640,360) if a.aspect=='16:9' else (640,480);preview=visual(movie_size);proc=subprocess.Popen(['ffmpeg','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',str(movie_size[0])+'x'+str(movie_size[1]),'-r','12','-i','-','-an','-c:v','libx264','-preset','fast','-crf','26','-pix_fmt','yuv420p',str(a.out/'continuous_constrained_low.mp4')],stdin=subprocess.PIPE)
        for i in range(0,len(clip['eva']['frames']),5):
            preview.set_camera(clip['camera']['position'][i],clip['camera']['target'][i]);preview.fov=clip['camera']['fov'][i]
            p=item(i);proc.stdin.write(preview.render(p,p['name']).tobytes())
            if i%300==0:print('rendered exact frame',i,flush=True)
        proc.stdin.close();proc.wait()
        for name,start,duration in [('rise_continuous',12,3.4),('approach_embrace_continuous',15.4,3.2)]:
            subprocess.run(['ffmpeg','-loglevel','error','-y','-ss',str(start),'-i',str(a.out/'continuous_constrained_low.mp4'),'-t',str(duration),'-an','-c:v','libx264','-preset','fast','-crf','23',str(a.out/(name+'.mp4'))],check=True)
    (a.out/'PREVIEW_RECEIPT.json').write_text(json.dumps({'candidate_sha256':clip_sha,'candidate':str(a.clip.resolve()),'camera':'authored per-frame position/target/FOV, actual selected meshes','aspect':a.aspect,'source_fps':clip['fps'],'preview_fps':12 if a.movie else None,'frame_step':5 if a.movie else None,'material_jar_sha256':material_sha,'repaired_hand_uv_geometry_and_normals_identical':material_sha is not None,'native_eye_jaw_validation':'not evaluated by offline geometry preview; see separate native eye/jaw review','native_verified':False,'user_accepted':False},indent=2),encoding='utf-8')
    print('Exact candidate preview complete',flush=True)
if __name__=='__main__':main()
