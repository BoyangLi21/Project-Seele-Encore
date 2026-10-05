package com.projectseele.world;

import com.projectseele.entity.*;
import com.projectseele.registry.ModEntities;
import com.projectseele.ProjectSeele;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.entity.Entity;
import java.util.Map;
import java.util.HashMap;
import java.util.UUID;

/** A fourth persistent capsule, owned by the UN airframe rather than a NERV fleet slot. */
public final class UNPlugDirector
{
    private static final Map<UUID,UUID> CRANES=new HashMap<>();
    public static void resetCraneR30(EvaPrototypeEntity eva)
    {
        UUID id=CRANES.remove(eva.getUUID());if(id!=null&&eva.level() instanceof ServerLevel level&&level.getEntity(id) instanceof NervCarrierPlatformEntity crane)crane.discard();
        eva.getPersistentData().putInt("UNSequenceTicks",0);
    }
    public static EntryPlugCarrierEntity capsule(EvaPrototypeEntity eva)
    {
        CompoundTag data=eva.getPersistentData();
        if(!(eva.level() instanceof ServerLevel level)||!data.hasUUID("UNPlug"))return null;
        var original=ServiceAircraftR32.capsule(level,data.getUUID("UNPlug"));
        // Recorded UN UUID remains authoritative for legacy capsules whose UN
        // flag is upgraded by the normal director; never adopt a lab owner.
        return original!=null&&original.laboratorySlotR47()<0?original:null;
    }
    /** A new spare is issued only for an explicitly destroyed, empty field capsule. */
    public static EntryPlugCarrierEntity replaceDestroyedAtDockR31(EvaPrototypeEntity eva)
    {
        EntryPlugCarrierEntity current=capsule(eva);if(current!=null&&!current.isRemoved())return current;
        if(!(eva.level() instanceof ServerLevel level)||!atDock(eva)||!EntryPlugDisposalR31.replacementAuthorized(eva))return null;
        UUID former=eva.getPersistentData().getUUID("UNPlug");
        var plug=ModEntities.ENTRY_PLUG_CARRIER.get().create(level);if(plug==null)return null;
        plug.assignIndependentEva(eva);plug.snapCanonicalTransformR31(dock(eva));
        if(!level.addFreshEntity(plug))return null;
        eva.getPersistentData().putUUID("UNPlug",plug.getUUID());eva.getPersistentData().putUUID("UNReplacedDestroyedPlugR31",former);
        eva.getPersistentData().putInt("UNSequenceTicks",0);UNRecoveryR22.remember(plug);
        ProjectSeele.LOGGER.info("UN replacement capsule issued after confirmed destruction: eva={} old={} new={}",eva.getUUID(),former,plug.getUUID());
        return plug;
    }
    public static boolean atDock(EvaPrototypeEntity eva)
    {
        var d=eva.getPersistentData();return d.contains("UNHomeX")&&eva.position().distanceTo(new Vec3(d.getDouble("UNHomeX"),d.getDouble("UNHomeY"),d.getDouble("UNHomeZ")))<4;
    }
    public static boolean prepareEmptyForTransport(EvaPrototypeEntity eva)
    {
        var plug=capsule(eva);
        if(plug==null||plug.isVehicle()||!atDock(eva)||!UNAirLiftR29.active((ServerLevel)eva.level(),eva.getUNSerial()))return false;
        if(plug.isLockedToEva())return true;
        if(plug.getInsertionStage()!=EntryPlugCarrierEntity.STAGE_SUSPENDED)return false;
        eva.getPersistentData().putBoolean("UNTransportAutoload",true);
        return plug.transitionInsertionStage(EntryPlugCarrierEntity.STAGE_SUSPENDED,EntryPlugCarrierEntity.STAGE_OCCUPIED);
    }
    public static RigidTransform dock(EvaPrototypeEntity eva)
    {
        var d=eva.getPersistentData();double yaw=Math.toRadians(d.getFloat("UNHomeYaw"));Vec3 rear=new Vec3(Math.sin(yaw),0,-Math.cos(yaw));
        Vec3 centre=new Vec3(d.getDouble("UNHomeX"),d.getDouble("UNHomeY"),d.getDouble("UNHomeZ"));
        return EntryPlugKinematics.dockTransform(centre.add(rear.scale(12)).add(0,51.6,0),d.getFloat("UNHomeYaw"));
    }
    public static void tick(EvaPrototypeEntity eva)
    {
        if(!(eva.level() instanceof ServerLevel level))return;
        CompoundTag d=eva.getPersistentData();EntryPlugCarrierEntity plug=capsule(eva);
        if(!d.hasUUID("UNPlug"))
        {
            boolean lab=java.util.Set.of("r11-mechanics","r19-un","r21-un00","r21-un01").contains(System.getProperty("projectseele.regionalBuild",""))&&d.getBoolean("UNMechanicsLab");
            if(!lab&&(!eva.isInsideTestHangar()||eva.position().distanceTo(eva.homePosition())>4))return;
            d.putDouble("UNHomeX",eva.getX());d.putDouble("UNHomeY",eva.getY());d.putDouble("UNHomeZ",eva.getZ());d.putFloat("UNHomeYaw",eva.getYRot());
            plug=ModEntities.ENTRY_PLUG_CARRIER.get().create(level);if(plug==null)return;
            plug.assignIndependentEva(eva);plug.setCanonicalTransform(dock(eva));
            if(!level.addFreshEntity(plug))return;d.putUUID("UNPlug",plug.getUUID());
            ProjectSeele.LOGGER.info("EVA-UN dedicated capsule commissioned: eva={} plug={}",eva.getUUID(),plug.getUUID());
        }
        if(plug==null)plug=replaceDestroyedAtDockR31(eva);
        if(plug==null)return; // An unloaded saved capsule is never replaced.
        plug.assignIndependentEva(eva);
        int stage=plug.getInsertionStage(),tick=d.getInt("UNSequenceTicks");
        if(stage==EntryPlugCarrierEntity.STAGE_SUSPENDED)
        {
            if(atDock(eva)){plug.setCanonicalTransform(dock(eva));hoist(level,eva,plug);}
            d.putInt("UNSequenceTicks",0);return;
        }
        if(stage==EntryPlugCarrierEntity.STAGE_OCCUPIED&&atDock(eva))
        {
            if(eva.isNervLogisticsLocked())return;
            plug.sealCabin();d.putInt("UNSequenceTicks",++tick);plug.setCabinSequenceProgress(Math.min(30,tick));
            if(tick>=36&&plug.isHatchFullySealed())
            {
                RigidTransform previous=dock(eva);boolean clear=true;
                for(int i=1;i<=80;i++){RigidTransform next=EntryPlugKinematics.insertionTransform(eva,dock(eva),i/80D);if(!clear(level,eva,plug,previous,next)){clear=false;break;}previous=next;}
                if(clear){plug.transitionInsertionStage(stage,EntryPlugCarrierEntity.STAGE_INSERTING);d.putInt("UNSequenceTicks",0);plug.clearInsertionAbortRequest();}
                else {d.putInt("UNSequenceTicks",0);if(plug.getFirstPassenger()!=null)plug.getFirstPassenger().stopRiding();d.putBoolean("UNTransportAutoload",false);ProjectSeele.LOGGER.warn("EVA-UN crane preflight obstructed; capsule held at dock");}
            }
            hoist(level,eva,plug);return;
        }
        if(stage==EntryPlugCarrierEntity.STAGE_INSERTING)
        {
            if((!plug.isVehicle()&&!UNAirLiftR29.emptyLoading(eva))||plug.isInsertionAbortRequested())
            {plug.transitionInsertionStage(stage,EntryPlugCarrierEntity.STAGE_ABORT_RETURNING);return;}
            EvaDorsalMechanism.prepare(eva,++tick);d.putInt("UNSequenceTicks",tick);
            double p=EvaDorsalMechanism.smooth((tick-36)/154F);RigidTransform next=EntryPlugKinematics.insertionTransform(eva,dock(eva),p);
            if(!clear(level,eva,plug,plug.getCanonicalTransform(),next)){plug.transitionInsertionStage(stage,EntryPlugCarrierEntity.STAGE_ABORT_RETURNING);return;}
            plug.setCanonicalTransform(next);plug.setInsertionProgress((int)Math.round(p*100));plug.setCabinSequenceProgress(30+(int)Math.round(40*p));hoist(level,eva,plug);
            if(tick>=190&&plug.lockToEva(eva)&&eva.bindEntryPlug(plug,70))d.putInt("UNSequenceTicks",0);
            return;
        }
        if(stage==EntryPlugCarrierEntity.STAGE_LOCKED&&atDock(eva))
        {
            if(tick<60){d.putInt("UNSequenceTicks",++tick);EvaDorsalMechanism.seal(eva,tick);}
            hoist(level,eva,plug,Math.min(1,tick/48D));
            return;
        }
        if(stage==EntryPlugCarrierEntity.STAGE_ABORT_RETURNING)
        {
            int p=Math.max(0,plug.getInsertionProgress()-1);RigidTransform next=EntryPlugKinematics.insertionTransform(eva,dock(eva),p/100D);
            if(!clear(level,eva,plug,plug.getCanonicalTransform(),next))return;
            plug.setCanonicalTransform(next);plug.setInsertionProgress(p);float hold=EvaDorsalMechanism.smooth(p/28F);EvaDorsalMechanism.set(eva,Math.min(hold,EvaDorsalMechanism.open(eva)),Math.min(hold,EvaDorsalMechanism.bow(eva)));hoist(level,eva,plug);
            if(p==0){plug.transitionInsertionStage(stage,EntryPlugCarrierEntity.STAGE_ABORT_DOCKED);plug.setCabinRecoveryProgress(0);}
            return;
        }
        if(stage==EntryPlugCarrierEntity.STAGE_ABORT_DOCKED)
        {
            plug.transitionInsertionStage(stage,plug.isVehicle()?EntryPlugCarrierEntity.STAGE_OCCUPIED:EntryPlugCarrierEntity.STAGE_SUSPENDED);
            // A deliberate abort stays at the bridge until the pilot leaves and boards again.
            if(plug.isVehicle())plug.getFirstPassenger().stopRiding();d.putInt("UNSequenceTicks",0);
        }
    }
    public static void extract(EntryPlugCarrierEntity plug,int ticks)
    {
        if(!(plug.getLinkedEva() instanceof EvaPrototypeEntity eva)||!(eva.level() instanceof ServerLevel level))return;
        if(ticks<=36)EvaDorsalMechanism.prepare(eva,ticks);else if(ticks>=137)EvaDorsalMechanism.seal(eva,ticks-137);
        double p=1-Math.max(0,Math.min(1,(ticks-36)/105D));RigidTransform next=EntryPlugKinematics.insertionTransform(eva,dock(eva),p);
        if(!clear(level,eva,plug,plug.getCanonicalTransform(),next))return;
        plug.setCanonicalTransform(next);plug.setInsertionProgress((int)Math.round(p*100));plug.setCabinRecoveryProgress((int)Math.round(p*70));hoist(level,eva,plug,ticks<=36?1-EvaDorsalMechanism.smooth(ticks/36F):0);
        if(ticks>=197)
        {
            plug.transitionInsertionStage(EntryPlugCarrierEntity.STAGE_EJECTING,EntryPlugCarrierEntity.STAGE_SUSPENDED);
            if(plug.isVehicle())plug.getFirstPassenger().stopRiding();plug.openCabin();eva.getPersistentData().putInt("UNSequenceTicks",0);
        }
    }
    private static boolean clear(ServerLevel level,EvaPrototypeEntity eva,EntryPlugCarrierEntity plug,RigidTransform before,RigidTransform after)
    {
        for(int i=1;i<=4;i++)
        {
            AABB bounds=EntryPlugKinematics.worldBounds(before.interpolate(after,i/4D),EntryPlugKinematics.BODY_OBB_CENTRE_P,EntryPlugKinematics.BODY_OBB_HALF_EXTENTS).deflate(.06);
            if(level.getBlockCollisions(plug,bounds).iterator().hasNext())
            {
                diagnoseClearance(level,eva,plug,bounds,"blocks");return false;
            }
            if(!level.getEntities(plug,bounds,e->e!=eva&&e.isPickable()&&!plug.hasPassenger(e)).isEmpty())
            {diagnoseClearance(level,eva,plug,bounds,"entities");return false;}
        }
        return true;
    }
    private static void diagnoseClearance(ServerLevel level,EvaPrototypeEntity eva,EntryPlugCarrierEntity plug,AABB bounds,String kind)
    {
        String review=System.getProperty("projectseele.regionalBuild","");
        if(!review.startsWith("r21-un-base")&&!review.equals("r22-un-base")&&!review.startsWith("r29-"))return;
        if(review.startsWith("r29-")&&level.getGameTime()%20!=0)return;
        try
        {
            var report=new com.google.gson.JsonObject();report.addProperty("unit",eva.getUNSerial());report.addProperty("kind",kind);report.addProperty("bounds",bounds.toString());var cells=new com.google.gson.JsonArray();
            for(var p:net.minecraft.core.BlockPos.betweenClosed(net.minecraft.core.BlockPos.containing(bounds.minX,bounds.minY,bounds.minZ),net.minecraft.core.BlockPos.containing(bounds.maxX,bounds.maxY,bounds.maxZ)))
            {var state=level.getBlockState(p);if(state.getCollisionShape(level,p,net.minecraft.world.phys.shapes.CollisionContext.of(plug)).toAabbs().stream().anyMatch(b->b.move(p).intersects(bounds))){var row=new com.google.gson.JsonObject();row.addProperty("pos",p.toShortString());row.addProperty("state",state.toString());cells.add(row);}}
            report.add("cells",cells);var entities=new com.google.gson.JsonArray();for(var entity:level.getEntities(plug,bounds,e->e!=eva&&e.isPickable()&&!plug.hasPassenger(e)))entities.add(entity.getType()+" "+entity.position());report.add("entities",entities);
            java.nio.file.Files.writeString(level.getServer().getWorldPath(net.minecraft.world.level.storage.LevelResource.ROOT).resolve("un_preflight_obstruction.json"),report.toString());
        }catch(Exception e){throw new IllegalStateException(e);}
    }
    private static void hoist(ServerLevel level,EvaPrototypeEntity eva,EntryPlugCarrierEntity plug)
    {hoist(level,eva,plug,0);}
    private static void hoist(ServerLevel level,EvaPrototypeEntity eva,EntryPlugCarrierEntity plug,double raised)
    {
        NervCarrierPlatformEntity crane=null;UUID id=CRANES.get(eva.getUUID());if(id!=null&&level.getEntity(id) instanceof NervCarrierPlatformEntity c)crane=c;
        Vec3 eye=plug.getCanonicalTransform().transformPoint(EntryPlugKinematics.CRANE_ATTACHMENT_P);double y=eva.getPersistentData().getDouble("UNHomeY")+73;
        double lower=eye.y+(y-2-eye.y)*Math.max(0,Math.min(1,raised));
        if(crane==null){crane=ModEntities.NERV_CARRIER_PLATFORM.get().create(level);if(crane==null)return;crane.configurePlugCrane(1,lower-y);crane.moveControlled(eye.x,y,eye.z);crane.linkCranePlug(plug);if(!level.addFreshEntity(crane))return;CRANES.put(eva.getUUID(),crane.getUUID());}
        crane.configurePlugCrane(1,lower-y);crane.moveControlled(eye.x,y,eye.z);crane.linkCranePlug(plug);
    }
    private UNPlugDirector() {}
}
