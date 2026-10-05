package com.projectseele.world;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.NervCarrierPlatformEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import java.util.Optional;

/** Only the canonical NERV plant's owned clocks; field combat and UN are outside this authority. */
public final class TvPersonnelOwnedMotionR44
{
    public static final int NONE=0, TRANSFER=1, LAUNCH=2, DESCENT=3, WET_EJECT=4;
    public record Decision(boolean owned,int kind,Optional<String> fault) { }
    private static Decision outside() { return new Decision(false,NONE,Optional.empty()); }
    private static Decision unknown(int kind,String reason) { return new Decision(true,kind,Optional.of(reason)); }
    public static BlockPos wetBed(int variant) { return new BlockPos(-12+42*variant,-443,-240); }
    private static BlockPos silo(ServerLevel level,int variant)
    {
        return FacilityV2EvaRuntime.ready(level,variant)?FacilityV2EvaRuntime.lowerLiftBed(level,variant)
                :IntegratedNervMapBuilder.lowerLiftBed(level,variant);
    }
    private static boolean near(Vec3 point,BlockPos bed,double above)
    {
        return point.distanceToSqr(new Vec3(bed.getX()+.5,bed.getY()+above,bed.getZ()+.5))<.0001;
    }
    public static Decision unit(EvaUnit01Entity unit)
    {
        if(!(unit.level() instanceof ServerLevel level)||!TvPersonnelPlatformInterlockR44.enabled(level)
                ||unit.isStreamingAirCarrierFrameR44()||com.projectseele.entity.EvaAirTransportR31.active(unit)
                ||unit.isFirstBattleActive()||unit.isBerserk())return outside();
        int v=unit.getUnitVariant();if(v<0||v>2)return outside();
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(v);
        if(fleet.isEmpty())return unit.hasSavedTvPersonnelOwnershipR44()?unknown(unit.tvPersonnelSavedKindR44(),"本机保存的时钟归属尚未附着。"):outside();
        if(!fleet.get().canonicalId().equals(unit.getUUID())||fleet.get().phase()==EvaFleetSavedData.Phase.DEPLOYED)return outside();
        if(unit.tvPersonnelClockPersistenceInvalidR44())return unknown(Math.max(TRANSFER,unit.tvPersonnelSavedKindR44()),"本机保存的时钟类型／版本未知。");
        int kind=NONE;var phase=fleet.get().phase();
        if(unit.isLaunchSequenceActive()&&phase==EvaFleetSavedData.Phase.SILO_READY)
        {
            var bed=unit.getLaunchBedPosition();
            if(bed==null||!bed.equals(silo(level,v)))return unknown(LAUNCH,"本机发射时钟与实际井底归属不一致。");
            kind=LAUNCH;
        }
        else if(unit.hasTimedCarrierMotionR44())
        {
            var from=unit.carrierMotionFromR44();var to=unit.carrierMotionToR44();var lower=silo(level,v);
            if(phase==EvaFleetSavedData.Phase.TO_SILO)
            {
                if(!near(from,wetBed(v),1)||!near(to,lower,1))return unknown(TRANSFER,"本机正向载台路径与归属不一致。");
                kind=TRANSFER;
            }
            else if(phase==EvaFleetSavedData.Phase.TO_HANGAR)
            {
                if(!near(from,lower,1)||!near(to,wetBed(v),1))return unknown(TRANSFER,"本机回收载台路径与归属不一致。");
                kind=TRANSFER;
            }
            else if(phase==EvaFleetSavedData.Phase.DESCENDING)
            {
                var surface=EvaLogisticsDirector.surfaceTransportBedR30(level,v);
                if(!near(from,surface,2)||!near(to,lower,1))return unknown(DESCENT,"本机下降路径与归属不一致。");
                kind=DESCENT;
            }
        }
        if(kind==NONE&&unit.getActivationTicks()>0
                &&(phase!=EvaFleetSavedData.Phase.PARKED||unit.isNervLogisticsLocked()))kind=LAUNCH;
        if(kind==NONE)
        {
            if(unit.hasSavedTvPersonnelActiveClockR44()&&unit.hasTimedCarrierMotionR44())
                return unknown(Math.max(TRANSFER,unit.tvPersonnelSavedKindR44()),"保存的本机活动时钟与当前阶段不一致。");
            return outside();
        }
        return new Decision(true,kind,TvPersonnelPlatformInterlockR44.movementFault(level,v));
    }
    public static Decision wetPlug(EntryPlugCarrierEntity plug)
    {
        if(!(plug.level() instanceof ServerLevel level)||!TvPersonnelPlatformInterlockR44.enabled(level)
                ||plug.laboratorySlotR47()>=0||plug.isIndependentUNPlug()||plug.getInsertionStage()!=EntryPlugCarrierEntity.STAGE_EJECTING)return outside();
        int v=plug.getAssignedVariant();if(v<0||v>2)return outside();
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(v);
        if(fleet.isEmpty())return plug.hasSavedTvPersonnelOwnershipR44()?unknown(WET_EJECT,"保存的湿舱弹出栓归属尚未附着。"):outside();
        if(fleet.get().entryPlugId()==null||!fleet.get().entryPlugId().equals(plug.getUUID()))return outside();
        switch(fleet.get().phase())
        {
            case DEPLOYED, SILO_READY, DESCENDING, TO_SILO, TO_HANGAR -> { return outside(); }
            default -> { }
        }
        if(plug.tvPersonnelWetPersistenceInvalidR44())return unknown(WET_EJECT,"本机湿舱弹出时钟保存类型／版本未知。");
        double x=-11.5+42*v;var p=plug.position();
        if(!plug.hasCanonicalPose()||p.x<x-20.5||p.x>x+20.5||p.y<-445||p.y>-355||p.z<-268||p.z>-210)
            return unknown(WET_EJECT,"本机湿舱弹出栓实际姿态不可验证。");
        return new Decision(true,WET_EJECT,TvPersonnelPlatformInterlockR44.movementFault(level,v));
    }
    /** A pause must not let the existing non-saving visuals expire after40ticks. */
    public static void keepWetMachines(ServerLevel level,int variant)
    {
        if(!TvPersonnelPlatformInterlockR44.enabled(level)||variant<0||variant>2)return;
        double x=-11.5+42*variant;
        for(var machine:level.getEntitiesOfClass(NervCarrierPlatformEntity.class,new AABB(x-21,-445,-268,x+21,-354,-210),
                e->e.isAlive()&&e.getUnitVariant()==variant&&(e.isRestraintGantry()||e.isPlugCrane())))
            machine.holdStatic(machine.getX(),machine.getY(),machine.getZ());
    }
    private TvPersonnelOwnedMotionR44() { }
}
