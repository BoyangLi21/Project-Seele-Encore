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
            StaffOperationsTraceR45.event(player.serverLevel(),"pilot_pending_canceled",player.getUUID(),npc.getUUID(),job.unit(),job.standby()?"standby":"board","owner_checked_before_cancellation");
        }
        return Cancellation.CANCELED;
    }
    public static String request(ServerPlayer player, NervStaffEntity npc, int unit)
    {
        if (unit<0 || unit>2 || !NervStaffDialogue.authorized(player) || !StaffAuthorityR25.allows(npc,"board"))
            return "本岗位无权调遣驾驶员，请联络美里、律子或冬月。";
        if(StaffRecoveryR47.pending(player.serverLevel(),unit))return "这台机体仍在回收与驾驶员交接，完成原路线后再安排登机。";
        var jobs=ORDERS.computeIfAbsent(player.serverLevel(),l->new HashMap<>());
        var command=StaffCommandBookR24.unitOrder(player.serverLevel(),unit);
        if(command!=null&&!command.owner.equals(player.getUUID()))return "这台机体已有其他指挥员的待执行指令，请先联系下令人。";
        if(jobs.containsKey(unit))return "该驾驶员已有登机指令，正在执行。";
        jobs.put(unit,new Order(player.getUUID(),npc.getUUID(),unit,player.server.getTickCount()+300,false,AutoSortieR32.missionToken(player.serverLevel())));
        StaffOperationsTraceR45.event(player.serverLevel(),"pilot_pending_accepted",player.getUUID(),npc.getUUID(),unit,"board","commander_unchanged_until_native_dispatch_accepts");
        EvaLogisticsDirector.loadControlTarget(player.serverLevel(),unit);
        return "正在呼叫"+TrainingPilotEntity.pilotName(unit)+"，确认对应机库后开始登机。";
    }
    public static String returnToStandby(ServerPlayer player,NervStaffEntity npc,int unit)
    {
        if(unit<0||unit>2||!NervStaffDialogue.authorized(player)||!StaffAuthorityR25.allows(npc,"board"))
            return "本岗位无权调遣驾驶员。";
        if(StaffCommandBookR24.unitOrder(player.serverLevel(),unit)!=null)
            return "请先取消待执行的出动指令，并将机体回收至机库。";
        var jobs=ORDERS.computeIfAbsent(player.serverLevel(),l->new HashMap<>());
        if(jobs.containsKey(unit))return "该驾驶员的上一条指令尚未结束。";
        jobs.put(unit,new Order(player.getUUID(),npc.getUUID(),unit,player.server.getTickCount()+300,true,AutoSortieR32.missionToken(player.serverLevel())));
        StaffOperationsTraceR45.event(player.serverLevel(),"pilot_pending_accepted",player.getUUID(),npc.getUUID(),unit,"standby","parked_phase_still_required_at_execution");
        EvaLogisticsDirector.loadControlTarget(player.serverLevel(),unit);
        return "正在确认机库联锁，随后通知驾驶员离开插入栓、返回待命。";
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
                {jobs.remove(job.unit());StaffOperationsTraceR45.event(level,"pilot_pending_invalidated",job.caller(),job.officer(),job.unit(),job.standby()?"standby":"board","owner_presence_or_authority_changed");continue;}
                if(event.getServer().getTickCount()>job.deadline())
                {jobs.remove(job.unit());NervStaffDialogue.reply(player,npc,"机库信号超时，登机指令未执行。");continue;}
                if(!job.standby()&&!missionContextCurrentR45(job.mission(),AutoSortieR32.missionToken(level)))
                {
                    jobs.remove(job.unit());
                    StaffOperationsTraceR45.event(level,"pilot_pending_invalidated",job.caller(),job.officer(),job.unit(),"board","mission_canceled_failed_or_replaced");
                    NervStaffDialogue.reply(player,npc,"作战安排已变更，上一条登机指令已撤销。");continue;
                }
                EvaLogisticsDirector.loadControlTarget(level,job.unit());
                if(EvaLogisticsDirector.canonicalUnit(level,job.unit())==null)continue;
                jobs.remove(job.unit());
                if(job.standby())
                {
                    var entry=EvaFleetSavedData.get(level.getServer()).entry(job.unit()).orElse(null);
                    if(entry==null||entry.phase()!=EvaFleetSavedData.Phase.PARKED)
                        NervStaffDialogue.reply(player,npc,"机体还未在机库停稳，请先完成回收。驾驶员继续留在插入栓内。");
                    else
                    {
                        int accepted=TrainingPilotDirector.stop(level,job.unit());
                        NervStaffDialogue.reply(player,npc,accepted>0?"已通知"+TrainingPilotEntity.pilotName(job.unit())+"离栓，返回待命。":"离栓条件尚未满足，驾驶员与机体保持原位。");
                    }
                    continue;
                }
                var result=TrainingPilotDirector.start(level,job.unit());
                if(result.accepted())AutoSortieR32.assignCommander(EvaLogisticsDirector.canonicalUnit(level,job.unit()),player);
                StaffOperationsTraceR45.event(level,result.accepted()?"pilot_native_dispatch_accepted":"pilot_native_dispatch_rejected",job.caller(),job.officer(),job.unit(),"board",result.message());
                NervStaffDialogue.reply(player,npc,result.accepted()?"已通知"+TrainingPilotEntity.pilotName(job.unit())+"登机。":result.message());
            }
        }
    }
    private StaffPilotOrdersR25() {}
}
