"""Rendered stock Create control probe on the single guarded construction copy."""
from pathlib import Path
import argparse,json,math,subprocess,sys,time
from freeze_native_r44 import freeze
from release_combat_r36 import guard
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('job',type=Path);a=p.parse_args();guard();job=a.job.resolve();data=json.loads(job.read_text('utf8'));world=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW';assert Path(data['world']).resolve()==world.resolve()
 out=ROOT/'artifacts/rebuild_r45/city_motion/native_control'/time.strftime('%Y%m%d_%H%M%S');out.mkdir(parents=True)
 spec=json.loads((ROOT/'.Codex/client-launch-r17.json').read_text('utf8'));cmd=[x for x in spec['command']if not x.startswith('-Dprojectseele.')]
 props={'regionalBuild':'r44-facility-photos','nativeReviewWorld':world.name,'r45CityCreateProbe':job.as_posix(),'photoCaptureHoldTicks':'1000',
  'bodyPoseReview':(ROOT/'artifacts/server-ready-r44-stage/stage/client/projectseele-local-maps/eva_body_r43.json').as_posix(),
  'gameplayReviewDirectory':(ROOT/'artifacts/server-ready-r44-stage/stage/client/projectseele-local-maps').as_posix()}
 cmd[1:1]=['-Dprojectseele.'+k+'='+v for k,v in props.items()];cmd[cmd.index('--quickPlaySingleplayer')+1]=world.name;spec['command']=cmd;spec=freeze(spec,out)
 x,y,z=data['anchor'];at=[x+24.5,y+16,z-29.5];target=[x,y+12,z];d=[target[i]-at[i]for i in range(3)];d[1]-=1.62
 views=[dict(file='city_create_actual.png',position=at,yaw=math.degrees(math.atan2(-d[0],d[2])),pitch=-math.degrees(math.atan2(d[1],math.hypot(d[0],d[2]))),warmupTicks=180,requiredSections=[])]
 (world/'r30_photo_views.json').write_text(json.dumps(views,indent=2),'utf8');(out/'input.json').write_bytes(job.read_bytes());launch=out/'launch.json';launch.write_text(json.dumps(spec,indent=2),'utf8')
 with(out/'native.log').open('w',encoding='utf8')as f:result=subprocess.run([sys.executable,'tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=360)
 report=Path(data['output']);observed=sorted(report.glob('*json'));print('Create probe exit',result.returncode,'reports',[p.name for p in observed],'logs',out)
 if result.returncode:raise SystemExit(result.returncode)
 failures=[p for p in observed if p.name=='failed.json']
 if failures:raise RuntimeError('Native control probe failed; inspect '+str(failures[0]))
if __name__=='__main__':main()
