package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervStaffEntity;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.ChunkPos;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;

/** One finite order per operator and airframe; every action still needs a physical press. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class StaffCommandBookR24
{
    public enum Step { SIGNAL, PILOT, PRESS, PREPARING, LAUNCHING, RECOVERING }
    public static final class Order
    {
        public final UUID actor, owner;
        public UUID contact;
        public final int unit;
        public final String requested;
        public final String mission;
        public final long deadline;
        public Step step = Step.SIGNAL;
        public boolean automatic;
        public String operation, message = "正在接收机库状态";
        public final String actorName;
        private BlockPos lastPosition;
        private int missingTicks;
        private Order(NervStaffEntity npc, ServerPlayer player, String operation, int unit)
        {
            actor = npc.getUUID(); contact = actor; owner = player.getUUID(); requested = operation;
            actorName = npc.getName().getString(); lastPosition = npc.blockPosition();
            this.operation = StaffUndergroundChoiceR52.initialOperation(operation);
            this.unit = unit; deadline = player.level().getGameTime() + 12000;
            mission=AutoSortieR32.missionToken(player.serverLevel());
        }
    }
    private static final Map<ServerLevel, Map<UUID, Order>> ORDERS = new WeakHashMap<>();
    private static final net.minecraft.server.level.TicketType<ChunkPos> TICKET =
            net.minecraft.server.level.TicketType.create("nerv_staff_order_r24", Comparator.comparingLong(ChunkPos::toLong), 100);

    private static void retainOperator(ServerLevel level, BlockPos at)
    {
        for (int x = (at.getX() >> 4) - 1; x <= (at.getX() >> 4) + 1; x++)
            for (int z = (at.getZ() >> 4) - 1; z <= (at.getZ() >> 4) + 1; z++)
            {
                var chunk = new ChunkPos(x, z); level.getChunkSource().addRegionTicket(TICKET, chunk, 2, chunk);
                level.getChunk(x, z);
            }
    }

    public static Order order(NervStaffEntity npc)
    {
        if (!(npc.level() instanceof ServerLevel level)) return null;
        var jobs = ORDERS.getOrDefault(level, Map.of());
        var direct = jobs.get(npc.getUUID());
        return direct != null ? direct : jobs.values().stream().filter(job -> job.contact.equals(npc.getUUID())).findFirst().orElse(null);
    }
    public static Order unitOrder(ServerLevel level,int unit)
    {return ORDERS.getOrDefault(level,Map.of()).values().stream().filter(order->order.unit==unit).findFirst().orElse(null);}
    public static void cancelAutomatic(ServerLevel level,int unit)
    {
        var jobs=ORDERS.get(level);if(jobs==null)return;
        for(var job:List.copyOf(jobs.values()))if(job.automatic&&job.unit==unit)
        {
            jobs.remove(job.actor);
            if(level.getEntity(job.actor) instanceof NervStaffEntity npc)npc.finishTask();
        }
    }
    public static boolean validateAutomatic(NervStaffEntity npc)
    {
        var job=order(npc);
        if(job==null)return true;
        var level=(ServerLevel)npc.level();
        if(!job.mission.isEmpty()&&!job.operation.equals("recover")&&!job.mission.equals(AutoSortieR32.missionToken(level)))
        {
            failed(npc,"ops.projectseele.orders.the_operation_changed_or_was_canceled_no");npc.finishTask();return false;
        }
        if(!job.automatic)return true;
        if(AutoSortieR32.automaticAllowed(level,job.unit))return true;
        cancelAutomatic(level,job.unit);return false;
    }
    public static void cancelMissionActions(ServerLevel level)
    {
        var jobs=ORDERS.get(level);if(jobs==null)return;
        for(var job:List.copyOf(jobs.values()))if(!job.mission.isEmpty()&&!job.operation.equals("recover"))
        {jobs.remove(job.actor);if(level.getEntity(job.actor) instanceof NervStaffEntity npc)npc.finishTask();}
    }

    public static int request(ServerPlayer player, NervStaffEntity npc, String operation, int unit)
    {
        if (unit < 0 || unit > 2 || !Set.of("prepare", "launch", "recover", "deploy","deploy_surface","deploy_geofront","deploy_hakone",StaffUndergroundChoiceR52.PREPARE_AND_DEPLOY).contains(operation)) return 0;
        String authority=operation.equals(StaffUndergroundChoiceR52.PREPARE_AND_DEPLOY)||operation.startsWith("deploy_")?"deploy":operation;
        if (!NervStaffDialogue.authorized(player) || !StaffAuthorityR25.allows(npc, authority))
        {
            NervStaffDialogue.reply(player, npc, NervStaffDialogue.commandRefusal(player,npc,authority));
            return 0;
        }
        ServerLevel level = player.serverLevel();
        var orders = ORDERS.computeIfAbsent(level, key -> new LinkedHashMap<>());
        if (npc.busy() || order(npc) != null || orders.values().stream().anyMatch(job -> job.unit == unit))
        {
            NervStaffDialogue.reply(player, npc, "ops.projectseele.orders.commander_the_unit_or_my_station_still");
            return 0;
        }
        if (npc.skin().equals("fuyutsuki"))
        {
            // The deputy's raised city console has no path to the EVA desks.
            // Keep the caller/contact while the responsible officer presses the real key.
            String skin = operation.equals("prepare") || operation.equals("recover") ? "ritsuko" : "misato";
            var post = NervStaffDirector.roster(level).stream().filter(p -> p.skin().equals(skin)).findFirst().orElse(null);
            if (post != null) retainOperator(level, post.feet());
            var identity = post == null ? null : NervStaffSavedData.get(level).identity(post.id());
            if (identity == null || !(level.getEntity(identity) instanceof NervStaffEntity operator))
            {
                NervStaffDialogue.reply(player, npc, "ops.projectseele.orders.the_unit_control_station_is_offline_the");
                return 0;
            }
            int accepted = request(player, operator, operation, unit);
            if (accepted > 0)
            {
                order(operator).contact = npc.getUUID();
                NervStaffDialogue.reply(player, npc, OperationText.format("ops.projectseele.orders.delegated", StaffDialogueCatalogR24.speaker(operator.getName().getString())));
            }
            return accepted;
        }
        var order = new Order(npc, player, operation, unit); orders.put(npc.getUUID(), order);
        EvaLogisticsDirector.loadControlTarget(level, unit);
        NervStaffDialogue.reply(player, npc, operation.equals(StaffUndergroundChoiceR52.PREPARE_AND_DEPLOY)
                ? "准备＋地下紧急部署已安排。驾驶员接入并完成准备，机体在发射井停稳待命后，再由承载板送出地下出口。"
                :operation.equals("deploy")
                ? "收到，司令。驾驶员接入后开始整备，机体抵达发射台以后，我再确认发射时机。"
                : "收到，司令。我先确认机库状态，随后向您报告。");
        return 1;
    }

    public static int cancel(ServerPlayer player, NervStaffEntity npc, int unit)
    {
        var job = order(npc);
        UUID owner = job == null ? npc.requester() : job.owner;
        if (owner != null && !owner.equals(player.getUUID()) && !player.hasPermissions(2))
        {
            NervStaffDialogue.reply(player, npc, "ops.projectseele.orders.ask_the_person_who_issued_the_order"); return 0;
        }
        if (job != null && unit >= 0 && unit != job.unit)
        {
            NervStaffDialogue.reply(player, npc, "ops.projectseele.orders.the_pending_order_is_for_another_unit"); return 0;
        }
        var pilotCancellation=StaffPilotOrdersR25.cancel(player,npc,unit);
        if(pilotCancellation==StaffPilotOrdersR25.Cancellation.DENIED)
        {
            NervStaffDialogue.reply(player,npc,"ops.projectseele.orders.ask_the_person_who_issued_the_order");return 0;
        }
        if (job != null)
        {
            ORDERS.get(player.serverLevel()).remove(job.actor);
            if (player.serverLevel().getEntity(job.actor) instanceof NervStaffEntity operator) operator.finishTask();
        }
        if(NervStaffDialogue.authorized(player)&&StaffAuthorityR25.commandContact(npc))
            AutoSortieR32.cancel(player,job==null?unit:job.unit);
        npc.finishTask();
        NervStaffDialogue.reply(player, npc, "ops.projectseele.orders.further_button_operations_canceled_machinery_already_moving");
        return 1;
    }

    public static void failed(NervStaffEntity npc, String message)
    {
        var job = order(npc); if (job == null) return;
        var level = (ServerLevel) npc.level(); ORDERS.get(level).remove(job.actor);
        var owner = level.getServer().getPlayerList().getPlayer(job.owner);
        if (owner != null) NervStaffDialogue.reply(owner, npc, message);
    }

    public static void pressed(NervStaffEntity npc, NervOperationsConsole.ControlOutcome outcome)
    {
        var job = order(npc); if (job == null) return;
        var level = (ServerLevel) npc.level();
        var owner = level.getServer().getPlayerList().getPlayer(job.owner);
        if (outcome == null || !outcome.accepted())
        {
            failed(npc, OperationText.format("ops.projectseele.orders.interlock", OperationText.read(NervStaffDialogue.readinessHint(level, job.unit, job.operation))));
            return;
        }
        if(job.automatic)
        {
            var airframe=EvaLogisticsDirector.canonicalUnit(level,job.unit);
            if(airframe!=null)airframe.getPersistentData().putString("R32AutoStep",job.operation+"_accepted");
            ORDERS.get(level).remove(npc.getUUID());
            if(owner!=null)NervStaffDialogue.reply(owner,npc,job.operation.equals("prepare")
                ?OperationText.format("ops.projectseele.orders.pilot_ready", OperationText.unit(job.unit))
                :OperationText.format("ops.projectseele.orders.launch", OperationText.unit(job.unit)));
            return;
        }
        switch (job.operation)
        {
            case "prepare" -> { job.step = Step.PREPARING; job.message = "整备中，等待机体到达发射台"; }
            case "recover" -> { job.step = Step.RECOVERING; job.message = "回收中，等待机体返回湿舱"; }
            default ->
            {
                job.step = Step.LAUNCHING; job.message = "弹射程序进行中";
                if (owner != null) NervStaffDialogue.reply(owner, npc, "ops.projectseele.orders.launch_interlock_cleared_keep_the_channel_open");
            }
        }
    }

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || event.getServer().getTickCount() % 5 != 0) return;
        for (var level : event.getServer().getAllLevels())
        {
            var jobs = ORDERS.get(level); if (jobs == null || jobs.isEmpty()) continue;
            for (var job : List.copyOf(jobs.values()))
            {
                if (event.getServer().getTickCount() % 40 == 0) retainOperator(level, job.lastPosition);
                var actor = level.getEntity(job.actor); var owner = event.getServer().getPlayerList().getPlayer(job.owner);
                if (!(actor instanceof NervStaffEntity npc))
                {
                    if (++job.missingTicks > 60)
                    {
                        jobs.remove(job.actor);
                        if (owner != null) NervStaffDialogue.say(owner, job.actorName, "操作人员暂时失联，待执行指令已取消。请重新联络。");
                    }
                    continue;
                }
                job.missingTicks = 0; job.lastPosition = npc.blockPosition();
                if(!validateAutomatic(npc))continue;
                if (owner == null || owner.level() != level || !NervStaffDialogue.authorized(owner) || level.getGameTime() > job.deadline)
                {
                    failed(npc, "ops.projectseele.orders.pending_orders_canceled_after_loss_of_contact"); npc.finishTask(); continue;
                }
                var status = EvaLogisticsDirector.status(level, job.unit);
                if (status.phase().equals("CANCELLED"))
                { failed(npc, "ops.projectseele.orders.the_sortie_order_was_canceled_the_unit"); npc.finishTask(); continue; }
                if (status.phase().equals("PLUG_FAULT"))
                { failed(npc, "ops.projectseele.orders.entry_plug_insertion_failed_further_launch_orders"); npc.finishTask(); continue; }
                if (job.step == Step.PRESS)
                {
                    if (!npc.busy()) failed(npc, "ops.projectseele.orders.the_button_operation_did_not_complete_pending");
                    continue;
                }
                if (job.step == Step.LAUNCHING)
                {
                    if (status.phase().equals("DEPLOYED"))
                    { jobs.remove(job.actor); NervStaffDialogue.reply(owner, npc, "ops.projectseele.orders.the_unit_has_reached_the_surface_pilot"); }
                    else if (Set.of("PARKED", "DESCENDING", "TO_HANGAR", "FILLING").contains(status.phase()))
                        failed(npc, "ops.projectseele.orders.deployment_status_changed_further_orders_stopped_verify");
                    continue;
                }
                if (job.step == Step.PREPARING)
                {
                    if(status.phase().equals("DEPLOYED")&&job.requested.startsWith("deploy_"))
                    {jobs.remove(job.actor);NervStaffDialogue.reply(owner,npc,"ops.projectseele.orders.the_unit_reached_the_selected_exit_control");continue;}
                    if (Set.of("PARKED", "PLUG_ABORT_RETURNING", "PLUG_ABORT_DOCKED", "DEPLOYED").contains(status.phase()))
                    { failed(npc, "ops.projectseele.orders.another_operation_changed_readiness_further_launch_orders"); continue; }
                    if (!status.phase().equals("SILO_READY")) continue;
                    String next=StaffUndergroundChoiceR52.readyContinuation(job.requested,status.phase());
                    if(next.equals("underground")){dispatchUndergroundR52(owner,npc,job);continue;}
                    if (next.equals("launch")) { job.operation = "launch"; job.step = Step.SIGNAL; }
                    else { jobs.remove(job.actor); NervStaffDialogue.reply(owner, npc, "ops.projectseele.orders.preparation_complete_the_unit_is_on_the"); continue; }
                }
                if (job.step == Step.RECOVERING)
                {
                    if (status.phase().equals("PARKED")) { jobs.remove(job.actor); NervStaffDialogue.reply(owner, npc, "ops.projectseele.orders.the_unit_is_back_in_the_hangar"); }
                    continue;
                }
                if (!status.loaded())
                {
                    job.message = "正在接收远端机库信号";
                    if (event.getServer().getTickCount() % 40 == 0) EvaLogisticsDirector.loadControlTarget(level, job.unit);
                    continue;
                }
                if (job.operation.equals("prepare"))
                {
                    String next=StaffUndergroundChoiceR52.readyContinuation(job.requested,status.phase());
                    if(next.equals("underground")){dispatchUndergroundR52(owner,npc,job);continue;}
                    if (next.equals("launch")) job.operation = "launch";
                    else if (!status.phase().equals("PARKED")) { failed(npc, OperationText.format("ops.projectseele.orders.not_standby", NervStaffDialogue.phaseText(status.phase()))); continue; }
                    else if (!NervStaffDialogue.boarded(level, job.unit))
                    {
                        if (job.step != Step.PILOT) NervStaffDialogue.reply(owner, npc, "ops.projectseele.orders.i_ll_wait_until_the_pilot_enters");
                        job.step = Step.PILOT; job.message = "等待驾驶员登机"; continue;
                    }
                }
                if (job.operation.equals("launch") && !status.phase().equals("SILO_READY")
                        || job.operation.equals("recover") && !status.phase().equals("DEPLOYED"))
                { failed(npc, NervStaffDialogue.readinessHint(level, job.unit, job.operation)); continue; }
                job.step = Step.PRESS; job.message = "前往控制台操作按键";
                if (NervStaffDialogue.beginNativeAction(owner, npc, job.operation, job.unit) == 0)
                    failed(npc, "ops.projectseele.orders.unable_to_reach_the_control_button_order");
            }
        }
    }

    private static void dispatchUndergroundR52(ServerPlayer owner,NervStaffEntity npc,Order job)
    {
        if(npc.busy()){job.message="准备完成，等待操作人员完成当前按键。";return;}
        var level=owner.serverLevel();var jobs=ORDERS.get(level);
        if(jobs==null||jobs.get(job.actor)!=job||!job.owner.equals(owner.getUUID()))return;
        // Remove this completed preparation before the existing strict operator
        // and airframe checks; it must not block itself or bypass another order.
        jobs.remove(job.actor);
        var result=StaffOperationsR48.undergroundDeploymentR52(owner,npc,job.unit);
        NervStaffDialogue.reply(owner,npc,result.message());
    }
    private StaffCommandBookR24() {}
}
