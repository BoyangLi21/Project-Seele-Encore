package com.projectseele.client.render;

import com.projectseele.entity.*;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;

/** Opt-in cannon blocking. Palm surface fit and native visual review remain open. */
final class EvaCannonContactRigR45
{
    static void apply(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f renderedRoot)
    {
        if(!EvaCannonFrameR45.enabled(eva)||renderedRoot==null||!EvaHandSurfaceR45.applies(eva)
                ||!eva.isPoweredOn()||eva.isNervLogisticsLocked()||eva.isFirstBattleActive()
                ||eva.isBerserk()||eva.getActivationTicks()>0||EvaShutdownR30.displayed(eva)
                ||EvaAirTransportR31.active(eva)||com.projectseele.physics.CombatBodyDynamics.active(eva))return;
        var grips=EvaAnatomicalHandsR45.rig(eva.getUnitVariant()).grips();
        if(!grips.containsKey("l")||!grips.containsKey("r"))return;
        var body=EvaBodyPose.sample(eva,partial);
        var frame=EvaCannonFrameR45.sample(eva,partial,eva.getAimDirectionForPoseCapture(partial),
                body,EvaRifleKinematics.world(eva,partial));
        body=frame.body();
        for(String name:body.rig.keySet())
        {
            if(!(name.equals("root")||name.equals("aim_pitch")||name.startsWith("torso_")||name.startsWith("clavicle_")
                    ||name.startsWith("arm_")||name.startsWith("forearm_")||name.startsWith("wrist_")
                    ||name.startsWith("hand_")||name.startsWith("leg_")||name.startsWith("shin_")
                    ||name.startsWith("ankle_")||name.startsWith("foot_")||name.equals("neck")||name.equals("head")))continue;
            var bone=model.getBone(name).orElse(null);if(bone==null)continue;
            EvaRigTransforms.rotate(bone,body.rotations.get(name));var p=body.positions.get(name);
            bone.setPosX(-p.x*16);bone.setPosY(p.y*16);bone.setPosZ(p.z*16);
            bone.setScaleX(1);bone.setScaleY(1);bone.setScaleZ(1);
        }
        var right=frame.right().toVector3f();var forward=frame.forward().toVector3f();var up=frame.up().toVector3f();
        var dominant=EvaRifleGripR45.fitPalm(grips.getOrDefault("cannon_r",grips.get("r")),body.rig.get("hand_r").pivot(),
                new Vector3f(forward).fma(-.56F,up),new Vector3f(up).fma(.56F,forward),frame.rightPad());
        var support=EvaRifleGripR45.fitPalm(grips.getOrDefault("cannon_l",grips.get("l")),body.rig.get("hand_l").pivot(),right,forward,frame.leftPad());
        solve(model,"r",dominant,new Vector3f(right).add(0,-.7F,0),renderedRoot);
        solve(model,"l",support,new Vector3f(right).negate().add(0,-.7F,0),renderedRoot);
        absolute(model.getBone("cannon").orElseThrow(),frame.weaponToWorld(),renderedRoot);
        var head=model.getBone("head").orElseThrow();
        var gaze=new Quaternionf().setFromNormalized(new Matrix3f().setColumn(0,right)
                .setColumn(1,up).setColumn(2,new Vector3f(forward).negate()));
        EvaRigTransforms.rotate(head,EvaRigTransforms.rotation(EvaRigTransforms.parent(head,renderedRoot)).invert().mul(gaze));
    }

    private static void solve(BakedGeoModel model,String side,EvaRifleGripR45.Contact contact,
                               Vector3f pole,Matrix4f world)
    {
        EvaRigTransforms.solveArm(model.getBone("arm_"+side).orElseThrow(),model.getBone("forearm_"+side).orElseThrow(),
                model.getBone("wrist_"+side).orElseThrow(),model.getBone("hand_"+side).orElseThrow(),
                side,contact.wrist(),contact.rotation(),pole,world);
    }

    private static void absolute(GeoBone bone,Matrix4f desired,Matrix4f world)
    {
        var relative=EvaRigTransforms.parent(bone,world).invert().mul(desired);
        var pivot=EvaRigTransforms.pivot(bone);var offset=relative.transformPosition(new Vector3f(pivot)).sub(pivot);
        bone.setPosX(-offset.x*16);bone.setPosY(offset.y*16);bone.setPosZ(offset.z*16);
        var scale=relative.getScale(new Vector3f());bone.setScaleX(scale.x);bone.setScaleY(scale.y);bone.setScaleZ(scale.z);
        EvaRigTransforms.rotate(bone,EvaRigTransforms.rotation(relative));
    }

    private EvaCannonContactRigR45() {}
}
