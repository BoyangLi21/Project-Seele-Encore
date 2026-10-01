"""Compare exact source, official retarget and saved contact local rotations."""
import argparse,json,sys,math
from pathlib import Path
import bpy

ap=argparse.ArgumentParser();ap.add_argument('--raw',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--leg-frames',default='465,466');ap.add_argument('--leg-side',choices=('l','r'),default='l');ap.add_argument('--hand-frames',default='1033,1034');ap.add_argument('--trace-label',default='')
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);records=json.loads((args.out/'contact_pass_receipt.json').read_text())['records']
side=args.leg_side;word='Left'if side=='l'else'Right';first,last=[int(v)for v in args.leg_frames.split(',')];hand_first,hand_last=[int(v)for v in args.hand_frames.split(',')]
pairs=[(first,last,(word+'UpLeg',word+'Leg',word+'Foot'),('leg_'+side,'shin_'+side,'foot_'+side)),(hand_first,hand_last,('RightArm','RightForeArm','RightHand'),('arm_r','forearm_r','hand_r','finger_index_r'))]
rows=[]
for first,last,source_names,target_names in pairs:
    row=dict(frames=[first,last],stages={})
    for folder,stage,names,rig_name in [(args.raw,'source',source_names,'ACCAD_continuous_original'),(args.raw,'official',target_names,'eva_unit01_AUTHOR'),(args.out,'author',target_names,'eva_unit01_AUTHOR'),(args.out,'deform',target_names,'eva_unit01_DEFORM')]:
        bpy.ops.wm.open_mainfile(filepath=str(folder/'rokoko_continuous_legs_r44.blend'));samples=[]
        for f in (first,last):
            r=records[f-1];raw_frame=r['raw_frame']
            if stage in ('source','official') and raw_frame is None:
                # The first bridge frame interpolates from the previous exact raw sample.
                raw_frame=records[first-1]['raw_frame'];row['bridge_source_sample_is_preceding_boundary']=True
            bpy.context.scene.frame_set(raw_frame if stage in ('source','official') else f);bpy.context.view_layer.update()
            rig=bpy.data.objects[rig_name].evaluated_get(bpy.context.evaluated_depsgraph_get())
            samples.append({n:dict(local=list(rig.pose.bones[n].matrix_basis.to_quaternion()),world=list(rig.pose.bones[n].matrix.to_quaternion())) for n in names})
        changes={}
        for n in names:
            changes[n]={space:math.degrees(2*math.acos(min(1.,abs(sum(a*b for a,b in zip(samples[0][n][space],samples[1][n][space])))))) for space in ('local','world')}
        row['stages'][stage]=dict(samples=samples,physical_rotation_degrees=changes)
    row['contacts']=[records[f-1]['source_contacts']for f in (first,last)];rows.append(row)
(args.out/('first_discontinuity_trace'+('_'+args.trace_label if args.trace_label else'')+'.json')).write_text(json.dumps(rows,indent=2),'utf8');print(json.dumps(rows,indent=2))
