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
    {
        if(StaffRecoveryR47.pending(level,unit))return false;
        String token=missionToken(level);var eva=EvaLogisticsDirector.canonicalUnit(level,unit);
        var plug=EntryPlugDirector.canonical(level,unit);
        var pilot=plug==null?null:plug.getFirstPassenger();if(pilot==null&&eva!=null)pilot=eva.getPilotEntity();
        boolean occupied=assignedPilotR45(level,unit,pilot)
                &&plug!=null&&plug.getAssignedVariant()==unit&&plug.getLinkedEva()==eva
                &&plug.getFirstPassenger()==pilot&&plug.isHatchFullySealed()
                &&(!(pilot instanceof TrainingPilotEntity npc)||seatedStage(npc));
        return !token.isEmpty()&&eva!=null&&!eva.getPersistentData().getBoolean("R32AutoCancelled")
                &&occupied
                &&token.equals(eva.getPersistentData().getString("R43AutoMission"));
    }
    public static void clearAutomatic(ServerLevel level,int unit)
    {
        StaffCommandBookR24.cancelAutomatic(level,unit);
        var eva=EvaLogisticsDirector.canonicalUnit(level,unit);if(eva==null)return;
        var tag=eva.getPersistentData();tag.remove("R32AutoStep");tag.remove("R32AutoNext");tag.remove("R43AutoMission");
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
            if(mission.isEmpty()){clearAutomatic(level,unit);continue;}
            if(StaffRecoveryR47.pending(level,unit)){StaffCommandBookR24.cancelAutomatic(level,unit);continue;}
            var tag=eva.getPersistentData();var plug=EntryPlugDirector.canonical(level,unit);
            var pilot=plug==null?null:plug.getFirstPassenger();if(pilot==null)pilot=eva.getPilotEntity();
            String phase=EvaLogisticsDirector.status(level,unit).phase();
            // A delayed boarding must not undo a cancellation of this mission.
            if(cancellationCurrentR45(tag.getBoolean("R32AutoCancelled"),tag.getString("R43AutoMission"),mission))
            {StaffCommandBookR24.cancelAutomatic(level,unit);continue;}
            if(pilot==null)
            {
                if(phase.equals("PARKED")){tag.remove("R32BoardingPilot");tag.remove("R32AutoStep");}
                continue;
            }
            if(!assignedPilotR45(level,unit,pilot)){clearAutomatic(level,unit);continue;}
            // Boarding acceptance is a walking order. Wait for the same pilot
            // in the canonical plug and the actual pressure hatch to finish closing.
            if(plug==null||plug.getFirstPassenger()!=pilot||plug.getLinkedEva()!=eva||!plug.isHatchFullySealed()
                    ||pilot instanceof TrainingPilotEntity npc&&!seatedStage(npc))continue;
            if(Set.of("PARKED","SILO_READY").contains(phase)&&(!tag.hasUUID("R32BoardingPilot")||!tag.getUUID("R32BoardingPilot").equals(pilot.getUUID())
                    ||!mission.equals(tag.getString("R43AutoMission"))))
            {
                StaffCommandBookR24.cancelAutomatic(level,unit);tag.putString("R43AutoMission",mission);
                tag.putUUID("R32BoardingPilot",pilot.getUUID());tag.putString("R32AutoStep","prepare");tag.remove("R32AutoCancelled");tag.remove("R32AutoNext");
                tag.putUUID("R32SortieCommander",TvCampaignSavedData.get(level).sorties.get(unit).commander);
            }
            if(tag.getBoolean("R32AutoCancelled")){StaffCommandBookR24.cancelAutomatic(level,unit);continue;}
            if(!automaticAllowed(level,unit)){clearAutomatic(level,unit);continue;}
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
            if(caller==null||caller.level()!=level||!NervStaffDialogue.authorized(caller))continue;
            if(StaffCommandBookR24.unitOrder(level,unit)!=null)continue;
            String operation=phase.equals("PARKED")?"prepare":"launch";
            var actor=officer(level,operation.equals("prepare")?"ritsuko":"misato");
            if(actor==null||actor.busy()||StaffCommandBookR24.order(actor)!=null)continue;
            tag.putLong("R32AutoNext",level.getGameTime()+100);
            if(StaffCommandBookR24.request(caller,actor,operation,unit)>0)
            {
                var order=StaffCommandBookR24.unitOrder(level,unit);if(order!=null)order.automatic=true;
                tag.putString("R32AutoStep",operation);
                com.projectseele.ProjectSeele.LOGGER.info("AUTO SORTIE unit={} pilot={} operator={} operation={}",unit,pilot.getUUID(),actor.skin(),operation);
            }
        }
    }
    private AutoSortieR32(){}
}
