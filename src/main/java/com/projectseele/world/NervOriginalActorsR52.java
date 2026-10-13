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
    public static boolean boardingAllowed(ServerLevel level,EntryPlugCarrierEntity plug,Entity passenger)
    {var owner=plugAccess(level);return owner!=null&&original(level,plug)&&passenger.level()==level&&owner.originalBoardingAllowed(level,plug,passenger)&&boardingAnchor(level,plug)!=null;}
    public static boolean riderUpdatesAllowed(ServerLevel level,EntryPlugCarrierEntity plug)
    {return plugAccess(level)!=null&&original(level,plug);}
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
        // Vanilla restores saved passenger graphs with forced startRiding at load,
        // before Root installs its owner. New boarding is gated in the capsule API.
        boolean safe=event.isMounting()||passenger instanceof LivingEntity living&&dismountAnchor(level,plug,living)!=null;
        if(holdDismount(true,true,event.isMounting(),safe))
        {event.setCanceled(true);}
    }
}
