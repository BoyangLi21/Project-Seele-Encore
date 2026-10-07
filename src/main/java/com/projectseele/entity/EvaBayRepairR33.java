package com.projectseele.entity;

import com.projectseele.ProjectSeele;
import com.projectseele.world.*;
import net.minecraft.network.syncher.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.util.Mth;

/** Repair the original airframe in its own dock; never reset or replace identities. */
public final class EvaBayRepairR33
{
    public static final int DURATION=2400;
    private static final EntityDataAccessor<Integer> ELAPSED=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.INT);
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData d){d.define(ELAPSED,-1);}
    public static boolean active(EvaUnit01Entity e){return e.getEntityData().get(ELAPSED)>=0;}
    public static void resetForMaintenance(EvaUnit01Entity e)
    {if(!e.level().isClientSide){e.getPersistentData().remove("R33Repair");e.getEntityData().set(ELAPSED,-1);}}
    public static float progress(EvaUnit01Entity e,float partial){return Mth.clamp((e.getEntityData().get(ELAPSED)+partial)/DURATION,0,1);}
    public static boolean docked(EvaUnit01Entity e)
    {
        if(!(e.level() instanceof ServerLevel level)||e.hasActiveCarrierMotion()||e.isLaunchSequenceActive()||EvaAirTransportR31.active(e))return false;
        if(e instanceof EvaPrototypeEntity un)
            return e.getUUID().equals(UNRecoveryR22.identity(level,un.getUNSerial()))&&e.position().distanceToSqr(UNRecoveryR22.home(un.getUNSerial()))<16;
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(e.getUnitVariant()).orElse(null);
        return e.isNervLogisticsLocked()&&EvaLogisticsDirector.inAssignedHangarR33(level,e)&&fleet!=null&&fleet.canonicalId().equals(e.getUUID())
                &&(fleet.phase()==EvaFleetSavedData.Phase.PARKED||fleet.phase()==EvaFleetSavedData.Phase.FILLING);
    }
    public static void tick(EvaUnit01Entity e)
    {
        if(e.level().isClientSide)return;
        var data=e.getPersistentData();boolean eligible=docked(e)&&e.getPilotEntity()==null;
        // Servicing a verified local bay must not depend on the launch
        // director having accepted every remote lift/shaft marker. Its global
        // interlock can correctly stop launches while a local repair proceeds.
        if(eligible&&!(e instanceof EvaPrototypeEntity)&&(active(e)||e.tickCount%20==0))
        {
            var level=(ServerLevel)e.level();var bay=EvaFleetSavedData.get(level.getServer()).entry(e.getUnitVariant()).orElse(null);
            if(bay!=null&&bay.phase()==EvaFleetSavedData.Phase.PARKED)
            {
                var bed=EvaLogisticsDirector.assignedHangarBedR33(level,e.getUnitVariant());
                NervCarrierVisuals.updateRestraints(level,e,bed.getX()+.5,bed.getY(),bed.getZ()+.5,1);
            }
        }
        if(!eligible)
        {
            if(active(e)){data.remove("R33Repair");e.getEntityData().set(ELAPSED,-1);}
            return;
        }
        // A finished service can wait for the same original shield's real
        // cabinet slot. Never repair a loaned/carried stack remotely.
        TvMissionEquipmentR45.applyCompletedShieldBayServiceR50(e);
        var shieldService=data.contains("R33Repair")?new CompoundTag():
                TvMissionEquipmentR45.shieldBayServiceTargetR50(e,e.getHealth()>=e.getMaxHealth());
        if(!data.contains("R33Repair")&&(e.getHealth()<e.getMaxHealth()||!shieldService.isEmpty())
                &&EvaDorsalMechanism.bow(e)<=.001F&&EvaDorsalMechanism.open(e)<=.001F)
        {
            var job=new CompoundTag();job.putLong("start",e.level().getGameTime());job.putFloat("health",e.getHealth());data.put("R33Repair",job);
            if(!shieldService.isEmpty())job.put("ShieldServiceR50",shieldService);
            e.getEntityData().set(ELAPSED,0);e.setNervLogisticsLocked(true);
            ProjectSeele.LOGGER.info("EVA bay repair started: eva={} health={} duration={}",e.getUUID(),e.getHealth(),DURATION);
        }
        if(!data.contains("R33Repair"))return;
        var job=data.getCompound("R33Repair");int elapsed=(int)Math.min(DURATION,Math.max(0,e.level().getGameTime()-job.getLong("start")));
        e.getEntityData().set(ELAPSED,elapsed);
        // Diagnosis and tool docking, structural repair, then retract/test. The
        // shutdown interlock stays engaged even after HP has become nonzero.
        float amount=Mth.clamp((elapsed-120F)/2160F,0,1);
        e.setHealth(Math.max(e.getHealth(),Mth.lerp(amount,job.getFloat("health"),e.getMaxHealth())));
        e.setDeltaMovement(net.minecraft.world.phys.Vec3.ZERO);
        if(elapsed>0&&elapsed<2280&&elapsed%100==0)e.level().playSound(null,e.getX(),e.getY()+35,e.getZ(),com.projectseele.registry.ModSounds.FACILITY.get("facility_hydraulic").get(),net.minecraft.sounds.SoundSource.BLOCKS,.7F,.84F);

        if(elapsed>=DURATION)
        {
            TvMissionEquipmentR45.completeShieldBayServiceR50(e,job.getCompound("ShieldServiceR50"));
            data.remove("R48YashimaFieldBurnout");
            data.remove("R48YashimaShieldHits");
            e.setHealth(e.getMaxHealth());data.remove("R33Repair");e.getEntityData().set(ELAPSED,-1);
            EvaShutdownR30.clear(e);
            if(e instanceof EvaPrototypeEntity){e.setYRot(0);e.setYHeadRot(0);e.setYBodyRot(0);}
            e.enterHangarStandby();
            ProjectSeele.LOGGER.info("EVA bay repair complete: originalEva={} health={}",e.getUUID(),e.getHealth());
        }
    }
    private EvaBayRepairR33(){}
}
