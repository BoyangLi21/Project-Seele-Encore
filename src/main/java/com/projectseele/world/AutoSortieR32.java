package com.projectseele.world;

import com.projectseele.entity.*;
import net.minecraft.server.level.*;
import net.minecraft.world.level.ChunkPos;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;

/** Active mission boarding arms a job; every physical press rechecks the mission. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class AutoSortieR32
{
    private static final TicketType<ChunkPos> TICKET=TicketType.create("auto_sortie_r32",Comparator.comparingLong(ChunkPos::toLong),100);
    private static final Map<ServerLevel,Map<Integer,String>> BLOCKED=new WeakHashMap<>();
    public static String missionToken(ServerLevel level)
    {
        var mission=TvCampaignSavedData.get(level);
        return mission.active.isEmpty()||Set.of("cancel","failure","combat_victory","episode_archived").contains(mission.phase)
                ||mission.targetDeathConfirmedR45||mission.owner==null?""
                :mission.active+":"+mission.generationR43+":"+mission.owner;
    }
    public static boolean cancellationCurrentR45(boolean canceled,String acceptedMission,String mission)
    {return canceled&&!mission.isEmpty()&&mission.equals(acceptedMission);}
    static boolean assignedPilotR45(ServerLevel level,int unit,net.minecraft.world.entity.Entity pilot)
    {
        var assignment=TvCampaignSavedData.get(level).sorties.get(unit);if(assignment==null||pilot==null||!pilot.isAlive())return false;
        if(TvSortiesR32.assignedUnit(level,assignment)==null)return false;
        return assignment.pilotR45!=null&&assignment.pilotR45.equals(pilot.getUUID())
                &&(pilot instanceof TrainingPilotEntity npc?assignment.npc&&npc.getAssignedVariant()==unit
                :pilot instanceof ServerPlayer player&&!assignment.npc&&player.getUUID().equals(assignment.commander));
    }
    public static boolean automaticAllowed(ServerLevel level,int unit)
    {return automaticBlockerR50(level,unit).isEmpty();}
    private static String automaticBlockerR50(ServerLevel level,int unit)
    {
        if(StaffRecoveryR47.pending(level,unit))return "original_recovery_pending";
        String token=missionToken(level);var eva=EvaLogisticsDirector.canonicalUnit(level,unit);
        if(token.isEmpty())return "no_live_mission";
        if(eva==null)return "original_airframe_not_loaded";
        if(UndergroundSortieR48.reservesLaunchR48(level,unit,eva))return "underground_sortie_reserves_launch";
        var plug=EntryPlugDirector.canonical(level,unit);
        var pilot=plug==null?null:plug.getFirstPassenger();if(pilot==null&&eva!=null)pilot=eva.getPilotEntity();
        String boarding=boardingBlockerR50(level,unit,eva,plug,pilot);if(!boarding.isEmpty())return boarding;
        if(eva.getPersistentData().getBoolean("R32AutoCancelled"))return "automatic_cancel_receipt_present";
        return token.equals(eva.getPersistentData().getString("R43AutoMission"))?"":"accepted_mission_token_mismatch";
    }
    /** PREPARE starts with an occupied original docked plug, before a host ride link exists. */
    private static String boardingBlockerR50(ServerLevel level,int unit,EvaUnit01Entity eva,
            EntryPlugCarrierEntity plug,net.minecraft.world.entity.Entity pilot)
    {
        if(eva==null||plug==null||pilot==null)return "waiting_original_airframe_capsule_or_pilot";
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(unit).orElse(null);
        if(fleet==null||!fleet.canonicalId().equals(eva.getUUID())||!plug.getUUID().equals(fleet.entryPlugId())
                ||plug.getAssignedVariant()!=unit||!assignedPilotR45(level,unit,pilot))return "original_fleet_or_assigned_pilot_mismatch";
        if(plug.getFirstPassenger()!=pilot||pilot.getVehicle()!=plug)return "pilot_not_in_original_capsule";
        if(!plug.isHatchFullySealed())return "original_hatch_not_sealed";
        if(pilot instanceof TrainingPilotEntity npc&&!seatedStage(npc))return "original_npc_not_seated";
        if(plug.isLockedToEva()&&plug.getVehicle()==eva&&plug.getLinkedEva()==eva)return "";
        if(fleet.phase()==EvaFleetSavedData.Phase.PARKED&&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_OCCUPIED
                &&EntryPlugDirector.originalCageDockR50(level,unit,eva,plug))return "";
        return "capsule_not_at_original_occupied_dock_or_locked_socket";
    }
    private static void blocked(ServerLevel level,int unit,String reason)
    {
        var mission=TvCampaignSavedData.get(level);if(!mission.sorties.containsKey(unit))return;
        String key=missionToken(level)+":"+reason;
        var states=BLOCKED.computeIfAbsent(level,ignored->new HashMap<>());
        if(key.equals(states.put(unit,key)))return;
        var eva=EvaLogisticsDirector.canonicalUnit(level,unit);var plug=EntryPlugDirector.canonical(level,unit);
        var pilot=plug==null?null:plug.getFirstPassenger();
        com.projectseele.ProjectSeele.LOGGER.info("AUTO SORTIE held unit={} mission={} reason={} phase={} eva={} plug={} plugStage={} pilot={} linkedEva={}",
                unit,missionToken(level),reason,EvaLogisticsDirector.status(level,unit).phase(),eva==null?null:eva.getUUID(),
                plug==null?null:plug.getUUID(),plug==null?-1:plug.getInsertionStage(),pilot==null?null:pilot.getUUID(),
                plug==null||plug.getLinkedEva()==null?null:plug.getLinkedEva().getUUID());
    }
    public static void clearAutomatic(ServerLevel level,int unit)
    {
        StaffCommandBookR24.cancelAutomatic(level,unit);
        var eva=EvaLogisticsDirector.canonicalUnit(level,unit);if(eva==null)return;
        var tag=eva.getPersistentData();tag.remove("R32AutoStep");tag.remove("R32AutoNext");tag.remove("R43AutoMission");
    }
    /** Historical delegation ends only after actual return/boarding and every live original lease has closed. */
    private static boolean originalLeaseFreeR50(ServerLevel level,EvaUnit01Entity eva)
    {
        int unit=eva.getUnitVariant();var fleet=EvaFleetSavedData.get(level.getServer()).entry(unit).orElse(null);
        if(eva.isExperimentalUnit()||unit<0||unit>2||fleet==null||!fleet.canonicalId().equals(eva.getUUID())
                ||EvaLogisticsDirector.canonicalUnit(level,unit)!=eva||!eva.isAlive()||eva.isFirstBattleActive()
                ||EvaShutdownR30.wreck(eva)||EvaBayRepairR33.active(eva)||EvaAirTransportR31.active(eva)
                ||NervAirLiftR30.originalJobPendingR50(level,eva)||StaffRecoveryR47.pending(level,unit)||PilotReturnR39.pending(level,unit)
                ||StaffCommandBookR24.unitOrder(level,unit)!=null||StaffPilotOrdersR25.pending(level).stream().anyMatch(p->p.unit()==unit)
                ||!TvCampaignSavedData.get(level).active.isEmpty()||ArmedSortieSavedDataR48.get(level).selection(unit)!=null
                ||TvMissionEquipmentR45.originalCargoOutstandingR50(eva))return false;
        var first=FirstBattleSavedData.get(level);
        if(first.active!=null||first.missionOwner!=null)return false;
        var vaults=level.getDataStorage().get(EquipmentVaultsR47.State::load,"projectseele_equipment_vaults_r47");
        return vaults==null||!vaults.loans.containsValue(eva.getUUID());
    }
    private static void endHistoricalDelegationR50(EvaUnit01Entity eva)
    {
        var tag=eva.getPersistentData();
        for(String key:List.of("R32SortieCommander","R32BoardingPilot","R32AutoCancelled","R32AutoStep","R32AutoNext","R43AutoMission",
                "R49RecoveryOwner","R49EjectedPilot","R49EjectedPlug"))tag.remove(key);
    }
    /** Empty recovered originals release the old commander's receipt, without changing any actor or inventory. */
    public static boolean releaseRecoveredDelegationR50(ServerLevel level,EvaUnit01Entity eva)
    {
        if(!originalLeaseFreeR50(level,eva))return false;int unit=eva.getUnitVariant();
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(unit).orElse(null);var plug=EntryPlugDirector.canonical(level,unit);
        if(fleet==null||fleet.phase()!=EvaFleetSavedData.Phase.PARKED||eva.getPilotEntity()!=null||plug==null||plug.isVehicle()
                ||!EntryPlugDirector.originalCageDockR50(level,unit,eva,plug)
                ||plug.getInsertionStage()!=EntryPlugCarrierEntity.STAGE_SUSPENDED||eva.isLaunchSequenceActive()
                ||!EvaLogisticsDirector.inAssignedHangarR33(level,eva)||!EvaLogisticsDirector.recoveryMotionSettled(eva))return false;
        var tag=eva.getPersistentData();
        if(!tag.hasUUID("R32SortieCommander")&&!tag.hasUUID("R32BoardingPilot")&&!tag.hasUUID("R49RecoveryOwner"))return false;
        var former=tag.hasUUID("R32SortieCommander")?tag.getUUID("R32SortieCommander"):null;endHistoricalDelegationR50(eva);
        com.projectseele.ProjectSeele.LOGGER.info("R50 original recovered delegation ended: eva={} formerCommander={}",eva.getUUID(),former);return true;
    }
    /** Explicit authorized recovery of the same empty faulted assembly ends only its completed prior lease. */
    public static boolean releaseEmptyFaultBayDelegationR50(ServerPlayer caller,EvaUnit01Entity eva)
    {
        var level=caller.serverLevel();
        if(!NervStaffDialogue.authorized(caller)||!originalLeaseFreeR50(level,eva)
                ||!EvaLogisticsDirector.emptyFaultBayRecoveryReadyR50(level,eva))return false;
        endHistoricalDelegationR50(eva);return true;
    }
    /** Positive canonical passenger proof also migrates an inherited, still-locked preparation receipt. */
    public static boolean acceptOriginalHumanBoardingR50(ServerLevel level,EvaUnit01Entity eva,ServerPlayer player)
    {
        if(player.level()!=level||!NervStaffDialogue.authorized(player)||!originalLeaseFreeR50(level,eva))return false;
        int unit=eva.getUnitVariant();var fleet=EvaFleetSavedData.get(level.getServer()).entry(unit).orElse(null);
        var plug=EntryPlugDirector.canonical(level,unit);
        if(fleet==null||plug==null||fleet.entryPlugId()==null||!fleet.entryPlugId().equals(plug.getUUID())
                ||plug.getLinkedEva()!=null&&plug.getLinkedEva()!=eva||plug.getAssignedVariant()!=unit||plug.getFirstPassenger()!=player
                ||plug.getPassengers().size()!=1||player.getVehicle()!=plug)return false;
        boolean docked=fleet.phase()==EvaFleetSavedData.Phase.PARKED&&EvaLogisticsDirector.inAssignedHangarR33(level,eva)
                &&EvaLogisticsDirector.recoveryMotionSettled(eva)&&!eva.isLaunchSequenceActive()
                &&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_OCCUPIED&&EntryPlugDirector.originalCageDockR50(level,unit,eva,plug);
        boolean prepared=fleet.phase()==EvaFleetSavedData.Phase.SILO_READY&&eva.getPilotEntity()==player
                &&plug.getLinkedEva()==eva&&EntryPlugDirector.hasLaunchLock(level,unit,eva)&&eva.getLaunchPhase()==EvaUnit01Entity.LAUNCH_LOCKED
                &&!eva.isLaunchCommandReleased()&&!eva.hasActiveCarrierMotion();
        if(!docked&&!prepared)return false;
        var tag=eva.getPersistentData();
        if(tag.hasUUID("R32SortieCommander")&&player.getUUID().equals(tag.getUUID("R32SortieCommander"))
                &&tag.hasUUID("R32BoardingPilot")&&player.getUUID().equals(tag.getUUID("R32BoardingPilot")))return false;
        var former=tag.hasUUID("R32SortieCommander")?tag.getUUID("R32SortieCommander"):null;endHistoricalDelegationR50(eva);
        tag.putUUID("R32SortieCommander",player.getUUID());tag.putUUID("R32BoardingPilot",player.getUUID());
        com.projectseele.ProjectSeele.LOGGER.info("R50 original human delegation accepted: eva={} plug={} pilot={} formerCommander={} phase={}",
                eva.getUUID(),plug.getUUID(),player.getUUID(),former,fleet.phase());return true;
    }
    private static boolean seatedStage(TrainingPilotEntity pilot)
    {
        int stage=pilot.getTrainingStage();
        return stage==TrainingPilotEntity.STAGE_IN_PLUG||stage==TrainingPilotEntity.STAGE_LINKED;
    }
    /** Selection/cancellation invalidate queued physical presses immediately, before the next staff tick. */
    public static void invalidateMission(ServerLevel level)
    {
        for(int unit=0;unit<3;unit++)clearAutomatic(level,unit);
        StaffCommandBookR24.cancelMissionActions(level);
        StaffPilotOrdersR25.invalidateMission(level);
    }
    public static void suspendAutomaticForRecovery(ServerLevel level,int unit)
    {
        clearAutomatic(level,unit);
        var eva=EvaLogisticsDirector.canonicalUnit(level,unit);if(eva==null)return;
        eva.getPersistentData().putBoolean("R32AutoCancelled",true);
        eva.getPersistentData().putString("R43AutoMission",missionToken(level));
    }
    public static void assignCommander(EvaUnit01Entity eva,ServerPlayer player)
    {if(eva!=null)eva.getPersistentData().putUUID("R32SortieCommander",player.getUUID());}
    public static void cancel(ServerPlayer player,int unit)
    {
        var level=player.serverLevel();
        for(int i=0;i<3;i++)if(unit<0||i==unit)
        {
            var e=EvaLogisticsDirector.canonicalUnit(level,i);if(e==null)continue;var tag=e.getPersistentData();
            if(player.hasPermissions(2)||tag.hasUUID("R32SortieCommander")&&player.getUUID().equals(tag.getUUID("R32SortieCommander")))
            {
                tag.putString("R43AutoMission",missionToken(level));
                tag.putBoolean("R32AutoCancelled",true);
                StaffCommandBookR24.cancelAutomatic(level,i);
            }
        }
    }
    private static NervStaffEntity officer(ServerLevel level,String skin)
    {
        var post=NervStaffDirector.roster(level).stream().filter(p->p.skin().equals(skin)).findFirst().orElse(null);if(post==null)return null;
        var c=new ChunkPos(post.feet());level.getChunkSource().addRegionTicket(TICKET,c,3,c);level.getChunk(post.feet());
        var id=NervStaffSavedData.get(level).identity(post.id());return id!=null&&level.getEntity(id) instanceof NervStaffEntity npc?npc:null;
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()%5!=0)return;
        var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        for(int unit=0;unit<3;unit++)
        {
            var eva=EvaLogisticsDirector.canonicalUnit(level,unit);if(eva==null)continue;
            String mission=missionToken(level);
            if(mission.isEmpty())
            {
                var states=BLOCKED.get(level);if(states!=null)states.remove(unit);
                clearAutomatic(level,unit);releaseRecoveredDelegationR50(level,eva);
                var originalPlug=EntryPlugDirector.canonical(level,unit);
                if(originalPlug!=null&&originalPlug.getFirstPassenger() instanceof ServerPlayer actual)
                    acceptOriginalHumanBoardingR50(level,eva,actual);
                continue;
            }
            if(StaffRecoveryR47.pending(level,unit)){blocked(level,unit,"original_recovery_pending");StaffCommandBookR24.cancelAutomatic(level,unit);continue;}
            var tag=eva.getPersistentData();var plug=EntryPlugDirector.canonical(level,unit);
            var pilot=plug==null?null:plug.getFirstPassenger();if(pilot==null)pilot=eva.getPilotEntity();
            String phase=EvaLogisticsDirector.status(level,unit).phase();
            // A delayed boarding must not undo a cancellation of this mission.
            if(cancellationCurrentR45(tag.getBoolean("R32AutoCancelled"),tag.getString("R43AutoMission"),mission))
            {blocked(level,unit,"this_mission_was_canceled");StaffCommandBookR24.cancelAutomatic(level,unit);continue;}
            if(pilot==null)
            {
                blocked(level,unit,"waiting_actual_boarding");
                if(phase.equals("PARKED")){tag.remove("R32BoardingPilot");tag.remove("R32AutoStep");}
                continue;
            }
            if(!assignedPilotR45(level,unit,pilot)){blocked(level,unit,"assigned_pilot_mismatch");clearAutomatic(level,unit);continue;}
            // Boarding acceptance is a walking order. Wait for the same pilot
            // in the canonical plug and the actual pressure hatch to finish closing.
            String boarding=boardingBlockerR50(level,unit,eva,plug,pilot);
            if(!boarding.isEmpty()){blocked(level,unit,boarding);continue;}
            if(Set.of("PARKED","SILO_READY").contains(phase)&&(!tag.hasUUID("R32BoardingPilot")||!tag.getUUID("R32BoardingPilot").equals(pilot.getUUID())
                    ||!mission.equals(tag.getString("R43AutoMission"))))
            {
                StaffCommandBookR24.cancelAutomatic(level,unit);tag.putString("R43AutoMission",mission);
                tag.putUUID("R32BoardingPilot",pilot.getUUID());tag.putString("R32AutoStep","prepare");tag.remove("R32AutoCancelled");tag.remove("R32AutoNext");
                tag.putUUID("R32SortieCommander",TvCampaignSavedData.get(level).sorties.get(unit).commander);
            }
            if(UndergroundSortieR48.reservesLaunchR48(level,unit,eva))
            {blocked(level,unit,"underground_sortie_reserves_launch");StaffCommandBookR24.cancelAutomatic(level,unit);continue;}
            if(tag.getBoolean("R32AutoCancelled")){blocked(level,unit,"automatic_cancel_receipt_present");StaffCommandBookR24.cancelAutomatic(level,unit);continue;}
            String automatic=automaticBlockerR50(level,unit);
            if(!automatic.isEmpty()){blocked(level,unit,automatic);clearAutomatic(level,unit);continue;}
            if(!tag.contains("R32AutoStep")||tag.getBoolean("R32AutoCancelled")||!tag.hasUUID("R32SortieCommander"))continue;
            if(EvaShutdownR30.wreck(eva)||eva.getHealth()<=0)
            {
                tag.putBoolean("R32AutoCancelled",true);
                var commander=level.getServer().getPlayerList().getPlayer(tag.getUUID("R32SortieCommander"));
                if(commander!=null)NervStaffDialogue.say(commander,"赤木律子 · 整备通信",NervStaffDialogue.unitName(unit)+"还有损伤，不能接入。先修复机体，再重新登机。");
                continue;
            }
            if(phase.equals("DEPLOYED")){tag.remove("R32AutoStep");continue;}
            if(tag.getString("R32AutoStep").equals("launch_accepted"))continue;
            if(phase.equals("PLUG_FAULT")||phase.contains("ABORT")||Set.of("DESCENDING","TO_HANGAR","FILLING").contains(phase))
            {tag.putBoolean("R32AutoCancelled",true);continue;}
            if(!Set.of("PARKED","SILO_READY").contains(phase)||level.getGameTime()<tag.getLong("R32AutoNext"))continue;
            var caller=level.getServer().getPlayerList().getPlayer(tag.getUUID("R32SortieCommander"));
            if(caller==null||caller.level()!=level||!NervStaffDialogue.authorized(caller))
            {blocked(level,unit,"commander_offline_outside_dimension_or_not_authorized");continue;}
            if(StaffCommandBookR24.unitOrder(level,unit)!=null){blocked(level,unit,"existing_original_operator_order");continue;}
            String operation=phase.equals("PARKED")?"prepare":"launch";
            var actor=officer(level,operation.equals("prepare")?"ritsuko":"misato");
            if(actor==null){blocked(level,unit,"original_posted_officer_unavailable_"+operation);continue;}
            if(actor.busy()||StaffCommandBookR24.order(actor)!=null){blocked(level,unit,"original_posted_officer_busy_"+operation);continue;}
            tag.putLong("R32AutoNext",level.getGameTime()+100);
            if(StaffCommandBookR24.request(caller,actor,operation,unit)>0)
            {
                var blockedStates=BLOCKED.get(level);if(blockedStates!=null)blockedStates.remove(unit);
                var order=StaffCommandBookR24.unitOrder(level,unit);if(order!=null)order.automatic=true;
                tag.putString("R32AutoStep",operation);
                com.projectseele.ProjectSeele.LOGGER.info("AUTO SORTIE unit={} pilot={} operator={} operation={}",unit,pilot.getUUID(),actor.skin(),operation);
            }
            else blocked(level,unit,"original_physical_order_request_refused_"+operation);
        }
    }
    private AutoSortieR32(){}
}
