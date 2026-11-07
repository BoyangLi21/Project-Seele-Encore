package com.projectseele.client.render;

import com.projectseele.entity.EvaUnit01Entity;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;
import java.util.LinkedHashSet;
import java.util.Set;

/** A restrained airframe has one structural bind pose; the dorsal hinge remains mechanical. */
final class EvaLockedCagePoseR44
{


    static boolean applies(EvaUnit01Entity entity)
    {
        return !entity.isExperimentalUnit() && entity.isNervLogisticsLocked() && !entity.isFirstBattleActive()
                && !entity.isCrucified() && !com.projectseele.physics.CombatBodyDynamics.active(entity)
                && !com.projectseele.entity.EvaShutdownR30.displayed(entity)
                && !com.projectseele.entity.EvaAirTransportR31.active(entity);
    }

    static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity entity, BakedGeoModel model)
    {
        Set<String> bones = new LinkedHashSet<>();
        for (GeoBone root : model.topLevelBones()) restore(root, bones);
        // Socket opening/head bow is an actual equipment state, not an idle
        // body overlay. Its torso release starts from this fixed bind pose.
        EvaDorsalPose.apply(entity, model);
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(bones), Set.copyOf(bones), "MOTION_ENGINE_LIVE_ACTION");
    }

    private static void restore(GeoBone bone, Set<String> bones)
    {
        var bind = bone.getInitialSnapshot();
        bone.setRotX(bind.getRotX()); bone.setRotY(bind.getRotY()); bone.setRotZ(bind.getRotZ());
        bone.setPosX(bind.getOffsetX()); bone.setPosY(bind.getOffsetY()); bone.setPosZ(bind.getOffsetZ());
        bone.setScaleX(bind.getScaleX()); bone.setScaleY(bind.getScaleY()); bone.setScaleZ(bind.getScaleZ());
        bones.add(bone.getName());
        for (GeoBone child : bone.getChildBones()) restore(child, bones);
    }


    private EvaLockedCagePoseR44() {}
}
