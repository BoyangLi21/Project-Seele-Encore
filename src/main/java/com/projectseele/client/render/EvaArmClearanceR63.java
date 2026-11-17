package com.projectseele.client.render;

import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.util.Mth;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;

/**
 * A swinging hand passes beside its thigh, not through it.
 * <p>
 * The walking and running clips swing each hand in close past the hip. At a run the hand went 1.7
 * blocks into the thigh and the forearm 0.8, once a stride, on all three units. Where the hand
 * comes nearer the thigh's axis than the two are thick, the upper arm is turned outward at the
 * shoulder by the angle that takes the hand clear. Away from the thigh the clip is untouched.
 * <p>
 * Standing still counts too: Unit-02 carrying its sword stood with the free hand 1.8 blocks inside
 * the thigh. The bare-handed stance hangs its hands clear of the legs and is not changed.
 */
final class EvaArmClearanceR63
{
    /** Half the thickness of a thigh and of a hand (blocks). */
    private static final float THIGH=Float.parseFloat(System.getProperty("projectseele.armClearThighR63","4.2")),HAND=1.3F;
    /** The largest turn (radians: twelve degrees). */
    private static final float MOST=.21F;

    static void apply(EvaUnit01Entity eva,BakedGeoModel model,Matrix4f root,float partial)
    {
        // The rifle's hands are on the gun; a strike, a fall or a low stance sets its arms itself.
        if(root==null||eva.isExperimentalUnit()||eva.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE||eva.hasLiveActionForRender(partial)
                ||eva.isFirstBattleActive()||eva.isNervLogisticsLocked()||eva.isVisuallyAirborneForRender()
                ||eva.rifleStanceLevel(partial)>.5F)return;
        var left=model.getBone("arm_l").orElse(null);var right=model.getBone("arm_r").orElse(null);
        if(left==null||right==null)return;
        float yaw=Mth.rotLerp(partial,eva.yBodyRotO,eva.yBodyRot)*Mth.DEG_TO_RAD;
        var forward=new Vector3f(-Mth.sin(yaw),0,Mth.cos(yaw));
        var shoulderL=EvaRigTransforms.point(left,EvaRigTransforms.pivot(left),root);
        var shoulderR=EvaRigTransforms.point(right,EvaRigTransforms.pivot(right),root);
        for(String side:new String[]{"l","r"})
        {
            var arm=side.equals("l")?left:right;
            var hand=model.getBone("hand_"+side).orElse(null);var finger=model.getBone("finger_middle_"+side).orElse(null);
            var leg=model.getBone("leg_"+side).orElse(null);var shin=model.getBone("shin_"+side).orElse(null);
            if(hand==null||leg==null||shin==null)continue;
            var shoulder=side.equals("l")?shoulderL:shoulderR;
            // Outward: from the other shoulder to this one, level.
            var out=new Vector3f(shoulder).sub(side.equals("l")?shoulderR:shoulderL);out.y=0;
            if(out.lengthSquared()<1e-6F)continue;
            out.normalize();
            var palm=EvaRigTransforms.point(hand,EvaRigTransforms.pivot(hand),root);
            if(finger!=null)palm.lerp(EvaRigTransforms.point(finger,EvaRigTransforms.pivot(finger),root),.5F);
            var hip=EvaRigTransforms.point(leg,EvaRigTransforms.pivot(leg),root);
            var knee=EvaRigTransforms.point(leg,EvaRigTransforms.knee(shin),root);
            // The nearest point of the thigh's axis.
            var axis=new Vector3f(knee).sub(hip);
            float along=Mth.clamp(new Vector3f(palm).sub(hip).dot(axis)/Math.max(1e-6F,axis.lengthSquared()),0,1);
            float overlap=THIGH+HAND-new Vector3f(hip).fma(along,axis).distance(palm);
            if(overlap<=0)continue;
            // Turning the arm about the heading through the shoulder carries the hand this far outward per radian.
            float lever=new Vector3f(forward).cross(new Vector3f(palm).sub(shoulder)).dot(out);
            if(Math.abs(lever)<1F)continue;
            float angle=Mth.clamp(overlap/lever,-MOST,MOST);
            var world=EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(arm)));
            var turned=new Quaternionf().rotationAxis(angle,forward.x,forward.y,forward.z).mul(world);
            EvaRigTransforms.rotate(arm,EvaRigTransforms.rotation(EvaRigTransforms.parent(arm,root)).invert().mul(turned));
        }
    }

    private EvaArmClearanceR63() {}
}
