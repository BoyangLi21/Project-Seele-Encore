package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.TrainingPilotEntity;
import java.util.List;
import java.util.UUID;
import java.util.function.Function;
import java.util.function.Predicate;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.entity.EntityMountEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Optional capability of the same explicitly installed Root owner. No coordinates,
 * actor creation, UUID adoption, or legacy repair is supplied by this bridge. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class NervOriginalActorsR52
{
    public interface Access
    {
        default boolean originalSeatAllowed(ServerLevel level,com.projectseele.entity.NervCommandSeatEntity seat,TrainingPilotEntity pilot){return false;}
        default Vec3 originalSeatStand(ServerLevel level,com.projectseele.entity.NervCommandSeatEntity seat,TrainingPilotEntity pilot){return null;}
        default boolean originalEntryPlugBindingsReady(ServerLevel level){return false;}
        default Vec3 originalBoardingAnchor(ServerLevel level,EntryPlugCarrierEntity plug){return null;}
        default RigidTransform originalDockPose(ServerLevel level,int variant){return null;}
        default RigidTransform originalBayPose(ServerLevel level,int variant){return null;}
        default Vec3 originalDismountAnchor(ServerLevel level,EntryPlugCarrierEntity plug,LivingEntity passenger){return null;}
        default boolean originalBoardingAllowed(ServerLevel level,EntryPlugCarrierEntity plug,Entity passenger){return false;}
        default boolean originalLaunchLock(ServerLevel level,int variant,EvaUnit01Entity eva,EntryPlugCarrierEntity plug){return false;}
        default boolean originalCageDock(ServerLevel level,int variant,EvaUnit01Entity eva,EntryPlugCarrierEntity plug){return false;}
        default boolean requestOriginalEjection(ServerLevel level,int variant,EvaUnit01Entity eva,LivingEntity pilot){return false;}
        default void maintainOriginalCapsule(ServerLevel level,EntryPlugCarrierEntity plug){}
        default TrainingPilotEntity originalPilot(ServerLevel level,int variant){return null;}
        default void retainOriginalPilotSections(ServerLevel level,int variant){}
        default List<NervStaffDirector.Station> originalStaffRoster(ServerLevel level){return List.of();}
        default void maintainOriginalStaff(ServerLevel level){}
    }
    private NervOriginalActorsR52(){}
    private static final String SAVED_SEAT_R54="NervOriginalSeatR54";
    private static final java.util.Map<ServerPlayer,Integer> SEAT_RESTORE_R54=new java.util.WeakHashMap<>();
    private static final java.util.Map<ServerPlayer,UUID> DISCONNECT_SEATS_R54=new java.util.WeakHashMap<>();

    /** World-owned roots must not migrate into one player's RootVehicle save.
     * This identity check is independent of the owner's installation readiness. */
    public static boolean worldOwnedVehicleR54(Entity actor)
    {
        if(!(actor.level() instanceof ServerLevel level))return false;
        if(actor instanceof EntryPlugCarrierEntity plug)
        {
            if(plug.laboratorySlotR47()>=0||plug.isIndependentUNPlug())return false;
            var fleet=EvaFleetSavedData.get(level.getServer()).entry(plug.getAssignedVariant()).orElse(null);
            return fleet!=null&&plug.getUUID().equals(fleet.entryPlugId());
        }
        if(actor instanceof EvaUnit01Entity eva&&!eva.isExperimentalUnit())
        {
            var fleet=EvaFleetSavedData.get(level.getServer()).entry(eva.getUnitVariant()).orElse(null);
            return fleet!=null&&eva.getUUID().equals(fleet.canonicalId());
        }
        return false;
    }

    private static void rememberSeatR54(ServerPlayer player,EntryPlugCarrierEntity plug)
    {
        var saved=new net.minecraft.nbt.CompoundTag();saved.putUUID("Player",player.getUUID());
        saved.putUUID("Seat",plug.getUUID());saved.putInt("Variant",plug.getAssignedVariant());
        saved.putString("Dimension",plug.level().dimension().location().toString());
        var chunk=plug.getRootVehicle().chunkPosition();saved.putInt("ChunkX",chunk.x);saved.putInt("ChunkZ",chunk.z);
        player.getPersistentData().put(SAVED_SEAT_R54,saved);
    }

    /** A player save holds only its own seat reference, never another actor copy. */
    @SubscribeEvent(priority=net.minecraftforge.eventbus.api.EventPriority.LOWEST)
    public static void rememberSeatMountR54(EntityMountEvent event)
    {
        if(event.isCanceled()||!(event.getEntityMounting() instanceof ServerPlayer player)
                ||!(event.getEntityBeingMounted() instanceof EntryPlugCarrierEntity plug)||!worldOwnedVehicleR54(plug))return;
        if(event.isMounting())rememberSeatR54(player,plug);
        else if(!plug.getUUID().equals(DISCONNECT_SEATS_R54.get(player)))player.getPersistentData().remove(SAVED_SEAT_R54);
    }

    @SubscribeEvent public static void retainSeatOnLogoutR54(net.minecraftforge.event.entity.player.PlayerEvent.PlayerLoggedOutEvent event)
    {
        if(!(event.getEntity() instanceof ServerPlayer player))return;
        SEAT_RESTORE_R54.remove(player);
        // Forge fires this before vanilla saves the player and unmounts it.
        if(player.getVehicle() instanceof EntryPlugCarrierEntity plug&&worldOwnedVehicleR54(plug))
        {rememberSeatR54(player,plug);DISCONNECT_SEATS_R54.put(player,plug.getUUID());}
        else player.getPersistentData().remove(SAVED_SEAT_R54);
    }

    /** Logout removes the player link, without performing a manual hatch exit. */
    public static boolean retainSeatStateOnLogoutR54(Entity passenger,EntryPlugCarrierEntity plug)
    {
        if(!(passenger instanceof ServerPlayer player)||!plug.getUUID().equals(DISCONNECT_SEATS_R54.get(player)))return false;
        DISCONNECT_SEATS_R54.remove(player);return true;
    }

    public static boolean resumeSavedSeatR54(ServerPlayer player)
    {
        var saved=player.getPersistentData().getCompound(SAVED_SEAT_R54);
        if(player.isPassenger())return false;
        var fleet=EvaFleetSavedData.get(player.getServer()).entry(saved.getInt("Variant")).orElse(null);
        if(!saved.hasUUID("Player")||!saved.getUUID("Player").equals(player.getUUID())||!saved.hasUUID("Seat")
                ||fleet==null||!saved.getUUID("Seat").equals(fleet.entryPlugId())
                ||!saved.getString("Dimension").equals(player.serverLevel().dimension().location().toString()))
        {player.getPersistentData().remove(SAVED_SEAT_R54);return false;}
        SEAT_RESTORE_R54.put(player,player.tickCount+200);
        tryResumeSeatR54(player);return true;
    }

    private static void tryResumeSeatR54(ServerPlayer player)
    {
        var saved=player.getPersistentData().getCompound(SAVED_SEAT_R54);var level=player.serverLevel();
        if(player.isPassenger()||!saved.hasUUID("Seat")||!saved.hasUUID("Player")
                ||!saved.getUUID("Player").equals(player.getUUID())
                ||!saved.getString("Dimension").equals(level.dimension().location().toString()))
        {SEAT_RESTORE_R54.remove(player);return;}
        var actor=saved.hasUUID("Seat")?level.getEntity(saved.getUUID("Seat")):null;
        if(actor instanceof EntryPlugCarrierEntity plug&&worldOwnedVehicleR54(plug)&&plug.isAlive())
        {
            SEAT_RESTORE_R54.remove(player);
            if(!plug.isVehicle()&&!player.isPassenger()&&player.startRiding(plug,true))
            {plug.syncPilotPositionNow();rememberSeatR54(player,plug);}
            else if(player.getVehicle()!=plug)player.getPersistentData().remove(SAVED_SEAT_R54);
            return;
        }
        if(player.isPassenger()||player.tickCount>=SEAT_RESTORE_R54.getOrDefault(player,0))
        {SEAT_RESTORE_R54.remove(player);return;}
        // The reference can only name this player's existing canonical seat.
        // Vanilla's short ticket expires; it does not create an entity.
        level.getChunkSource().addRegionTicket(net.minecraft.server.level.TicketType.POST_TELEPORT,
                new net.minecraft.world.level.ChunkPos(saved.getInt("ChunkX"),saved.getInt("ChunkZ")),2,player.getId());
    }

    @SubscribeEvent public static void resumeSeatTickR54(net.minecraftforge.event.TickEvent.PlayerTickEvent event)
    {
        if(event.phase==net.minecraftforge.event.TickEvent.Phase.END&&event.player instanceof ServerPlayer player
                &&player.tickCount%5==0&&SEAT_RESTORE_R54.containsKey(player))tryResumeSeatR54(player);
    }

    public static <T> T originalOnly(UUID original,Function<UUID,T> lookup,Predicate<T> valid)
    {if(original==null)return null;T actor=lookup.apply(original);return actor!=null&&valid.test(actor)?actor:null;}
    static boolean holdDismount(boolean managed,boolean alive,boolean mounting,boolean verifiedAnchor)
    {return managed&&alive&&!mounting&&!verifiedAnchor;}
    public static boolean mappedPersonnel(ServerLevel level)
    {return personnelAccess(level)!=null;}
    public static boolean managed(EntryPlugCarrierEntity plug)
    {return plug.laboratorySlotR47()<0&&!plug.isIndependentUNPlug()&&plug.getAssignedVariant()>=0&&plug.getAssignedVariant()<3
            &&plug.level() instanceof ServerLevel level&&NervRouteRuntimeR52.claimed(level);}
    private static Access plugAccess(ServerLevel level)
    {var owner=NervRouteRuntimeR52.originalActorAccess(level);return owner!=null&&NervRouteRuntimeR52.ready(level)&&owner.originalEntryPlugBindingsReady(level)?owner:null;}
    private static Access personnelAccess(ServerLevel level)
    {var owner=NervRouteRuntimeR52.originalActorAccess(level);return owner!=null&&NervRouteRuntimeR52.personnelBindingsReady(level)?owner:null;}
    private static boolean original(ServerLevel level,EntryPlugCarrierEntity plug)
    {var fleet=EvaFleetSavedData.get(level.getServer()).entry(plug.getAssignedVariant()).orElse(null);return fleet!=null&&plug.isAlive()
            &&plug.level()==level&&plug.getUUID().equals(fleet.entryPlugId());}
    private static boolean originalUnit(ServerLevel level,int variant,EvaUnit01Entity eva)
    {var fleet=EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);return fleet!=null&&eva!=null&&eva.isAlive()&&eva.level()==level
            &&!eva.isExperimentalUnit()&&eva.getUnitVariant()==variant&&eva.getUUID().equals(fleet.canonicalId());}
    private static Vec3 finite(Vec3 point)
    {return point!=null&&Double.isFinite(point.x)&&Double.isFinite(point.y)&&Double.isFinite(point.z)?point:null;}
    public static Vec3 boardingAnchor(ServerLevel level,EntryPlugCarrierEntity plug)
    {var owner=plugAccess(level);return owner!=null&&original(level,plug)?finite(owner.originalBoardingAnchor(level,plug)):null;}
    public static Vec3 dismountAnchor(ServerLevel level,EntryPlugCarrierEntity plug,LivingEntity passenger)
    {
        var owner=plugAccess(level);var point=owner!=null&&original(level,plug)&&passenger.level()==level?finite(owner.originalDismountAnchor(level,plug,passenger)):null;
        return point!=null&&level.hasChunkAt(net.minecraft.core.BlockPos.containing(point))&&TrainingPilotDirector.safeActualFeetR47(level,point)
                &&level.noCollision(passenger,passenger.getBoundingBox().move(point.subtract(passenger.position())))?point:null;
    }
    public static RigidTransform dockPose(ServerLevel level,int variant)
    {var owner=plugAccess(level);var pose=owner==null?null:owner.originalDockPose(level,variant);return pose!=null&&finite(pose.translation())!=null
            &&Float.isFinite(pose.qx())&&Float.isFinite(pose.qy())&&Float.isFinite(pose.qz())&&Float.isFinite(pose.qw())?pose:null;}
    public static RigidTransform bayPose(ServerLevel level,int variant)
    {var owner=NervRouteRuntimeR52.originalActorAccess(level);return owner==null?null:owner.originalBayPose(level,variant);}
    public static boolean boardingAllowed(ServerLevel level,EntryPlugCarrierEntity plug,Entity passenger)
    {var owner=plugAccess(level);return owner!=null&&original(level,plug)&&passenger.level()==level&&owner.originalBoardingAllowed(level,plug,passenger)&&boardingAnchor(level,plug)!=null;}
    public static boolean riderUpdatesAllowed(ServerLevel level,EntryPlugCarrierEntity plug)
    {return plugAccess(level)!=null&&original(level,plug);}
    public static boolean riderPositionUpdatesAllowed(ServerLevel level,EntryPlugCarrierEntity plug,Entity passenger)
    {
        if(!original(level,plug)||passenger.getVehicle()!=plug||plug.getFirstPassenger()!=passenger)return false;
        // An already locked original ride chain must follow its moving EVA
        // while another unit or the plant is still restoring. This admits
        // seat updates only; hatch, boarding and dismount still need the owner.
        var eva=plug.getLinkedEva();
        if(plug.isLockedToEva()&&originalUnit(level,plug.getAssignedVariant(),eva)
                &&plug.getVehicle()==eva&&eva.getLockedEntryPlug()==plug)return true;
        return plugAccess(level)!=null;
    }
    public static boolean launchLock(ServerLevel level,int variant,EvaUnit01Entity eva,EntryPlugCarrierEntity plug)
    {var owner=plugAccess(level);return owner!=null&&originalUnit(level,variant,eva)&&plug!=null&&original(level,plug)&&owner.originalLaunchLock(level,variant,eva,plug);}
    public static boolean cageDock(ServerLevel level,int variant,EvaUnit01Entity eva,EntryPlugCarrierEntity plug)
    {var owner=plugAccess(level);return owner!=null&&originalUnit(level,variant,eva)&&plug!=null&&original(level,plug)&&owner.originalCageDock(level,variant,eva,plug);}
    public static boolean requestEjection(ServerLevel level,int variant,EvaUnit01Entity eva,LivingEntity pilot)
    {var owner=plugAccess(level);var plug=eva==null?null:eva.getLockedEntryPlug();return owner!=null&&originalUnit(level,variant,eva)&&plug!=null&&original(level,plug)
            &&pilot!=null&&pilot.isAlive()&&pilot.level()==level&&plug.getFirstPassenger()==pilot&&owner.requestOriginalEjection(level,variant,eva,pilot);}
    public static void tickPlug(ServerLevel level,EntryPlugCarrierEntity plug)
    {var owner=plugAccess(level);if(owner!=null&&original(level,plug))owner.maintainOriginalCapsule(level,plug);}
    public static boolean originalSeatAllowed(ServerLevel level,com.projectseele.entity.NervCommandSeatEntity seat,TrainingPilotEntity pilot)
    {var owner=personnelAccess(level);return owner!=null&&pilot.level()==level&&pilot.isAlive()&&owner.originalSeatAllowed(level,seat,pilot);}
    public static Vec3 originalSeatStand(ServerLevel level,com.projectseele.entity.NervCommandSeatEntity seat,TrainingPilotEntity pilot)
    {var owner=personnelAccess(level);var at=owner==null?null:finite(owner.originalSeatStand(level,seat,pilot));return at!=null&&TrainingPilotDirector.safeActualFeetR47(level,at)&&level.noCollision(pilot,pilot.getDimensions(net.minecraft.world.entity.Pose.STANDING).makeBoundingBox(at))?at:null;}
    public static TrainingPilotEntity pilot(ServerLevel level,int variant)
    {var owner=personnelAccess(level);var pilot=owner==null?null:owner.originalPilot(level,variant);return pilot!=null&&pilot.level()==level&&pilot.isAlive()&&pilot.getAssignedVariant()==variant?pilot:null;}
    public static void retainPilot(ServerLevel level,int variant)
    {var owner=personnelAccess(level);if(owner!=null)owner.retainOriginalPilotSections(level,variant);}
    public static List<NervStaffDirector.Station> roster(ServerLevel level)
    {var owner=personnelAccess(level);return owner==null?List.of():List.copyOf(owner.originalStaffRoster(level));}
    public static void tickStaff(ServerLevel level)
    {var owner=personnelAccess(level);if(owner!=null)owner.maintainOriginalStaff(level);}
    @SubscribeEvent public static void mount(EntityMountEvent event)
    {
        if(!(event.getEntityBeingMounted() instanceof EntryPlugCarrierEntity plug)||!managed(plug)
                ||!(plug.level() instanceof ServerLevel level))return;
        Entity passenger=event.getEntityMounting();if(!passenger.isAlive()||passenger.isRemoved())return;
        if(!event.isMounting()&&passenger instanceof ServerPlayer player
                &&plug.getUUID().equals(DISCONNECT_SEATS_R54.get(player)))return;
        if(plug.getPersistentData().getBoolean("AdministrativeResetR53"))return;
        // Vanilla restores saved passenger graphs with forced startRiding at load,
        // before Root installs its owner. New boarding is gated in the capsule API.
        boolean safe=event.isMounting()||passenger instanceof LivingEntity living&&dismountAnchor(level,plug,living)!=null;
        if(holdDismount(true,true,event.isMounting(),safe))
        {event.setCanceled(true);}
    }
}
