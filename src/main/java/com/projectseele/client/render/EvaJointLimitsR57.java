package com.projectseele.client.render;

import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;

/**
 * Human ranges for the spine, neck, head and hips, applied to the final pose.
 * <p>
 * The EVA is a human body: no source clip, retarget or blend may fold the
 * chest over, wring the waist or swing a thigh behind the hips. The local
 * rotation is split into twist about the bone (its Y axis) and the swing that
 * tilts it. Twist is clamped to its range; swing keeps its direction and is
 * shortened to an ellipse through the bend and side limits. A joint inside
 * its range is unchanged, and the limit is reached continuously. Angles are
 * in this rig's local frame: negative X bends the chest forward and swings a
 * thigh back.
 */
final class EvaJointLimitsR57
{
    private record Range(float flexMin,float flexMax,float side,float twist) {}
    private static final String[] BONES={"torso_upper","neck","head","leg_l","leg_r"};
    private static final Range[] RANGES={
            new Range(-45,40,35,45),
            new Range(-45,45,35,60),
            new Range(-40,40,30,45),
            new Range(-50,110,50,45),
            new Range(-50,110,50,45)};
    private static final boolean ENABLED=Boolean.parseBoolean(System.getProperty("projectseele.jointLimitsR57","true"));

    static void apply(BakedGeoModel model)
    {
        if(!ENABLED)return;
        for(int i=0;i<BONES.length;i++)
        {
            GeoBone bone=model.getBone(BONES[i]).orElse(null);
            if(bone!=null)limit(bone,RANGES[i]);
        }
    }

    private static void limit(GeoBone bone,Range range)
    {
        var q=new Quaternionf().rotationZYX(bone.getRotZ(),bone.getRotY(),bone.getRotX());
        if(q.w<0)q.set(-q.x,-q.y,-q.z,-q.w);
        float norm=(float)Math.hypot(q.y,q.w);
        var twist=norm<1e-6F?new Quaternionf():new Quaternionf(0,q.y/norm,0,q.w/norm);
        var swing=new Quaternionf(q).mul(new Quaternionf(twist).invert());
        if(swing.w<0)swing.set(-swing.x,-swing.y,-swing.z,-swing.w);
        float twistAngle=(float)(2*Math.atan2(twist.y,twist.w));
        float twistLimit=(float)Math.toRadians(range.twist());
        boolean changed=false;
        if(Math.abs(twistAngle)>twistLimit)
        {
            twist.rotationY(Math.copySign(twistLimit,twistAngle));changed=true;
        }
        // Swing as axis and angle; the axis lies in the bone's X-Z plane.
        float sine=(float)Math.sqrt(swing.x*swing.x+swing.y*swing.y+swing.z*swing.z);
        if(sine>1e-6F)
        {
            float angle=(float)(2*Math.atan2(sine,swing.w));
            var axis=new Vector3f(swing.x,swing.y,swing.z).div(sine);
            float bend=(float)Math.toRadians(axis.x>=0?range.flexMax():-range.flexMin()),side=(float)Math.toRadians(range.side());
            float limit=(float)(1/Math.sqrt(axis.x*axis.x/(bend*bend)+axis.z*axis.z/(side*side)+1e-12));
            if(angle>limit){swing.fromAxisAngleRad(axis,limit);changed=true;}
        }
        if(changed)EvaRigTransforms.rotate(bone,new Quaternionf(swing).mul(twist));
    }

    private EvaJointLimitsR57(){}
}
