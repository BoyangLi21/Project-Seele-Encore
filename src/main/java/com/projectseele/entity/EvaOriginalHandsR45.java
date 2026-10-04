package com.projectseele.entity;

import net.minecraft.util.Mth;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Original artist surfaces use their measured bind frames, not prism adapters. */
public final class EvaOriginalHandsR45
{
    public static boolean enabled(EvaUnit01Entity eva)
    {
        return Boolean.getBoolean("projectseele.originalHandsR45")&&!eva.isExperimentalUnit()
                &&eva.getUnitVariant()==Integer.getInteger("projectseele.originalHandsRigR45",1);
    }
    public static void apply(EvaUnit01Entity eva,EvaBodyPose.Sample pose)
    {
        if(!enabled(eva))return;
        for(String side:new String[]{"l","r"})
        {
            for(String digit:new String[]{"index","middle","ring","little"})
            {
                String axis="finger_"+digit+"_axis_"+side;
                if(pose.rig.containsKey(axis))
                {
                    pose.rotations.put(axis,new Quaternionf(pose.rig.get(axis).bindRotation()));
                    pose.positions.put(axis,new Vector3f());
                }
            }
            String thumb="finger_thumb_"+side,tip="finger_thumb_tip_"+side,middle="finger_middle_"+side;
            if(!pose.rig.containsKey(thumb)||!pose.rig.containsKey(tip)||!pose.rig.containsKey(middle))continue;
            var curl=pose.rotations.get(middle);
            float closure=Mth.clamp((Math.abs(2*(float)Math.atan2(curl.z,curl.w))*Mth.RAD_TO_DEG-14)/58,0,1);
            var root=pose.rig.get(thumb).pivot();
            var tangent=new Vector3f(pose.rig.get(tip).pivot()).sub(root).normalize();
            var target=new Vector3f(pose.rig.get("finger_index_"+side).pivot()).sub(root).normalize();
            var opposed=new Quaternionf().rotationTo(tangent,target);
            pose.rotations.put(thumb,new Quaternionf().slerp(opposed,closure));
            pose.rotations.put(tip,new Quaternionf());
            pose.positions.put(thumb,new Vector3f());pose.positions.put(tip,new Vector3f());
        }
        pose.dirty();
    }
    private EvaOriginalHandsR45(){}
}
