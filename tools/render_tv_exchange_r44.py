"""CPU-only fixed-camera complete exchange review, from the saved scene."""
from pathlib import Path
import argparse,sys
import bpy
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/blocking_v1');ap.add_argument('--step',type=int,default=3);ap.add_argument('--start',type=int,default=1);ap.add_argument('--end',type=int,default=241);ap.add_argument('--frames');ap.add_argument('--width',type=int,default=960);ap.add_argument('--samples',type=int,default=2);args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]if'--'in sys.argv else[])
OUT=args.out.resolve();frames=OUT/'review_frames';frames.mkdir(parents=True,exist_ok=True);scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.render.threads_mode='FIXED';scene.render.threads=2;scene.cycles.samples=args.samples;scene.render.resolution_x=args.width;scene.render.resolution_y=round(args.width*9/16);scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.cycles.use_denoising=True
scene.render.use_persistent_data=True;scene.cycles.max_bounces=1;scene.cycles.diffuse_bounces=1;scene.cycles.glossy_bounces=0;scene.cycles.transmission_bounces=0;scene.cycles.volume_bounces=0
for frame in [int(v)for v in args.frames.split(',')]if args.frames else range(args.start,args.end+1,args.step):
    scene.frame_set(frame);scene.render.filepath=str(frames/f'{frame:04d}.png');bpy.ops.render.render(write_still=True)
    print('CPU review frame',frame,flush=True)
