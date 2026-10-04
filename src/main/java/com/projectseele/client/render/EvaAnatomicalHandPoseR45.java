package com.projectseele.client.render;

import com.projectseele.entity.EvaAnatomicalHandsR45;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaGameplayMotionR32;
import com.projectseele.entity.EvaCombatR31;
import com.projectseele.entity.EvaShutdownR30;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;

/** Final finger owner; wrist and weapon solvers cannot rewrite these joints. */
final class EvaAnatomicalHandPoseR45
{
    static void apply(EvaUnit01Entity eva,BakedGeoModel model,float partial)
    {
        if(!EvaAnatomicalHandsR45.enabled(eva)||!EvaHandSurfaceR45.applies(eva))return;
        var mechanism=EvaAnatomicalHandsR45.knifeMechanism(eva);
        if(mechanism!=null)
        {
            var cover=model.getBone(mechanism.cover()).orElseThrow(()->new IllegalStateException("Missing candidate knife cover"));
            float angle=mechanism.openDegrees()*net.minecraft.util.Mth.DEG_TO_RAD
                    *com.projectseele.entity.EvaWeaponHandlingR45.hatchOpen(eva,partial);
            var hinge=mechanism.hingeAxis();
            EvaRigTransforms.rotate(cover,new Quaternionf().rotationAxis(angle,hinge.x,hinge.y,hinge.z));
            cover.setPosX(0);cover.setPosY(0);cover.setPosZ(0);
            if(!mechanism.carriage().isEmpty())
            {
                var carriage=model.getBone(mechanism.carriage()).orElseThrow();
                var actuator=model.getBone(mechanism.actuator()).orElseThrow();
                float w=com.projectseele.entity.EvaWeaponHandlingR45.carriage(eva,partial);
                var stored=new Vector3f(-carriage.getPivotX(),carriage.getPivotY(),carriage.getPivotZ());
                var centre=new Vector3f(stored).lerp(mechanism.presented(),w);
                centre.y+=mechanism.liftModel()*(float)Math.sin(Math.PI*w);
                var offset=new Vector3f(centre).sub(stored);
                carriage.setPosX(offset.x);carriage.setPosY(offset.y);carriage.setPosZ(offset.z);
                float carrierAngle=net.minecraft.util.Mth.lerp(w,mechanism.storedPitchDegrees(),-90)*net.minecraft.util.Mth.DEG_TO_RAD;
                EvaRigTransforms.rotate(carriage,new Quaternionf().rotationX(carrierAngle));
                var base=new Vector3f(-actuator.getPivotX(),actuator.getPivotY(),actuator.getPivotZ());
                var endpoint=new Vector3f(mechanism.actuatorPin()).rotateX(carrierAngle).add(centre);
                var direction=endpoint.sub(base).mul(-1,1,1);float length=direction.length();
                EvaRigTransforms.rotate(actuator,new Quaternionf().rotationTo(new Vector3f(0,1,0),direction.normalize()));
                actuator.setPosX(0);actuator.setPosY(0);actuator.setPosZ(0);
                actuator.setScaleX(1);actuator.setScaleY(length/mechanism.actuatorLength());actuator.setScaleZ(1);
            }
        }
        var pose=EvaAnatomicalHandsR45.sample(eva,partial);
        for(var entry:pose.rotations().entrySet())
        {
            var bone=model.getBone(entry.getKey()).orElseThrow(()->new IllegalStateException("Missing candidate hand joint "+entry.getKey()));
            EvaRigTransforms.rotate(bone,entry.getValue());
            bone.setPosX(0);bone.setPosY(0);bone.setPosZ(0);bone.setScaleX(1);bone.setScaleY(1);bone.setScaleZ(1);
        }
        if(eva.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE&&!EvaGameplayMotionR32.sharedBody(eva,partial)
                &&EvaCombatR31.action(eva)==EvaCombatR31.NONE&&!eva.isNervLogisticsLocked()
                &&!eva.isFirstBattleActive()&&!EvaShutdownR30.disabled(eva))
            model.getBone("knife").ifPresent(b->{
                var pivot=new Vector3f(b.getPivotX(),b.getPivotY(),b.getPivotZ()).div(16);
                var authored=new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX());
                var k=EvaAnatomicalHandsR45.knifePose(eva,pivot,authored);if(k==null)return;
                EvaRigTransforms.rotate(b,k.rotation());var p=k.position();
                b.setPosX(-p.x*16);b.setPosY(p.y*16);b.setPosZ(p.z*16);
            });
    }
    private EvaAnatomicalHandPoseR45(){}
}
