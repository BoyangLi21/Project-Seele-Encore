"""Compare actual saved source and retarget joint flexion before contact fixes."""
from pathlib import Path
import argparse,json,sys,math
import bpy

p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);assert a.out.is_absolute() and not a.out.exists()
source=next(o for o in bpy.data.objects if o.type=='ARMATURE' and 'Hips' in o.pose.bones)
target=next(o for o in bpy.data.objects if o.type=='ARMATURE' and o.name.endswith('_AUTHOR'))
records=[]
def flex(a,b,c):return math.degrees((b-a).angle(c-b))
def point(rig,name):return rig.matrix_world@rig.pose.bones[name].head
for frame in [0,1,10,19,28,37]:
    bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
    s=source.evaluated_get(deps);t=target.evaluated_get(deps);row={'frame':frame}
    for side,word in [('l','Left'),('r','Right')]:
        row['source_knee_'+side]=flex(*(point(s,word+n)for n in ('UpLeg','Leg','Foot')))
        row['target_knee_'+side]=flex(*(point(t,n+'_'+side)for n in ('leg','shin','foot')))
        for label,sa,sb,ta,tb in [('upper_arm','Arm','ForeArm','arm','forearm'),
                                   ('forearm','ForeArm','Hand','forearm','hand')]:
            u=(point(s,word+sb)-point(s,word+sa)).normalized()
            v=(point(t,tb+'_'+side)-point(t,ta+'_'+side)).normalized()
            row['source_'+label+'_direction_'+side]=list(u)
            row['target_'+label+'_direction_'+side]=list(v)
            row[label+'_direction_difference_'+side]=math.degrees(u.angle(v))
    for name,rig,hip,head in [('source',s,'Hips','Head'),('target',t,'pelvis','head')]:
        vector=point(rig,head)-point(rig,hip)
        row[name+'_trunk_forward_lean_degrees']=math.degrees(math.atan2(vector.y,vector.z))
    records.append(row)
a.out.write_text(json.dumps({'source':source.name,'target':target.name,'samples':records,
    'scope':'Saved source FK vs actual Rokoko target before contact solver; not game/native acceptance'},indent=2),'utf8')
print(json.dumps(records))
