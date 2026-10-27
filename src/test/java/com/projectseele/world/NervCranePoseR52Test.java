package com.projectseele.world;

import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Compare the common endpoint evaluator with the exact original draw block.
 * No entities/worlds/GL, and no continuous sweep claim from these samples. */
public final class NervCranePoseR52Test
{
    private static int checks;private static void check(boolean ok,String reason){checks++;if(!ok)throw new AssertionError(reason);}
    public static void main(String[] args)
    {
        for(var outer:new Quaternionf[]{new Quaternionf(),new Quaternionf().rotationY((float)Math.PI),new Quaternionf().rotationY(.73F)})for(int i=0;i<=100;i++)
        {
            var origin=new Vec3(12.5,-609.25,317.5);var machine=RigidTransform.of(origin,outer);var world=RigidTransform.of(origin.add(0,-28.25,3.75),new Quaternionf().rotationZYX(.19F,.63F,-.21F));var mountSource=new Vec3(.2,.7,1.1);double bottom=-28.25+26.25*i/100;
            for(boolean coupled:new boolean[]{true,false})
            {
                var common=NervCranePoseR52.evaluate(machine,bottom,world,coupled,null,null,mountSource);
                // These are the actual source statements in the original draw;
                // the common path cannot substitute another local/world frame.
                var local=NervMachineFrameR52.worldToLocal(origin,outer,world.transformPoint(EntryPlugKinematics.CRANE_ATTACHMENT_P),world.rotation());Vec3 anchor=local.translation(),lower=new Vec3(0,bottom,0);var rotation=local.rotation();float released=1;
                if(coupled){lower=anchor;released=0;}else{double travel=Math.max(1,NervCranePoseR52.STOW_BOTTOM_R53-anchor.y),linear=Math.max(0,Math.min(1,(lower.y-anchor.y)/travel));double rise=travel*smooth((float)linear);var f=rotation.transform(new Vector3f(0,0,1));var axis=new Vec3(f.x,f.y,f.z);double axial=Math.min(rise,2*Math.max(.25,axis.y));lower=anchor.add(axis.scale(axial/Math.max(.25,axis.y))).add(0,rise-axial,0);released=(float)Math.max(0,Math.min(1,rise/.65));rotation.slerp(new Quaternionf().rotationX((float)-Math.PI/2),smooth((float)((rise-Math.min(2,travel*.5))/Math.max(.1,travel-Math.min(2,travel*.5)))));}
                check(common.grip().translation().distanceToSqr(lower)<1e-12,"Production lower mount moved");check(common.grip().rotationErrorDegrees(RigidTransform.of(lower,rotation))<.0001,"Production gripper orientation changed");check(common.released()==released,"Production jaw phase changed");
                var p=rotation.transform(new Vector3f((float)mountSource.x,(float)mountSource.y,(float)mountSource.z));var mount=lower.add(p.x,p.y,p.z);check(common.mount().distanceToSqr(mount)<1e-12&&common.yoke().distanceToSqr(mount.add(0,.45,0))<1e-12,"Production ropes/yoke endpoints changed");
            }
        }
        var frame=RigidTransform.of(new Vec3(12,-600,300),new Quaternionf());
        var reference=new Vec3(12,-623,302);var orientation=new Quaternionf().rotationX(-1.2F);
        var from=new NervCranePoseR52.State(frame,-2,null,false,reference,orientation);
        var shift=new Vec3(0,0,.5);var translated=RigidTransform.of(frame.translation().add(shift),frame.rotation());
        var to=new NervCranePoseR52.State(translated,-2,null,false,reference.add(shift),orientation);
        var halfway=from.interpolate(to,.5);var start=from.pose(Vec3.ZERO);var middle=halfway.pose(Vec3.ZERO);
        check(middle.machine().transformPoint(middle.grip().translation()).distanceToSqr(start.machine().transformPoint(start.grip().translation()).add(shift.scale(.5)))<1e-10,"Migrating saved reference must carry the complete retracted chuck continuously");
        boolean rejected=false;try{from.interpolate(new NervCranePoseR52.State(translated,-2,null,false,reference.add(0,0,2),orientation),.5);}catch(IllegalArgumentException expected){rejected=true;}
        check(rejected,"Unrelated reference changes must still reject instead of teleporting the chuck");
        // UN hoists can carry a capsule across the NERV-only bearing plane.
        var unPlug=RigidTransform.of(new Vec3(0,-24,0),new Quaternionf().rotationY((float)Math.PI/2));
        var unState=new NervCranePoseR52.State(RigidTransform.identity(),-24,unPlug,true,null,null);
        var unPose=unState.pose(Vec3.ZERO,false);
        check(unPose.grip().rotationErrorDegrees(unPlug)<.001,"UN clamp must retain its actual capsule orientation");
        boolean planarRejected=false;
        try{unState.pose(Vec3.ZERO,true);}catch(IllegalArgumentException expected){planarRejected=true;}
        check(planarRejected,"Regression fixture must exercise the formerly misapplied NERV bearing restriction");
        System.out.println("Actual original crane pose endpoint comparison PASS checks="+checks+"; no native/continuous sweep acceptance");
    }
    private static float smooth(float x){x=Math.max(0,Math.min(1,x));return x*x*x*(x*(x*6-15)+10);}
}
