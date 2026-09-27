package com.projectseele.entity;

import net.minecraft.util.Mth;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import org.joml.Matrix3f;

/** Locomotion uses the current anatomical finger hinges, on both hands. */
public final class EvaHandsR41
{
    public static void apply(EvaUnit01Entity eva, EvaBodyPose.Sample body, float partial)
    {
        if(!body.rig.containsKey("finger_index_axis_l")||!body.rig.containsKey("finger_index_axis_r"))return;
        float stance=eva.rifleStanceLevel(partial);
        boolean rifle=eva.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE;
        boolean weapon=eva.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS;
        int action=EvaCombatR31.action(eva);
        boolean grasp=action>=EvaCombatR31.REACH&&action<=EvaCombatR31.THROW;
        float low=Mth.clamp((stance-.5F)/1.5F,0,1);low=low*low*(3-2*low);
        float transitionSupport=stance>1&&stance<3?(float)Math.pow(Math.sin((stance-1)*Math.PI/2),2):0;
        for(String side:new String[]{"l","r"})
        {
            Vector3f along=longitudinal(body,side);
            Vector3f palmar=palmar(body,side,along);
            Quaternionf extended=new Quaternionf().setFromNormalized(new Matrix3f()
                    .setColumn(0,palmar).setColumn(1,new Vector3f(along).negate())
                    .setColumn(2,new Vector3f(palmar).cross(new Vector3f(along).negate())));
            float support=rifle&&side.equals("l")?transitionSupport:!weapon&&!grasp?low:0;
            for(String digit:new String[]{"index","middle","ring","little","thumb"})
            {
                String stem="finger_"+digit;
                String axis=stem+"_axis_"+side;
                if(body.rig.containsKey(axis))
                {
                    body.rotations.put(axis,new Quaternionf(body.rig.get(axis).bindRotation()));
                    body.positions.put(axis,new Vector3f());
                    if(!digit.equals("thumb"))
                    {
                        // The recovered TV wrist marker lies off the palm's
                        // longitudinal axis. Its middle-MCP vector describes
                        // an oblique diagonal, not finger extension.
                        body.rotations.put(axis,new Quaternionf(extended));
                    }
                    if(digit.equals("thumb"))
                    {
                        float opposition=(weapon||grasp?65:10)*(1-support);
                        body.rotations.get(axis).rotateZ(opposition*Mth.DEG_TO_RAD*(side.equals("r")?1:-1));
                    }
                }
                float[] curl=digit.equals("thumb")?(weapon||grasp?new float[]{28,42,0}:new float[]{6,12,0})
                        :grasp?new float[]{34,48,25}
                        :rifle&&side.equals("r")&&digit.equals("index")?new float[]{12,24,8}
                        :weapon?new float[]{57,84,54}:new float[]{10,14,7};
                for(int joint=0;joint<3;joint++)
                {
                    String name=stem+(joint==0?"":joint==1?"_tip":"_distal")+"_"+side;
                    if(!body.rig.containsKey(name))continue;
                    Quaternionf rotation=new Quaternionf();
                    if(digit.equals("thumb")&&!body.rig.containsKey(axis))
                    {
                        // The original thumb is one rigid skin segment. Its
                        // marker descendants must not create extra hinges.
                        if(joint==0)
                        {
                            Vector3f thumb=body.rig.get(name).pivot();
                            Vector3f tangent=new Vector3f(body.rig.get(stem+"_tip_"+side).pivot()).sub(thumb).normalize();
                            Vector3f target=new Vector3f(body.rig.get("finger_index_"+side).pivot())
                                    .fma(1.6F/16,palmar).fma(1.4F/16,along).sub(thumb).normalize();
                            Quaternionf opposed=new Quaternionf().rotationTo(tangent,target);
                            Quaternionf open=openThumb(body,side);
                            rotation=weapon||grasp?opposed.slerp(open,support):open.slerp(opposed,.08F*(1-support));
                        }
                    }
                    else rotation.rotationZ(curl[joint]*(1-support)*Mth.DEG_TO_RAD);
                    body.rotations.put(name,rotation);body.positions.put(name,new Vector3f());
                }
            }
        }
        body.dirty();
    }
    private static Quaternionf openThumb(EvaBodyPose.Sample body,String side)
    {
        Vector3f root=body.rig.get("finger_thumb_"+side).pivot();
        Vector3f tangent=new Vector3f(body.rig.get("finger_thumb_tip_"+side).pivot()).sub(root).normalize();
        Vector3f middle=body.rig.get("finger_middle_"+side).pivot();
        Vector3f along=longitudinal(body,side);
        Vector3f normal=palmar(body,side,along);
        Vector3f radial=new Vector3f(root).sub(middle);radial.fma(-radial.dot(along),along).fma(-radial.dot(normal),normal).normalize();
        // Extend the actual single rigid thumb in the palm plane, with radial
        // abduction. Its source zero was almost perpendicular to that plane.
        return new Quaternionf().rotationTo(tangent,along.add(radial).normalize());
    }
    private static Vector3f longitudinal(EvaBodyPose.Sample body,String side)
    {
        Vector3f width=new Vector3f(body.rig.get("finger_index_"+side).pivot()).sub(body.rig.get("finger_little_"+side).pivot()).normalize();
        Vector3f along=new Vector3f(body.rig.get("hand_"+side).pivot()).sub(body.rig.get("forearm_"+side).pivot());
        return along.fma(-along.dot(width),width).normalize();
    }
    private static Vector3f palmar(EvaBodyPose.Sample body,String side,Vector3f along)
    {
        Vector3f width=new Vector3f(body.rig.get("finger_index_"+side).pivot()).sub(body.rig.get("finger_little_"+side).pivot()).normalize();
        Vector3f normal=width.cross(along).normalize();
        Vector3f flex=body.rig.get("finger_middle_axis_"+side).bindRotation().transform(new Vector3f(1,0,0));
        return normal.dot(flex)<0?normal.negate():normal;
    }
    private EvaHandsR41(){}
}
