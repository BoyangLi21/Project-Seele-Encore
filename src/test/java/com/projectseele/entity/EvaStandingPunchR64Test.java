package com.projectseele.entity;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** A captured forward offset or a recovering row cannot move the locomotion pelvis and soles. */
public final class EvaStandingPunchR64Test
{
    public static void main(String[] args)
    {
        Map<String,EvaBodyPose.Bone> rig=new LinkedHashMap<>();
        add(rig,"root",null,0,0,0);
        add(rig,"torso_lower","root",0,7,0);
        add(rig,"torso_upper","torso_lower",0,9,0);
        add(rig,"arm_l","torso_upper",2,9,0);
        add(rig,"hand_l","arm_l",2,5,0);
        for(String side:List.of("l","r"))
        {
            float x=side.equals("l")?1:-1;
            add(rig,"leg_"+side,"torso_lower",x,7,0);
            add(rig,"foot_"+side,"leg_"+side,x,0,0);
        }
        var support=new EvaBodyPose.Sample(rig);
        support.rotations.get("torso_lower").rotationZ(.08F);
        support.contactGoals.put("foot_l",new Vector3f(1,0,0));
        for(int frame=0;frame<=120;frame++)
        {
            float phase=frame/120F;
            support.positions.get("root").set(phase,0,0);
            support.dirty();
            var strike=new EvaBodyPose.Sample(rig);
            strike.positions.get("root").z=-3+.8F*(float)Math.sin(phase*Math.PI);
            strike.rotations.get("torso_lower").rotationY(.3F);
            strike.rotations.get("torso_upper").rotationY(-.8F*phase);
            strike.rotations.get("arm_l").rotationX(phase);
            strike.rotations.get("leg_l").rotationX(-.5F*phase);
            // Both entry and recovery fades mutate their first sample.
            strike=EvaBodyPose.blend(EvaBodyPose.copy(support),strike,(float)Math.sin(phase*Math.PI));
            var handBefore=orientation(strike,"hand_l");
            var armVector=point(strike,"hand_l").sub(point(strike,"torso_upper"));
            EvaBodyPose.strikeOverSupportR64(strike,support);
            for(String n:List.of("root","torso_lower","leg_l","leg_r","foot_l","foot_r"))
                if(point(strike,n).distance(point(support,n))>1e-5)throw new AssertionError(n+" left support");
            if(Math.abs(handBefore.dot(orientation(strike,"hand_l")))<.99999F
                    ||armVector.distance(point(strike,"hand_l").sub(point(strike,"torso_upper")))>1e-5)
                throw new AssertionError("Captured fist and chest lost their alignment");
            if(!strike.contactGoals.equals(support.contactGoals)||support.positions.get("root").z!=0)
                throw new AssertionError("Support changed during the strike");
        }
    }

    private static void add(Map<String,EvaBodyPose.Bone> rig,String name,String parent,float x,float y,float z)
    {rig.put(name,new EvaBodyPose.Bone(name,parent,new Vector3f(x,y,z),new Quaternionf()));}

    private static Vector3f point(EvaBodyPose.Sample pose,String name)
    {return pose.matrix(name).transformPosition(new Vector3f(pose.rig.get(name).pivot()));}

    private static Quaternionf orientation(EvaBodyPose.Sample pose,String name)
    {return pose.matrix(name).getUnnormalizedRotation(new Quaternionf()).normalize();}
}
