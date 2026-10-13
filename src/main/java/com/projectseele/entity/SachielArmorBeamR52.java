package com.projectseele.entity;

import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;
import org.joml.Quaternionf;

/** Real original skull surface, transformed by the same body/head pose submitted by the renderer. */
public final class SachielArmorBeamR52
{
    public static final int CHARGE=32,FIRE_END=40,DURATION=52;
    // Original selected Sachiel head mesh's centre-front vertex, model pixels.
    private static final Vector3f FACE=new Vector3f(0,179.8075556F,-18.1404394F).div(16);
    public static float weight(float age)
    {return age<0?0:EvaDorsalMechanism.smooth(age/18)*(1-EvaDorsalMechanism.smooth((age-FIRE_END)/(DURATION-FIRE_END)));}
    public static void pose(SachielEntity actor,EvaBodyPose.Sample pose,float partial)
    {
        if(!actor.isArmorBeamR52())return;
        pose.rotations.get("head").rotateX(-.95F*weight(actor.armorBeamAgeR52(partial)));pose.dirty();
    }
    public static Vec3 origin(SachielEntity actor,float partial)
    {
        return origin(actor,SachielBodyPoseR35.sample(actor,partial),partial);
    }
    public static Vec3 origin(SachielEntity actor,EvaBodyPose.Sample pose,float partial)
    {
        // Exact original four skin influences, with the renderer's first-slot DQS hemisphere rule.
        String[] bones={"torso_lower","torso_upper","neck","head"};float[] weights={.0002686F,.0070894F,.1922536F,.8003883F};
        var q=new Quaternionf(0,0,0,0);var d=new Quaternionf(0,0,0,0);Quaternionf reference=null;
        for(int i=0;i<4;i++)
        {
            var matrix=pose.matrix(bones[i]);var real=matrix.getUnnormalizedRotation(new Quaternionf()).normalize();var at=matrix.getTranslation(new Vector3f());
            var dual=new Quaternionf(at.x,at.y,at.z,0).mul(real).mul(.5F);if(reference==null)reference=real;
            float w=reference.dot(real)<0?-weights[i]:weights[i];q.x+=w*real.x;q.y+=w*real.y;q.z+=w*real.z;q.w+=w*real.w;d.x+=w*dual.x;d.y+=w*dual.y;d.z+=w*dual.z;d.w+=w*dual.w;
        }
        float length=(float)Math.sqrt(q.lengthSquared());q.mul(1/length);d.mul(1/length);float orthogonal=q.dot(d);d.x-=q.x*orthogonal;d.y-=q.y*orthogonal;d.z-=q.z*orthogonal;d.w-=q.w*orthogonal;
        var translation=d.mul(new Quaternionf(q).conjugate());var point=q.transform(new Vector3f(FACE)).add(2*translation.x,2*translation.y,2*translation.z);
        return new Vec3(SachielStrike.root(actor,partial).transformPosition(point));
    }
    private SachielArmorBeamR52(){}
}
