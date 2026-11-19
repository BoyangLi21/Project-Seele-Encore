package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervStaffEntity;
import com.projectseele.entity.TrainingPilotEntity;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;

/** Dispatch waits for the existing remote airframe; it never replaces a pilot. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class StaffPilotOrdersR25
{
    private record Order(UUID caller, UUID officer, int unit, long deadline, boolean standby, String mission) {}
    public enum Cancellation { NONE, CANCELED, DENIED }
    public record Pending(UUID caller, UUID officer, int unit, long deadline, boolean standby) {}
    private static final Map<ServerLevel, Map<Integer,Order>> ORDERS = new WeakHashMap<>();
    public static boolean missionContextCurrentR45(String accepted,String current)
    {return accepted.equals(current);}
    public static List<Pending> pending(ServerLevel level)
    {
        return ORDERS.getOrDefault(level,Map.of()).values().stream()
                .map(job->new Pending(job.caller(),job.officer(),job.unit(),job.deadline(),job.standby())).toList();
    }
    public static void invalidateMission(ServerLevel level)
    {
        var jobs=ORDERS.get(level);if(jobs==null)return;
        // Explicit safe leave-plug/standby orders remain valid. Mission-bound
        // boarding that has not reached the native dispatcher cannot run late.
        jobs.values().removeIf(job->!job.standby()&&!job.mission().isEmpty());
    }
    public static Cancellation cancel(ServerPlayer player,NervStaffEntity npc,int unit)
    {
        var jobs=ORDERS.get(player.serverLevel());if(jobs==null)return Cancellation.NONE;
        var selected=jobs.values().stream().filter(job->job.officer().equals(npc.getUUID())
                &&(unit<0||job.unit()==unit)).toList();
        if(selected.isEmpty())return Cancellation.NONE;
        if(!NervStaffDialogue.authorized(player)||!StaffAuthorityR25.allows(npc,"board")
                ||selected.stream().anyMatch(job->!job.caller().equals(player.getUUID())&&!player.hasPermissions(2)))
            return Cancellation.DENIED;
        for(var job:selected)
        {
            jobs.remove(job.unit());
        }
        return Cancellation.CANCELED;
    }
    public static String request(ServerPlayer player, NervStaffEntity npc, int unit)
    {
        if (unit<0 || unit>2 || !NervStaffDialogue.authorized(player) || !StaffAuthorityR25.allows(npc,"board"))
            return "ops.projectseele.staff.this_station_cannot_dispatch_pilots_contact_misato_ritsuko";
        if(StaffRecoveryR47.pending(player.serverLevel(),unit))return "ops.projectseele.pilotorders.the_unit_and_pilot_are_completing_recovery";
        var jobs=ORDERS.computeIfAbsent(player.serverLevel(),l->new HashMap<>());
        var command=StaffCommandBookR24.unitOrder(player.serverLevel(),unit);
        if(command!=null&&!command.owner.equals(player.getUUID()))return "ops.projectseele.pilotorders.another_commander_has_an_outstanding_order_for";
        if(jobs.containsKey(unit))return "ops.projectseele.pilotorders.this_pilot_s_boarding_order_is_already";
        jobs.put(unit,new Order(player.getUUID(),npc.getUUID(),unit,player.server.getTickCount()+300,false,AutoSortieR32.missionToken(player.serverLevel())));
        EvaLogisticsDirector.loadControlTarget(player.serverLevel(),unit);
        return OperationText.format("ops.projectseele.pilotorders.contact", StaffDialogueCatalogR24.pilotName(unit));
    }
    public static String returnToStandby(ServerPlayer player,NervStaffEntity npc,int unit)
    {
        if(unit<0||unit>2||!NervStaffDialogue.authorized(player)||!StaffAuthorityR25.allows(npc,"board"))
            return "ops.projectseele.pilotorders.this_station_cannot_dispatch_pilots";
        if(StaffCommandBookR24.unitOrder(player.serverLevel(),unit)!=null)
            return "ops.projectseele.pilotorders.cancel_the_outstanding_sortie_order_and_recover";
        var jobs=ORDERS.computeIfAbsent(player.serverLevel(),l->new HashMap<>());
        if(jobs.containsKey(unit))return "ops.projectseele.pilotorders.the_pilot_s_previous_order_is_still";
        jobs.put(unit,new Order(player.getUUID(),npc.getUUID(),unit,player.server.getTickCount()+300,true,AutoSortieR32.missionToken(player.serverLevel())));
        EvaLogisticsDirector.loadControlTarget(player.serverLevel(),unit);
        return "ops.projectseele.pilotorders.checking_the_hangar_interlocks_before_asking_the";
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END || event.getServer().getTickCount()%5!=0)return;
        for(var level:event.getServer().getAllLevels())
        {
            var jobs=ORDERS.get(level);if(jobs==null)continue;
            for(var job:List.copyOf(jobs.values()))
            {
                var player=event.getServer().getPlayerList().getPlayer(job.caller());
                var actor=level.getEntity(job.officer());
                if(player==null || player.level()!=level || !(actor instanceof NervStaffEntity npc)
                        || !NervStaffDialogue.authorized(player) || !StaffAuthorityR25.allows(npc,"board"))
                {jobs.remove(job.unit());continue;}
                if(event.getServer().getTickCount()>job.deadline())
                {jobs.remove(job.unit());NervStaffDialogue.reply(player,npc,"ops.projectseele.pilotorders.hangar_signal_timed_out_the_boarding_order");continue;}
                if(!job.standby()&&!missionContextCurrentR45(job.mission(),AutoSortieR32.missionToken(level)))
                {
                    jobs.remove(job.unit());
                    NervStaffDialogue.reply(player,npc,"ops.projectseele.pilotorders.the_operation_changed_the_previous_boarding_order");continue;
                }
                EvaLogisticsDirector.loadControlTarget(level,job.unit());
                if(EvaLogisticsDirector.canonicalUnit(level,job.unit())==null)continue;
                jobs.remove(job.unit());
                if(job.standby())
                {
                    var entry=EvaFleetSavedData.get(level.getServer()).entry(job.unit()).orElse(null);
                    if(entry==null||entry.phase()!=EvaFleetSavedData.Phase.PARKED)
                        NervStaffDialogue.reply(player,npc,"ops.projectseele.pilotorders.the_unit_has_not_stopped_in_its");
                    else
                    {
                        int accepted=TrainingPilotDirector.stop(level,job.unit());
                        NervStaffDialogue.reply(player,npc,accepted>0?OperationText.format("ops.projectseele.pilotorders.leave", StaffDialogueCatalogR24.pilotName(job.unit())):"离栓条件尚未满足，驾驶员与机体保持原位。");
                    }
                    continue;
                }
                var result=TrainingPilotDirector.start(level,job.unit());
                if(result.accepted())AutoSortieR32.assignCommander(EvaLogisticsDirector.canonicalUnit(level,job.unit()),player);
                NervStaffDialogue.reply(player,npc,result.accepted()?OperationText.format("ops.projectseele.pilotorders.board", StaffDialogueCatalogR24.pilotName(job.unit())):result.message());
            }
        }
    }
    private StaffPilotOrdersR25() {}
}
