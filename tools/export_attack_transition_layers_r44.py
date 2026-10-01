"""Export exact saved source/author FK for transition review; no pose edits."""
from pathlib import Path
import argparse,json,sys
import bpy

ap=argparse.ArgumentParser();ap.add_argument('--raw',type=Path,required=True);ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);args.out.mkdir(parents=True,exist_ok=True)
receipt=json.loads((args.candidate/'contact_pass_receipt.json').read_text('utf8'));records=receipt['records'];fixture=json.loads((args.candidate/'fixture.json').read_text('utf8'));actor=fixture['actors'][0]['name'];stages={}
for directory,stage in ((args.raw,'source_official'),(args.candidate,'authored')):
    bpy.ops.wm.open_mainfile(filepath=str(directory/'rokoko_continuous_legs_r44.blend'));rows=[]
    for r in records:
        if stage=='source_official'and r['raw_frame']is None:continue
        bpy.context.scene.frame_set(r['raw_frame']if stage=='source_official'else r['frame']);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();rigs={}
        for name in (('ACCAD_continuous_original',actor+'_AUTHOR')if stage=='source_official'else(actor+'_AUTHOR',)):
            obj=bpy.data.objects[name];rig=obj.evaluated_get(deps)
            rigs[name]={b.name:dict(head=list(obj.matrix_world@b.head),tail=list(obj.matrix_world@b.tail),world_quaternion_wxyz=list((obj.matrix_world@b.matrix).to_quaternion()),local_quaternion_wxyz=list(b.matrix_basis.to_quaternion()),parent=b.parent.name if b.parent else None)for b in rig.pose.bones}
        rows.append(dict(frame=r['frame'],raw_frame=r['raw_frame'],label=r['label'],rigs=rigs))
    stages[stage]=rows
(args.out/'actual_source_author_fk.json').write_text(json.dumps(dict(actor=actor,stages=stages,scope='Exact saved source and actual target FK. Joint centres are geometric references, not measured force/COM. Original source and authored scenes unmodified.'),separators=(',',':')),'utf8')
print('Exact layers exported',args.out,flush=True)
