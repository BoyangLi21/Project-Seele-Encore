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
        public final int unit;
        public final String requested;
        public final long deadline;
        public Step step = Step.SIGNAL;
        public boolean automatic;
        public String operation, message = "正在接收机库状态";
        public final String actorName;
        private BlockPos lastPosition;
        private int missingTicks;
        private Order(NervStaffEntity npc, ServerPlayer player, String operation, int unit)
        {
            actor = npc.getUUID(); owner = player.getUUID(); requested = operation;
            actorName = npc.getName().getString(); lastPosition = npc.blockPosition();
            this.operation = operation.equals("deploy") ? "prepare" : operation;
            this.unit = unit; deadline = player.level().getGameTime() + 12000;
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
        return npc.level() instanceof ServerLevel level ? ORDERS.getOrDefault(level, Map.of()).get(npc.getUUID()) : null;
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
        if(job==null||!job.automatic)return true;
        var level=(ServerLevel)npc.level();
        if(AutoSortieR32.automaticAllowed(level,job.unit))return true;
        cancelAutomatic(level,job.unit);return false;
    }

    public static int request(ServerPlayer player, NervStaffEntity npc, String operation, int unit)
    {
        if (unit < 0 || unit > 2 || !Set.of("prepare", "launch", "recover", "deploy").contains(operation)) return 0;
        if (!NervStaffDialogue.authorized(player) || !StaffAuthorityR25.allows(npc, operation))
        {
            NervStaffDialogue.reply(player, npc, "这项指令需要指挥权限或 NERV 通行证，并由指挥或技术负责人执行。");
            return 0;
        }
        ServerLevel level = player.serverLevel();
        var orders = ORDERS.computeIfAbsent(level, key -> new LinkedHashMap<>());
        if (npc.busy() || orders.containsKey(npc.getUUID()) || orders.values().stream().anyMatch(job -> job.unit == unit))
        {
            NervStaffDialogue.reply(player, npc, "操作人员或这台机体已有待执行指令。请等它完成，或由下令人取消后续操作。");
            return 0;
        }
        var order = new Order(npc, player, operation, unit); orders.put(npc.getUUID(), order);
        EvaLogisticsDirector.loadControlTarget(level, unit);
        NervStaffDialogue.reply(player, npc, operation.equals("deploy")
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
            NervStaffDialogue.reply(player, npc, "请由下达这项指令的人取消，或联系值班指挥。"); return 0;
        }
        if (job != null && unit >= 0 && unit != job.unit)
        {
            NervStaffDialogue.reply(player, npc, "当前待执行指令属于另一台机体，没有取消它。"); return 0;
        }
        if (job != null) ORDERS.get(player.serverLevel()).remove(npc.getUUID());
        if(NervStaffDialogue.authorized(player)&&StaffAuthorityR25.commandContact(npc))
            AutoSortieR32.cancel(player,job==null?unit:job.unit);
        npc.finishTask();
        NervStaffDialogue.reply(player, npc, "后续按键操作已取消。已经开始的机械运输会按原流程运行到安全位置。");
        return 1;
    }

    public static void failed(NervStaffEntity npc, String message)
    {
        var job = order(npc); if (job == null) return;
        var level = (ServerLevel) npc.level(); ORDERS.get(level).remove(npc.getUUID());
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
            failed(npc, "联锁没有接受这次操作。" + NervStaffDialogue.readinessHint(level, job.unit, job.operation));
            return;
        }
        if(job.automatic)
        {
            var airframe=EvaLogisticsDirector.canonicalUnit(level,job.unit);
            if(airframe!=null)airframe.getPersistentData().putString("R32AutoStep",job.operation+"_accepted");
            ORDERS.get(level).remove(npc.getUUID());
            if(owner!=null)NervStaffDialogue.reply(owner,npc,job.operation.equals("prepare")
                ?NervStaffDialogue.unitName(job.unit)+"驾驶员就位。开始整备，美里，等机体到发射台后交给你。"
                :NervStaffDialogue.unitName(job.unit)+"，发射！到地面后保持通信。");
            return;
        }
        switch (job.operation)
        {
            case "prepare" -> { job.step = Step.PREPARING; job.message = "整备中，等待机体到达发射台"; }
            case "recover" -> { job.step = Step.RECOVERING; job.message = "回收中，等待机体返回湿舱"; }
            default ->
            {
                job.step = Step.LAUNCHING; job.message = "弹射程序进行中";
                if (owner != null) NervStaffDialogue.reply(owner, npc, "发射联锁通过。保持联络，运输和弹射由发射系统继续完成。");
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
                    failed(npc, "待执行指令已取消：通讯中断、权限改变或等待超时。已开始的运输继续按安全流程运行。"); npc.finishTask(); continue;
                }
                var status = EvaLogisticsDirector.status(level, job.unit);
                if (status.phase().equals("PLUG_FAULT"))
                { failed(npc, "插入栓接入出现故障，后续发射已取消。请到机库检查。"); npc.finishTask(); continue; }
                if (job.step == Step.PRESS)
                {
                    if (!npc.busy()) failed(npc, "按键操作没有完成，待执行指令已停止。");
                    continue;
                }
                if (job.step == Step.LAUNCHING)
                {
                    if (status.phase().equals("DEPLOYED"))
                    { jobs.remove(job.actor); NervStaffDialogue.reply(owner, npc, "机体已抵达地表，操纵权交还驾驶员。保持联络。"); }
                    else if (Set.of("PARKED", "DESCENDING", "TO_HANGAR", "FILLING").contains(status.phase()))
                        failed(npc, "出动状态已改变，后续指令已停止。请确认当前机体位置。");
                    continue;
                }
                if (job.step == Step.PREPARING)
                {
                    if (Set.of("PARKED", "PLUG_ABORT_RETURNING", "PLUG_ABORT_DOCKED", "DEPLOYED").contains(status.phase()))
                    { failed(npc, "整备状态已被其他操作改变，后续发射已取消。请重新核对机体状态。"); continue; }
                    if (!status.phase().equals("SILO_READY")) continue;
                    if (job.requested.equals("deploy")) { job.operation = "launch"; job.step = Step.SIGNAL; }
                    else { jobs.remove(job.actor); NervStaffDialogue.reply(owner, npc, "整备完成，机体已到达发射台。等待你的发射指令。"); continue; }
                }
                if (job.step == Step.RECOVERING)
                {
                    if (status.phase().equals("PARKED")) { jobs.remove(job.actor); NervStaffDialogue.reply(owner, npc, "机体已返回机库，湿舱恢复完成。"); }
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
                    if (job.requested.equals("deploy") && status.phase().equals("SILO_READY")) job.operation = "launch";
                    else if (!status.phase().equals("PARKED")) { failed(npc, "机体尚未回到整备待命状态。当前：" + NervStaffDialogue.stage(status.phase()) + "。"); continue; }
                    else if (!NervStaffDialogue.boarded(level, job.unit))
                    {
                        if (job.step != Step.PILOT) NervStaffDialogue.reply(owner, npc, "我会等驾驶员进入对应机库的悬挂插入栓，再继续整备。你可以离开指挥台前往登机桥。");
                        job.step = Step.PILOT; job.message = "等待驾驶员登机"; continue;
                    }
                }
                if (job.operation.equals("launch") && !status.phase().equals("SILO_READY")
                        || job.operation.equals("recover") && !status.phase().equals("DEPLOYED"))
                { failed(npc, NervStaffDialogue.readinessHint(level, job.unit, job.operation)); continue; }
                job.step = Step.PRESS; job.message = "前往控制台操作按键";
                if (NervStaffDialogue.beginNativeAction(owner, npc, job.operation, job.unit) == 0)
                    failed(npc, "未能抵达对应控制按键，指令已停止。");
            }
        }
    }

    private StaffCommandBookR24() {}
}
