package com.projectseele.client.render;
import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaUnit01Entity;
import org.joml.Quaternionf;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.*;

/** All low-stance locomotion uses one continuous body path, before final transition and contact writers. */
public final class EvaLocomotionRig
{
    public static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva,BakedGeoModel model,float partial)
    {
        if(eva.hasLegacyStrikeForRender())return EvaMotionEngineV2.BoneWrites.empty();
        if(!EvaBodyPose.hasTerrainStances()||!eva.isPoweredOn()||eva.isFirstBattleActive()||eva.isBerserk()||eva.isCrucified()||eva.isNervLogisticsLocked()||eva.getActivationTicks()>0||eva.getVisualPose()!=0||eva.getMotionLabPhysicsPreview()!=0||eva.isVisuallyAirborneForRender()||eva.hasLiveActionForRender(partial))return EvaMotionEngineV2.BoneWrites.empty();
        if(eva.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS&&eva.getWeapon()!=EvaUnit01Entity.WEAPON_KNIFE)return EvaMotionEngineV2.BoneWrites.empty();
        var body=EvaBodyPose.sample(eva,partial);Set<String> names=new LinkedHashSet<>();
        for(String n:body.rig.keySet())
        {
            if(n.equals("cannon")||n.contains("knife")||n.contains("lance"))continue;
            var bone=model.getBone(n).orElse(null);if(bone==null)continue;
            EvaRigTransforms.rotate(bone,body.rotations.get(n));var p=body.positions.get(n);bone.setPosX(-p.x*16);bone.setPosY(p.y*16);bone.setPosZ(p.z*16);names.add(n);
        }
        // Keep head look relative to the authored low body, rather than forcing an upright neck.
        model.getBone("head").ifPresent(b->{Quaternionf q=new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX());q.rotateY((float)Math.toRadians(-eva.pilotHeadYawForRender(partial))).rotateX((float)Math.toRadians(-eva.pilotHeadPitchForRender(partial)));EvaRigTransforms.rotate(b,q);});
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(names),Set.copyOf(names),"MOTION_ENGINE_LIVE_ACTION");
    }
    private EvaLocomotionRig() {}
}
