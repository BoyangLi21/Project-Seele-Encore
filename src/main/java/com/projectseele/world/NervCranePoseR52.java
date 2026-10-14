package com.projectseele.world;

import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.util.Objects;

/** Endpoint evaluation of the existing production PlugGantryRenderer rig.
 * The exact same evaluator is intended for renderer and native clearance;
 * no plant/world positions are chosen here. */
public final class NervCranePoseR52
{
    public record State(RigidTransform machine,double bottom,RigidTransform plug,boolean coupled,Vec3 referenceWorld,Quaternionf referenceRotation)
    {
        public State{if(!Double.isFinite(bottom)||bottom>=0||coupled&&plug==null||(referenceWorld==null)!=(referenceRotation==null))throw new IllegalArgumentException("Complete actual crane state required");referenceRotation=referenceRotation==null?null:new Quaternionf(referenceRotation);}
        public State interpolate(State to,double t)
        {if(coupled!=to.coupled||machine.rotationErrorDegrees(to.machine)>.001||(plug==null)!=(to.plug==null)||!Objects.equals(referenceWorld,to.referenceWorld))throw new IllegalArgumentException("A mechanism change requires a coincident checked crane pose");return new State(machine.interpolate(to.machine,t),bottom+(to.bottom-bottom)*t,plug==null?null:plug.interpolate(to.plug,t),coupled,referenceWorld,referenceRotation);}
        public Pose pose(Vec3 mount){return evaluate(machine,bottom,plug,coupled,referenceWorld,referenceRotation,mount);}
    }
    /** Stable original cylinder roll through the downward vertical. The same
     * frame is used for draw and sweep, avoiding rotationTo's antipodal branch. */
    public static RigidTransform ropeFrame(Vec3 first,Vec3 last)
    {var y=last.subtract(first).normalize();var projection=new Vec3(1,0,0).subtract(y.scale(y.x));var x=projection.length()>1e-7?projection.normalize():new Vec3(0,0,1);return RigidTransform.fromAxes(first,x,y,x.cross(y));}
    /** Original R50 cylinder rotationTo. Kept separate from ropeFrame:
     * fixed ground-guide brackets retain their existing stable basis. */
    public static Quaternionf originalHoistRopeRotationR63(Vec3 first,Vec3 last)
    {var delta=last.subtract(first);double length=delta.length();if(length<1e-6)throw new IllegalArgumentException("Original hoist rope cannot vanish");return new Quaternionf().rotationTo(new Vector3f(0,1,0),new Vector3f((float)(delta.x/length),(float)(delta.y/length),(float)(delta.z/length)));}
    public static RigidTransform originalHoistRopeFrameR63(Vec3 first,Vec3 last)
    {return RigidTransform.of(first,originalHoistRopeRotationR63(first,last));}
    public record Pose(RigidTransform machine,RigidTransform grip,Vec3 mount,Vec3 yoke,float released)
    {public Pose{if(released<0||released>1||!Float.isFinite(released))throw new IllegalArgumentException("Actual jaw channel required");}}
    public static Pose evaluate(RigidTransform machine,double bottom,RigidTransform actualPlug,boolean coupled,Vec3 referenceWorld,Quaternionf referenceRotation,Vec3 suppliedMount)
    {
        Vec3 lower=new Vec3(0,bottom,0);var stowed=new Quaternionf().rotationX((float)-Math.PI/2);var rotation=new Quaternionf(stowed);var anchor=lower;boolean hasReference=referenceWorld!=null;
        if(actualPlug!=null){var local=NervMachineFrameR52.worldToLocal(machine.translation(),machine.rotation(),actualPlug.transformPoint(EntryPlugKinematics.CRANE_ATTACHMENT_P),actualPlug.rotation());anchor=local.translation();rotation=local.rotation();}
        else if(hasReference){var local=NervMachineFrameR52.worldToLocal(machine.translation(),machine.rotation(),referenceWorld,referenceRotation);anchor=local.translation();rotation=local.rotation();}
        float released=1;if(coupled){if(actualPlug==null)throw new IllegalArgumentException("Actual coupled capsule pose required");lower=anchor;released=0;}
        else if(actualPlug!=null||hasReference)
        {
            double travel=Math.max(1,-2-anchor.y),linear=Math.max(0,Math.min(1,(lower.y-anchor.y)/travel)),rise=travel*smooth((float)linear);
            var forward=rotation.transform(new Vector3f(0,0,1));var axis=new Vec3(forward.x,forward.y,forward.z);double axial=Math.min(rise,2*Math.max(.25,axis.y));lower=anchor.add(axis.scale(axial/Math.max(.25,axis.y))).add(0,rise-axial,0);
            released=(float)Math.max(0,Math.min(1,rise/.65));rotation.slerp(stowed,smooth((float)((rise-2)/Math.max(1,travel-2))));
        }
        Vec3 mount=lower;if(suppliedMount!=null){var p=rotation.transform(new Vector3f((float)suppliedMount.x,(float)suppliedMount.y,(float)suppliedMount.z));mount=lower.add(p.x,p.y,p.z);}
        Vec3 yoke=suppliedMount==null?lower.add(0,1.6,0):mount.add(0,.45,0);return new Pose(machine,RigidTransform.of(lower,rotation),mount,yoke,released);
    }
    public static float smooth(float x){x=Math.max(0,Math.min(1,x));return x*x*x*(x*(x*6-15)+10);}
    private NervCranePoseR52(){}
}
