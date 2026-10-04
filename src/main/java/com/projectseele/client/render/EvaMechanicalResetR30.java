package com.projectseele.client.render;

import com.projectseele.entity.EvaUnit01Entity;
import java.util.Map;
import java.util.WeakHashMap;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;

final class EvaMechanicalResetR30
{
    private record Generation(int revision,String asset,int weapon) {}
    private static final Map<EvaUnit01Entity,Generation> REVISIONS=new WeakHashMap<>();
    private static final Map<EvaUnit01Entity,Boolean> RESTORE_BIND=new WeakHashMap<>();

    /** Run before Gecko evaluates the entity; clearing post-Gecko is one frame too late. */
    static void prepare(EvaUnit01Entity eva,BakedGeoModel model)
    {
        apply(eva);
        if(RESTORE_BIND.remove(eva)==null)return;
        for(GeoBone bone:model.topLevelBones())restoreBind(bone);
    }

    private static void restoreBind(GeoBone bone)
    {
        var bind=bone.getInitialSnapshot();
        bone.setRotX(bind.getRotX());bone.setRotY(bind.getRotY());bone.setRotZ(bind.getRotZ());
        bone.setPosX(bind.getOffsetX());bone.setPosY(bind.getOffsetY());bone.setPosZ(bind.getOffsetZ());
        bone.setScaleX(bind.getScaleX());bone.setScaleY(bind.getScaleY());bone.setScaleZ(bind.getScaleZ());
        for(GeoBone child:bone.getChildBones())restoreBind(child);
    }

    static void apply(EvaUnit01Entity eva)
    {
        var generation=new Generation(eva.mechanicalRevisionR30(),eva.isExperimentalUnit()?eva.experimentalAssetName():"eva_unit0"+eva.getUnitVariant(),eva.getWeapon());
        Generation previous=REVISIONS.put(eva,generation);
        if(generation.equals(previous)||(previous==null&&generation.revision()==0))return;
        if(previous!=null&&generation.revision()==previous.revision()&&generation.asset().equals(previous.asset()))
        {
            // Only an actual weapon change invalidates these controller snapshots.
            // Stance packet clocks and captured shutdown/physical owners keep their authority.
            if(normalWeaponChangeR45(eva))
            {
                RESTORE_BIND.put(eva,true);
                var manager=eva.getAnimatableInstanceCache().getManagerForId(eva.getId());
                manager.clearSnapshotCache();
                manager.getAnimationControllers().values().forEach(controller->{controller.stop();controller.forceAnimationReset();controller.getBoneAnimationQueues().clear();});
                EvaMotionEngineV2.resetEntityR30(eva);EvaPoseTransition.resetEntityR30(eva);
                EvaRifleProneBody.resetEntityR31(eva);EvaRifleMocap.resetEntityR31(eva);
            }
            return;
        }
        RESTORE_BIND.put(eva,true);
        // Managers belong to this entity, while the baked geometry is shared.
        // Retaining controller snapshots after a reset can restore an old UN
        // pose over the new bind, including extra fingers and jet hinge bones.
        var manager=eva.getAnimatableInstanceCache().getManagerForId(eva.getId());
        manager.clearSnapshotCache();
        manager.getAnimationControllers().values().forEach(controller->{controller.stop();controller.forceAnimationReset();controller.getBoneAnimationQueues().clear();});
        EvaMotionEngineV2.resetEntityR30(eva);EvaPoseTransition.resetEntityR30(eva);eva.resetClientMechanicalClocksR30();
        EvaRifleProneBody.resetEntityR31(eva);EvaRifleMocap.resetEntityR31(eva);
        EvaHandPoseR28.resetEntityR31(eva);EvaUNHandPoseR30.resetEntityR31(eva);
        EvaShutdownPoseR30.resetEntityR31(eva);UNFlightPoseR29.resetEntityR31(eva);
        com.projectseele.entity.CombatFeelR31.clear(eva);EvaCombatPoseR31.resetEntityR31(eva);
        EvaRifleContactRig.LAST.remove(eva.getId());EvaFootPlacement.LAST.remove(eva.getId());
    }
    private static boolean normalWeaponChangeR45(EvaUnit01Entity eva)
    {
        return eva.getVisualPose()==EvaUnit01Entity.VISUAL_NORMAL&&eva.isPoweredOn()
                &&!eva.isCrucified()&&!eva.isBerserk()&&!eva.isNervLogisticsLocked()&&!eva.isLaunchSequenceActive()
                &&!eva.hasActiveCarrierMotion()&&!eva.isFirstBattleActive()
                &&!com.projectseele.entity.EvaShutdownR30.disabled(eva)
                &&!com.projectseele.entity.EvaAirTransportR31.active(eva)
                &&!com.projectseele.physics.CombatBodyDynamics.active(eva)
                &&!com.projectseele.entity.EvaWeaponHandlingR45.active(eva);
    }
    private EvaMechanicalResetR30() {}
}
