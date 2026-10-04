package com.projectseele.physics;

import com.projectseele.entity.EvaBodyPose;
import net.minecraft.util.Mth;
import org.joml.Matrix3f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** A knee/elbow flexes about its measured axis; the bind-pose bow is not that axis. */
public final class AnatomicalLimbConstraints
{
    /** A joint-centre compensation is derived from rotation, not an independent
     * animation channel. Interpolating the two separately opens the hinge. */
    public static void restoreAuthoredJointCentres(EvaBodyPose.Sample pose,CombatBodyProfiles.Profile profile)
    {
        if(profile==null)return;
        for(var element:profile.definition().getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();String name=row.get("name").getAsString();
            if(!row.has("hinge")||!(name.startsWith("shin_")||name.startsWith("forearm_"))
                    ||!pose.rig.containsKey(name))continue;
            var m=row.getAsJsonArray("joint");
            Vector3f joint=new Vector3f(m.get(3).getAsFloat(),m.get(7).getAsFloat(),m.get(11).getAsFloat())
                    .div(CombatBodyProfiles.MODEL_TO_PHYSICS);
            Vector3f offset=joint.sub(pose.rig.get(name).pivot());
            pose.positions.put(name,AuthoredJointCentreR45.translation(offset,pose.rotations.get(name)));
        }
        pose.dirty();
    }

    /** Interpolate low-pose contact intent in body space. A local-only SLERP
     * can swing a knee through the floor between two valid captured poses. */
    public static void blendAuthoredContacts(EvaBodyPose.Sample pose,EvaBodyPose.Sample from,
                                             EvaBodyPose.Sample to,float amount,CombatBodyProfiles.Profile profile)
    {
        if(profile==null||amount<=0||amount>=1)return;
        restoreAuthoredJointCentres(pose,profile);
        for(var element:profile.definition().getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();String lower=row.get("name").getAsString();
            if(!row.has("hinge")||!(lower.startsWith("shin_")||lower.startsWith("forearm_")))continue;
            String upper=row.get("parent").getAsString();
            String end=(lower.startsWith("shin_")?"foot_":"hand_")+lower.charAt(lower.length()-1);
            if(!pose.rig.containsKey(end))continue;
            var m=row.getAsJsonArray("joint");
            Vector3f joint=new Vector3f(m.get(3).getAsFloat(),m.get(7).getAsFloat(),m.get(11).getAsFloat())
                    .div(CombatBodyProfiles.MODEL_TO_PHYSICS);
            Vector3f target=point(from,end).lerp(point(to,end),amount);
            Vector3f pole=from.matrix(upper).transformPosition(new Vector3f(joint))
                    .lerp(to.matrix(upper).transformPosition(new Vector3f(joint)),amount);
            Quaternionf orientation=from.matrix(end).getUnnormalizedRotation(new Quaternionf()).normalize()
                    .slerp(to.matrix(end).getUnnormalizedRotation(new Quaternionf()).normalize(),amount);
            var upperMatrix=pose.matrix(upper);
            Vector3f origin=point(pose,upper),middle=upperMatrix.transformPosition(new Vector3f(joint));
            Vector3f currentEnd=point(pose,end);
            Quaternionf upperWorld=upperMatrix.getUnnormalizedRotation(new Quaternionf()).normalize();
            Quaternionf lowerWorld=pose.matrix(lower).getUnnormalizedRotation(new Quaternionf()).normalize();
            Vector3f axis=new Vector3f(m.get(2).getAsFloat(),m.get(6).getAsFloat(),m.get(10).getAsFloat()).normalize();
            Vector3f fallback=upperWorld.transform(axis).cross(new Vector3f(currentEnd).sub(origin));
            var solved=AuthoredTwoBoneIKR45.solveWithPole(origin,middle,currentEnd,target,pole,fallback);
            if(solved==null)continue;
            upperWorld=solved.upperSwing().mul(upperWorld);
            lowerWorld=solved.lowerSwing().mul(lowerWorld);
            pose.rotations.put(upper,parent(pose,upper).invert().mul(upperWorld));pose.dirty();
            Quaternionf localLower=parent(pose,lower).invert().mul(lowerWorld);
            pose.rotations.put(lower,localLower);
            pose.positions.put(lower,AuthoredJointCentreR45.translation(
                    new Vector3f(joint).sub(pose.rig.get(lower).pivot()),localLower));pose.dirty();
            pose.rotations.put(end,parent(pose,end).invert().mul(orientation));pose.dirty();
        }
    }

