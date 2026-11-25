package com.projectseele.entity;

import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Reach of a real wrist chain, including the palm-to-finger contact offset: an aerial strike's hand is kept within it. */
public final class CombatReachR31
{
    public static Vec3 clampContact(EvaUnit01Entity eva,String side,Vec3 contact)
    {return clampContact(eva,side,contact,1F);}

    /** The client must pass its render partial; server contacts pass 1. */
    public static Vec3 clampContact(EvaUnit01Entity eva,String side,Vec3 contact,float partial)
    {
        var body=posedBody(eva,partial);var upper=body.rig.get("arm_"+side);var hand=body.rig.get("hand_"+side);var middle=body.rig.get("finger_middle_"+side);
        if(upper==null||hand==null||middle==null)return contact;
        Vector3f elbow=elbow(body,side);double a=upper.pivot().distance(elbow)*EvaScale.RENDER_SCALE,b=hand.pivot().distance(elbow)*EvaScale.RENDER_SCALE;
        Vec3 shoulder=new Vec3(EvaRifleKinematics.world(eva,partial).mul(body.matrix("arm_"+side)).transformPosition(new Vector3f(upper.pivot())));
        double palm=middle.pivot().distance(hand.pivot())*.62*EvaScale.RENDER_SCALE;
        Vec3 wrist=contact.add(0,-palm,0),direction=wrist.subtract(shoulder);double distance=direction.length();
        if(distance<1e-8)direction=new Vec3(0,-1,0);else direction=direction.scale(1/distance);
        double low=Math.abs(a-b)+.75,high=a+b-.75;
        double wanted=Math.max(low,Math.min(high,distance));
        return shoulder.add(direction.scale(wanted)).add(0,palm,0);
    }

    private static EvaBodyPose.Sample posedBody(EvaUnit01Entity eva,float partial)
    {
        var body=EvaBodyPose.sample(eva,partial);int action=EvaCombatR31.action(eva);
        float age=EvaCombatR31.age(eva,partial),weight=action==EvaCombatR31.NONE?1:(float)CombatMotionR29.ease(age/6);
        if(action==EvaCombatR31.AIR_STRIKE)
        {
            weight*=1-(float)CombatMotionR29.ease((age-20)/7);
            offset(body,"torso_upper",-.12F*weight,-.30F*(float)CombatMotionR29.ease((age-4)/7)*weight);
        }
        body.dirty();return body;
    }

    private static void offset(EvaBodyPose.Sample body,String name,float x,float y)
    {
        var q=body.rotations.get(name);if(q==null)return;var angle=EvaShutdownR30.euler(q);
        body.rotations.put(name,new Quaternionf().rotationZYX(angle.z,angle.y+y,angle.x+x));
    }

    private static Vector3f elbow(EvaBodyPose.Sample body,String side)
    {var marker=body.rig.get("r30_elbow_socket_"+side);return marker==null?new Vector3f(side.equals("l")?-23.489652F:23.489652F,123.435069F,7.737214F).div(16):new Vector3f(marker.pivot());}
    private CombatReachR31() {}
}
