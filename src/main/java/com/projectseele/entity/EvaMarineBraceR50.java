package com.projectseele.entity;

import net.minecraft.util.Mth;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Actual two-hand support against the visible upper jaw, without moving either actor. */
public final class EvaMarineBraceR50
{
    public static GaghielEntity target(EvaUnit01Entity eva)
    {
        if(eva.isExperimentalUnit()||eva.getUnitVariant()!=2||!eva.isPoweredOn()
                ||eva.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS||!eva.isPilotCrouching()
                ||eva.isPilotProne()||eva.isNervLogisticsLocked()||EvaShutdownR30.disabled(eva)
                ||eva.isFirstBattleActive()||eva.hasLiveActionForRender(0))return null;
        return eva.level().getEntitiesOfClass(GaghielEntity.class,eva.getBoundingBox().inflate(40),
                b->b.isAlive()&&b.mouthOpen(1)>.45F&&b.mouthWorldPos(1).distanceTo(eva.position().add(0,25,0))<25)
                .stream().min(java.util.Comparator.comparingDouble(b->b.mouthWorldPos(1).distanceToSqr(eva.position()))).orElse(null);
    }

    public static void apply(EvaUnit01Entity eva,EvaBodyPose.Sample pose,float partial)
    {
        var boss=target(eva);if(boss==null)return;
        var profile=com.projectseele.physics.CombatBodyProfiles.get(eva);if(profile==null)return;
        var inverse=new Matrix4f(EvaRifleKinematics.world(eva,partial)).invert();
        float blend=Mth.clamp(eva.rifleCrouchBlend(partial),0,1)
                *Mth.clamp((boss.mouthOpen(partial)-.45F)/.25F,0,1);
        for(String side:java.util.List.of("l","r"))
        {
            String upper="arm_"+side,lower="forearm_"+side,hand="hand_"+side;
            var worldTarget=boss.modelPointR50(new net.minecraft.world.phys.Vec3(side.equals("l")?-5:5,4,-37),partial);
            var target=inverse.transformPosition(worldTarget.toVector3f());
            var origin=pose.matrix(upper).transformPosition(new Vector3f(pose.rig.get(upper).pivot()));
            var joint=com.projectseele.physics.AnatomicalLimbConstraints.elbowJoint(profile,side,pose.rig.get(lower).pivot());
            var middle=pose.matrix(upper).transformPosition(new Vector3f(joint));
            var end=pose.matrix(hand).transformPosition(new Vector3f(pose.rig.get(hand).pivot()));
            // A target outside the physical arm reach does not count as contact.
            float reach=origin.distance(middle)+middle.distance(end);
            if(origin.distance(target)>reach*.99F)continue;
            target=new Vector3f(end).lerp(target,blend);
            var upperWorld=pose.matrix(upper).getUnnormalizedRotation(new Quaternionf()).normalize();
            var lowerWorld=pose.matrix(lower).getUnnormalizedRotation(new Quaternionf()).normalize();
            var right=pose.matrix("root").transformDirection(new Vector3f(1,0,0)).normalize();
            var pole=new Vector3f(origin).fma(side.equals("l")?-.6F:.6F,right).add(0,-1.5F,.5F);
            var solved=com.projectseele.physics.AuthoredTwoBoneIKR45.solveWithPole(origin,middle,end,target,pole,right);
            if(solved==null)continue;
            upperWorld=solved.upperSwing().mul(upperWorld);lowerWorld=solved.lowerSwing().mul(lowerWorld);
            String parent=pose.rig.get(upper).parent();
            pose.rotations.put(upper,pose.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize().invert().mul(upperWorld));pose.dirty();
            parent=pose.rig.get(lower).parent();
            var local=pose.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize().invert().mul(lowerWorld);
            pose.rotations.put(lower,local);
            pose.positions.put(lower,com.projectseele.physics.AuthoredJointCentreR45.translation(new Vector3f(joint).sub(pose.rig.get(lower).pivot()),local));pose.dirty();
            var frame=EvaAnatomicalHandsR45.rig(eva.getUnitVariant()).carry().get(side);
            if(frame!=null)
            {
                var normal=new Vector3f(0,1,0);var along=new Vector3f(target).sub(origin);along.y=0;
                if(along.lengthSquared()<1e-6F)continue;along.normalize();
                var sourceAlong=new Vector3f(frame.along()).normalize();var sourceNormal=new Vector3f(frame.normal());
                sourceNormal.fma(-sourceNormal.dot(sourceAlong),sourceAlong).normalize();
                var source=new Matrix3f().setColumn(0,sourceNormal).setColumn(1,sourceAlong).setColumn(2,new Vector3f(sourceNormal).cross(sourceAlong));
                var desired=new Matrix3f().setColumn(0,normal).setColumn(1,along).setColumn(2,new Vector3f(normal).cross(along)).mul(source.transpose());
                var rotation=new Quaternionf().setFromNormalized(desired).normalize();parent=pose.rig.get(hand).parent();
                var handLocal=pose.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize().invert().mul(rotation);
                pose.rotations.get(hand).slerp(handLocal,blend);pose.dirty();
            }
        }
    }
    private EvaMarineBraceR50(){}
}