    /** Captured support already owns the bend plane and local knee twist. */
    public static void reachAuthoredFoot(EvaBodyPose.Sample pose,CombatBodyProfiles.Profile profile,
                                         String side,Vector3f target,Quaternionf orientation)
    {
        if(profile==null)return;
        for(var element:profile.definition().getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();String lower="shin_"+side;
            if(!row.get("name").getAsString().equals(lower))continue;
            String upper="leg_"+side,end="foot_"+side;
            var m=row.getAsJsonArray("joint");
            Vector3f joint=new Vector3f(m.get(3).getAsFloat(),m.get(7).getAsFloat(),m.get(11).getAsFloat())
                    .div(CombatBodyProfiles.MODEL_TO_PHYSICS);
            var upperMatrix=pose.matrix(upper);
            Vector3f origin=point(pose,upper),middle=upperMatrix.transformPosition(new Vector3f(joint));
            Vector3f currentEnd=point(pose,end);
            Quaternionf currentOrientation=pose.matrix(end).getUnnormalizedRotation(new Quaternionf()).normalize();
            if(currentEnd.distanceSquared(target)<1e-10F&&Math.abs(currentOrientation.dot(orientation))>1-1e-7F)return;
            Quaternionf upperWorld=upperMatrix.getUnnormalizedRotation(new Quaternionf()).normalize();
            Quaternionf lowerWorld=pose.matrix(lower).getUnnormalizedRotation(new Quaternionf()).normalize();
            Vector3f axis=new Vector3f(m.get(2).getAsFloat(),m.get(6).getAsFloat(),m.get(10).getAsFloat()).normalize();
            Vector3f fallback=upperWorld.transform(axis).cross(new Vector3f(currentEnd).sub(origin));
            var solved=AuthoredTwoBoneIKR45.solve(origin,middle,currentEnd,target,fallback);
            if(solved==null)return;
            upperWorld=solved.upperSwing().mul(upperWorld);
            lowerWorld=solved.lowerSwing().mul(lowerWorld);
            pose.rotations.put(upper,parent(pose,upper).invert().mul(upperWorld));pose.dirty();
            Quaternionf localLower=parent(pose,lower).invert().mul(lowerWorld);
            pose.rotations.put(lower,localLower);
            Vector3f offset=new Vector3f(joint).sub(pose.rig.get(lower).pivot());
            pose.positions.put(lower,new Vector3f(offset).sub(localLower.transform(new Vector3f(offset))));pose.dirty();
            pose.rotations.put(end,parent(pose,end).invert().mul(orientation));pose.dirty();
            return;
        }
    }

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
    public static Vector3f elbowJoint(CombatBodyProfiles.Profile profile,String side,Vector3f fallback)
    {
        if(profile!=null)for(var element:profile.definition().getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();if(!row.get("name").getAsString().equals("forearm_"+side))continue;
            var m=row.getAsJsonArray("joint");return new Vector3f(m.get(3).getAsFloat(),m.get(7).getAsFloat(),m.get(11).getAsFloat()).div(CombatBodyProfiles.MODEL_TO_PHYSICS);
        }
        return new Vector3f(fallback);
    }
    /** Solve the real two-link arm for a tip extending along its forearm. */
    public static void reachForearmTip(EvaBodyPose.Sample pose,CombatBodyProfiles.Profile profile,String side,Vector3f target,float extension)
    {
        if(profile==null)return;
        for(var element:profile.definition().getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();if(!row.get("name").getAsString().equals("forearm_"+side))continue;var m=row.getAsJsonArray("joint");
            var joint=new Vector3f(m.get(3).getAsFloat(),m.get(7).getAsFloat(),m.get(11).getAsFloat()).div(CombatBodyProfiles.MODEL_TO_PHYSICS);
            var axis=new Vector3f(m.get(2).getAsFloat(),m.get(6).getAsFloat(),m.get(10).getAsFloat()).normalize();
            var hand=pose.rig.get("hand_"+side).pivot();var tip=new Vector3f(hand).add(new Vector3f(hand).sub(joint).normalize().mul(extension));
            solve(pose,"arm_"+side,"forearm_"+side,"hand_"+side,joint,axis,row.getAsJsonArray("hinge").get(1).getAsFloat(),target,tip);return;
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
    {solve(p,upper,lower,end,joint,axis,maximum,goal,null);}
    private static void solve(EvaBodyPose.Sample p,String upper,String lower,String end,Vector3f joint,Vector3f axis,float maximum,Vector3f goal,Vector3f extendedEnd)
    {
        Vector3f origin=point(p,upper),target=goal==null?point(p,end):new Vector3f(goal),oldJoint=p.matrix(upper).transformPosition(new Vector3f(joint));
        Quaternionf endOrientation=p.matrix(end).getUnnormalizedRotation(new Quaternionf()).normalize();
        Vector3f u=new Vector3f(joint).sub(p.rig.get(upper).pivot()),v=new Vector3f(extendedEnd==null?p.rig.get(end).pivot():extendedEnd).sub(joint);
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
        if(lower.startsWith("shin_")||goal==null)
        {
            // An almost-straight limb cannot define a stable pole from its
            // joint position. During normalization preserve the authored twist
            // for elbows too; only swing the complete anatomical hinge reach.
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
