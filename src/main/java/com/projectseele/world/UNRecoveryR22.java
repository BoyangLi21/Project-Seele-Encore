package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import net.minecraft.commands.*;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.*;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.*;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.*;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;

/** Recall the recorded UN actors; absent/unloaded UUIDs never authorize respawning. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class UNRecoveryR22
{
    public static final class Locations extends SavedData
    {
        final Map<UUID,BlockPos> positions=new HashMap<>();
        static Locations load(CompoundTag t){var s=new Locations();for(String k:t.getAllKeys())try{s.positions.put(UUID.fromString(k),BlockPos.of(t.getLong(k)));}catch(IllegalArgumentException ignored){}return s;}
        @Override public CompoundTag save(CompoundTag t){positions.forEach((id,p)->t.putLong(id.toString(),p.asLong()));return t;}
    }
    private record Job(int serial,boolean reset,CommandSourceStack source,int started) {}
    private static final Map<ServerLevel,Map<Integer,Job>> JOBS=new WeakHashMap<>();
    private static final TicketType<ChunkPos> TICKET=TicketType.create("seele_un_recovery",Comparator.comparingLong(ChunkPos::toLong),240);
    private static Locations locations(ServerLevel l){return l.getDataStorage().computeIfAbsent(Locations::load,Locations::new,"projectseele_un_locations_r22");}
    public static void remember(net.minecraft.world.entity.Entity eva)
    {
        if(!(eva.level() instanceof ServerLevel l)||!l.dimension().equals(FacilitySchemaV2.DIMENSION))return;
        if(!(eva instanceof EvaPrototypeEntity)&&!(eva instanceof EntryPlugCarrierEntity p&&p.isIndependentUNPlug()))return;
        var s=locations(l);BlockPos p=eva.blockPosition();
        if(!p.equals(s.positions.get(eva.getUUID()))){s.positions.put(eva.getUUID(),p);s.setDirty();}
    }
    public static UUID identity(ServerLevel l,int serial){return serial==0?MilitaryR07Director.state(l).entities.get("prototype"):UNAnnexR20.state(l).unitId;}
    public static Vec3 originalHome(int serial){return new Vec3(serial==1?6282.5:6442.5,77,-6205.5);}
    public static Vec3 home(ServerLevel level,int serial){return FacilitySites.un(level,originalHome(serial));}
    public static BlockPos lastKnownPosition(ServerLevel level,UUID id){return locations(level).positions.get(id);}
    private static void load(ServerLevel l,BlockPos p)
    {
        for(int x=(p.getX()>>4)-1;x<=(p.getX()>>4)+1;x++)for(int z=(p.getZ()>>4)-1;z<=(p.getZ()>>4)+1;z++)
        {var c=new ChunkPos(x,z);l.getChunkSource().addRegionTicket(TICKET,c,2,c);l.getChunk(x,z);}
    }
    public static int request(CommandSourceStack source,int serial,boolean reset)
    {
        var l=source.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(l==null||identity(l,serial)==null){source.sendFailure(Component.translatable("message.projectseele.un.unregistered"));return 0;}
        if(!reset)
        {
            var caller=source.getPlayer();
            if(caller==null){source.sendFailure(Component.translatable("message.projectseele.un.request_airlift"));return 0;}
            String reply=UNAirLiftR29.requestRecoveryR47(caller,serial);
            source.sendSuccess(()->Component.translatable("ops.projectseele.un.unit_reply", "EVA-UN-0"+serial, OperationText.read(reply)),false);return 1;
        }
        if(UNAirLiftR29.active(l,serial))
        {
            if(!reset){source.sendFailure(Component.translatable("message.projectseele.un.transport_busy"));return 0;}
        }
        JOBS.computeIfAbsent(l,k->new HashMap<>()).put(serial,new Job(serial,reset,source,source.getServer().getTickCount()));
        source.sendSuccess(()->Component.translatable("message.projectseele.unrecovery_r22.eva_un_0_s_locating_the_eva", serial),false);return 1;
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;var l=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(l==null)return;
        var jobs=JOBS.get(l);if(jobs==null)return;
        for(var it=jobs.values().iterator();it.hasNext();)
        {
            var job=it.next();UUID id=identity(l,job.serial());Vec3 home=home(l,job.serial());
            load(l,locations(l).positions.getOrDefault(id,BlockPos.containing(home)));load(l,BlockPos.containing(home));
            if(event.getServer().getTickCount()-job.started()>200){job.source().sendFailure(Component.translatable("message.projectseele.un.unloaded"));it.remove();continue;}
            if(!(l.getEntity(id) instanceof EvaPrototypeEntity eva))continue;
            load(l,eva.blockPosition());var data=eva.getPersistentData();
            if(data.hasUUID("UNPlug"))
            {
                BlockPos parked=locations(l).positions.get(data.getUUID("UNPlug"));if(parked!=null)load(l,parked);
            }
            var plug=UNPlugDirector.capsule(eva);
            boolean destroyed=plug==null&&EntryPlugDisposalR31.replacementAuthorized(eva);
            if(plug==null&&!destroyed)continue;
            if(eva.getPilotEntity()!=null||eva.getPassengers().stream().anyMatch(person->!(person instanceof EntryPlugCarrierEntity))||plug!=null&&!plug.getPassengers().isEmpty())
            {job.source().sendFailure(Component.translatable("message.projectseele.un.pilot_aboard"));it.remove();continue;}
            if(UNAirLiftR29.active(l,job.serial()))UNAirLiftR29.abortForMaintenance(l,job.serial());
            eva.stopUNFlight();
            var pilot=eva.getPilotEntity();var passengers=new ArrayList<net.minecraft.world.entity.Entity>();if(plug!=null)passengers.addAll(plug.getPassengers());passengers.addAll(eva.getPassengers());
            eva.normalizeAfterTransportR30(true);UNPlugDirector.resetCraneR30(eva);
            eva.teleportTo(home.x,home.y,home.z);eva.moveOnNervCarrier(home.x,home.y,home.z,0);eva.resetFallDistance();
            eva.xo=eva.xOld=home.x;eva.yo=eva.yOld=home.y;eva.zo=eva.zOld=home.z;
            eva.setYRot(0);eva.yRotO=0;eva.setXRot(0);eva.xRotO=0;eva.setYBodyRot(0);eva.yBodyRotO=0;eva.setYHeadRot(0);eva.yHeadRotO=0;
            eva.setNervLogisticsLocked(false);eva.setNervLogisticsLocked(true);
            data.putDouble("UNHomeX",home.x);data.putDouble("UNHomeY",home.y);data.putDouble("UNHomeZ",home.z);data.putFloat("UNHomeYaw",0);
            if(destroyed){plug=UNPlugDirector.replaceDestroyedAtDockR31(eva);if(plug==null)continue;}
            boolean extracting=pilot!=null&&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_LOCKED;
            if(extracting)
            {
                plug.snapCanonicalTransformR31(EntryPlugKinematics.lockedTransform(eva));
                if(!EntryPlugDirector.ejectPilotToPlug(l,-1,eva,pilot))throw new IllegalStateException("UN extraction failed after identity-safe recall");
            }
            else
            {
                for(var person:passengers)
                {
                    if(person instanceof EntryPlugCarrierEntity)continue;
                    person.stopRiding();person.setInvisible(false);person.setDeltaMovement(Vec3.ZERO);person.resetFallDistance();
                    // Original crew use the actual capsule's native safe exit.
                    // Their existing return controller owns walking/standby.
                }
                if(job.reset()){EvaBayRepairR33.resetForMaintenance(eva);eva.setHealth(eva.getMaxHealth());}
                plug.resetIndependentAtDock(eva);eva.enterHangarStandby();EvaDorsalMechanism.set(eva,0,0);
            }
            remember(eva);remember(plug);job.source().sendSuccess(()->Component.translatable("message.projectseele.unrecovery_r22.eva_un_0_s_is_back_in", job.serial(), Component.translatable(extracting ? "message.projectseele.unrecovery_r22.the_entry_plug_is_being_extracted" : destroyed ? "message.projectseele.unrecovery_r22.a_spare_entry_plug_has_been_fitted" : "message.projectseele.unrecovery_r22.the_eva_and_entry_plug_have_been")),false);
            ProjectSeele.LOGGER.info("UN R22 {} serial={} eva={} plug={}",job.reset()?"reset":"recover",job.serial(),id,plug.getUUID());it.remove();
        }
    }
    private UNRecoveryR22(){}
}
