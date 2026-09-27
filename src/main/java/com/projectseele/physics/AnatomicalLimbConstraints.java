package com.projectseele.physics;

import com.projectseele.entity.EvaBodyPose;
import net.minecraft.util.Mth;
import org.joml.Matrix3f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** A knee/elbow flexes about its measured axis; the bind-pose bow is not that axis. */
public final class AnatomicalLimbConstraints
{
    public static void apply(EvaBodyPose.Sample pose,CombatBodyProfiles.Profile profile)
    {
        for(var element:profile.definition().getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();if(!row.has("hinge"))continue;String lower=row.get("name").getAsString(),upper=row.get("parent").getAsString();
            String end=(lower.startsWith("shin_")?"foot_":"hand_")+lower.charAt(lower.length()-1);if(!pose.rig.containsKey(end))continue;
            var matrix=row.getAsJsonArray("joint");Vector3f joint=new Vector3f(matrix.get(3).getAsFloat(),matrix.get(7).getAsFloat(),matrix.get(11).getAsFloat()).div(CombatBodyProfiles.MODEL_TO_PHYSICS);
            Vector3f axis=new Vector3f(matrix.get(2).getAsFloat(),matrix.get(6).getAsFloat(),matrix.get(10).getAsFloat()).normalize();
            solve(pose,upper,lower,end,joint,axis,row.getAsJsonArray("hinge").get(1).getAsFloat(),null);
        }
    }
    public static void reachHand(EvaBodyPose.Sample pose,CombatBodyProfiles.Profile profile,String side,Vector3f target)
    {
        for(var element:profile.definition().getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();if(!row.get("name").getAsString().equals("forearm_"+side))continue;var m=row.getAsJsonArray("joint");
            var joint=new Vector3f(m.get(3).getAsFloat(),m.get(7).getAsFloat(),m.get(11).getAsFloat()).div(CombatBodyProfiles.MODEL_TO_PHYSICS);var axis=new Vector3f(m.get(2).getAsFloat(),m.get(6).getAsFloat(),m.get(10).getAsFloat()).normalize();
            solve(pose,"arm_"+side,"forearm_"+side,"hand_"+side,joint,axis,row.getAsJsonArray("hinge").get(1).getAsFloat(),target);return;
        }
    }
    public static void reachFoot(EvaBodyPose.Sample pose,CombatBodyProfiles.Profile profile,String side,Vector3f target,Quaternionf orientation)
    {
        if(profile==null)
        {
            String marker="r30_knee_socket_"+side;
            Vector3f joint=pose.rig.containsKey(marker)?new Vector3f(pose.rig.get(marker).pivot())
                    :new Vector3f(pose.rig.get("shin_"+side).pivot()).add(0,11.4F/16,0);
            solve(pose,"leg_"+side,"shin_"+side,"foot_"+side,joint,new Vector3f(-1,0,0),2.62F,target);
            pose.rotations.put("foot_"+side,parent(pose,"foot_"+side).invert().mul(orientation));pose.dirty();return;
        }
        for(var element:profile.definition().getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();if(!row.get("name").getAsString().equals("shin_"+side))continue;var m=row.getAsJsonArray("joint");
            var joint=new Vector3f(m.get(3).getAsFloat(),m.get(7).getAsFloat(),m.get(11).getAsFloat()).div(CombatBodyProfiles.MODEL_TO_PHYSICS);
            var axis=new Vector3f(m.get(2).getAsFloat(),m.get(6).getAsFloat(),m.get(10).getAsFloat()).normalize();
            solve(pose,"leg_"+side,"shin_"+side,"foot_"+side,joint,axis,row.getAsJsonArray("hinge").get(1).getAsFloat(),target);
            pose.rotations.put("foot_"+side,parent(pose,"foot_"+side).invert().mul(orientation));pose.dirty();return;
        }
    }
    private static Vector3f point(EvaBodyPose.Sample p,String name){return p.matrix(name).transformPosition(new Vector3f(p.rig.get(name).pivot()));}
    private static Quaternionf parent(EvaBodyPose.Sample p,String name){String parent=p.rig.get(name).parent();return parent==null?new Quaternionf():p.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize();}
    private static Matrix3f frame(Vector3f first,Vector3f second)
    {
        Vector3f y=new Vector3f(first).normalize(),x=new Vector3f(first).cross(second);
        if(x.lengthSquared()<1e-10F)x.set(1,0,0).fma(-y.x,y);x.normalize();Vector3f z=new Vector3f(x).cross(y);
        return new Matrix3f().setColumn(0,x).setColumn(1,y).setColumn(2,z);
    }
    private static void solve(EvaBodyPose.Sample p,String upper,String lower,String end,Vector3f joint,Vector3f axis,float maximum,Vector3f goal)
    {
        Vector3f origin=point(p,upper),target=goal==null?point(p,end):new Vector3f(goal),oldJoint=p.matrix(upper).transformPosition(new Vector3f(joint));
        Quaternionf endOrientation=p.matrix(end).getUnnormalizedRotation(new Quaternionf()).normalize();
        Vector3f u=new Vector3f(joint).sub(p.rig.get(upper).pivot()),v=new Vector3f(p.rig.get(end).pivot()).sub(joint);
        float la=u.length(),lb=v.length();Vector3f parallel=new Vector3f(axis).mul(axis.dot(v)),perpendicular=new Vector3f(v).sub(parallel);
        float a=u.dot(perpendicular),b=u.dot(new Vector3f(axis).cross(v)),c=u.dot(parallel),amplitude=(float)Math.hypot(a,b),neutral=(float)Math.atan2(b,a);
        float longest=(float)Math.sqrt(la*la+lb*lb+2*(amplitude+c))*.9999F;
        float shortest=(float)Math.sqrt(Math.max(0,la*la+lb*lb+2*(a*Math.cos(maximum)+b*Math.sin(maximum)+c)))+.0001F;
        Vector3f direction=new Vector3f(target).sub(origin);if(direction.lengthSquared()<1e-9F)return;float length=Mth.clamp(direction.length(),shortest,longest);direction.normalize();
        target.set(origin).fma(length,direction);float angle=neutral+(float)Math.acos(Mth.clamp(((length*length-la*la-lb*lb)/2-c)/Math.max(amplitude,1e-8F),-1,1));
        Quaternionf hinge=new Quaternionf().rotationAxis(angle,axis);
        float along=(la*la-lb*lb+length*length)/(2*length);Vector3f bend=oldJoint.sub(origin);bend.fma(-bend.dot(direction),direction);
        if(bend.lengthSquared()<1e-8F)bend.set(0,0,-1).fma(direction.z,direction);bend.normalize();
        Vector3f middle=new Vector3f(origin).fma(along,direction).fma((float)Math.sqrt(Math.max(0,la*la-along*along)),bend);
        Quaternionf upperWorld;
        if(lower.startsWith("shin_"))
        {
            // The bind leg bows sideways. Its almost-straight joint position
            // cannot define a knee pole: that turned tiny offsets into hip roll.
            // Preserve the authored twist, and swing only the complete hinge reach.
            Quaternionf authored=p.matrix(upper).getUnnormalizedRotation(new Quaternionf()).normalize();
            Vector3f reach=authored.transform(new Vector3f(u).add(hinge.transform(new Vector3f(v)))).normalize();
            upperWorld=new Quaternionf().rotationTo(reach,direction).mul(authored).normalize();
        }
        else
        {
            Matrix3f world=frame(new Vector3f(middle).sub(origin),new Vector3f(target).sub(middle)).mul(frame(u,hinge.transform(new Vector3f(v))).transpose());
            upperWorld=new Quaternionf().setFromNormalized(world);
        }
        p.rotations.put(upper,parent(p,upper).invert().mul(upperWorld));p.rotations.put(lower,hinge);
        Vector3f offset=new Vector3f(joint).sub(p.rig.get(lower).pivot());p.positions.put(lower,new Vector3f(offset).sub(hinge.transform(offset)));p.dirty();
        p.rotations.put(end,parent(p,end).invert().mul(endOrientation));p.dirty();
    }
    private AnatomicalLimbConstraints(){}
}
