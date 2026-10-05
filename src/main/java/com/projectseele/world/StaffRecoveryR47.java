package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervStaffEntity;
import com.projectseele.entity.TrainingPilotEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.Comparator;

/** Phone recovery coordinates original aircraft, original console operator and original pilot. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class StaffRecoveryR47
{
    private static final TicketType<ChunkPos> TICKET=TicketType.create("staff_recovery_r47",Comparator.comparingLong(ChunkPos::toLong),100);
    private static final class Job
    {
        int unit;
        UUID eva, owner, officer, pilot;
        long expires;
        String stage = "LOCATE";
        boolean consoleRequested, exitRequested, npc;
    }
    private static final class State extends SavedData
    {
        final Map<Integer, Job> jobs = new LinkedHashMap<>();
        static State load(CompoundTag tag)
        {
            var state = new State();
            for (var raw : tag.getList("Jobs", Tag.TAG_COMPOUND))
            {
                var row = (CompoundTag) raw; int unit = row.getInt("Unit");
                if (unit < 0 || unit > 2 || !row.hasUUID("Eva") || !row.hasUUID("Owner") || !row.hasUUID("Officer")) continue;
                var job = new Job(); job.unit = unit; job.eva = row.getUUID("Eva"); job.owner = row.getUUID("Owner");
                job.officer = row.getUUID("Officer"); job.expires = row.getLong("Expires"); job.stage = row.getString("Stage");
                // In-memory physical console orders do not survive a restart.
                job.npc=row.getBoolean("Npc");if(row.hasUUID("Pilot"))job.pilot=row.getUUID("Pilot");
                // The original navigation dispatcher revalidates a resumed exit.
                job.exitRequested = false; state.jobs.putIfAbsent(unit, job);
            }
            return state;
        }
        @Override public CompoundTag save(CompoundTag tag)
        {
            var rows = new ListTag();
            for (var job : jobs.values())
            {
                var row = new CompoundTag(); row.putInt("Unit", job.unit); row.putUUID("Eva", job.eva);
                row.putUUID("Owner", job.owner); row.putUUID("Officer", job.officer); row.putLong("Expires", job.expires);
                row.putString("Stage", job.stage); row.putBoolean("ExitRequested", job.exitRequested); rows.add(row);
                row.putBoolean("Npc",job.npc);if(job.pilot!=null)row.putUUID("Pilot",job.pilot);
            }
            tag.put("Jobs", rows); return tag;
        }
    }
    private static State state(ServerLevel level)
    { return level.getDataStorage().computeIfAbsent(State::load, State::new, "projectseele_staff_recovery_r47"); }

    public static String request(ServerPlayer caller, NervStaffEntity officer, int unit)
    {
        if (unit < 0 || unit > 2 || !NervStaffDialogue.authorized(caller) || !StaffAuthorityR25.allows(officer, "recover"))
            return "回收安排请联络葛城部长或赤木博士，并指定机体。";
        var level = caller.serverLevel();
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION))return "请先进入第三新东京市，再安排本部机体回收。";
        var state = state(level);
        if (state.jobs.containsKey(unit)) return "这台机体的回收已经在安排，请查看运输状态。";
        var receipt = EvaFleetSavedData.get(level.getServer()).entry(unit).orElse(null);
        if (receipt == null) return "原机体登记尚未接通，不能安排回收。";
        if (receipt.phase() != EvaFleetSavedData.Phase.DEPLOYED && receipt.phase() != EvaFleetSavedData.Phase.PARKED)
            return "机体仍在机库运输过程中。请等它到安全位置，再安排回收。";
        var eva = EvaLogisticsDirector.canonicalUnit(level, unit);
        if (eva != null && eva.getPilotEntity() instanceof ServerPlayer pilot && pilot != caller)
            return "请由当前驾驶员请求回收，或先让驾驶员按原流程离栓。";
        var job = new Job(); job.unit = unit; job.eva = receipt.canonicalId(); job.owner = caller.getUUID();
        if(eva!=null&&eva.getPilotEntity() instanceof TrainingPilotEntity pilot){job.npc=true;job.pilot=pilot.getUUID();}
        var sortie=TvCampaignSavedData.get(level).sorties.get(unit);
        if(job.pilot==null&&sortie!=null&&sortie.npc&&job.eva.equals(sortie.eva)&&sortie.pilotR45!=null)
        {job.npc=true;job.pilot=sortie.pilotR45;}
        job.officer = officer.getUUID(); job.expires = level.getGameTime() + 20 * 60 * 12;
        state.jobs.put(unit, job); state.setDirty(); AutoSortieR32.suspendAutomaticForRecovery(level,unit);
        if(eva!=null){eva.stopAutonomousR30();TvEncounterRulesR45.pauseNpcUnitForRecoveryR47(eva);}
        return "收到。先安排机体返回所属发射井，再按常规流程回库。驾驶员保持通信。";
    }

    public static boolean cancel(ServerPlayer caller, int unit)
    {
        var state = state(caller.serverLevel()); boolean canceled = false;
        for (var job : List.copyOf(state.jobs.values()))
            if ((unit < 0 || unit == job.unit) && (job.owner.equals(caller.getUUID()) || caller.hasPermissions(2)))
            { state.jobs.remove(job.unit); canceled = true; }
        if (canceled) state.setDirty();
        return canceled;
    }
    public static boolean queuedBy(ServerPlayer caller,int unit)
    {
        var job=state(caller.serverLevel()).jobs.get(unit);
        return job!=null&&job.owner.equals(caller.getUUID());
    }
    public static boolean pending(ServerLevel level,int unit)
    {return state(level).jobs.containsKey(unit);}

    private static void stage(State state, Job job, String stage)
    { if (!job.stage.equals(stage)) { job.stage = stage; state.setDirty(); } }

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || event.getServer().getTickCount() % 10 != 0) return;
        for (var level : event.getServer().getAllLevels())
        {
            var state = state(level);
            for (var job : List.copyOf(state.jobs.values()))
            {
                var owner = event.getServer().getPlayerList().getPlayer(job.owner);
                if (level.getGameTime() > job.expires)
                {
                    state.jobs.remove(job.unit); state.setDirty();
                    if (owner != null) NervStaffDialogue.say(owner, "NERV 回收联络", "回收等待超时。已开始的机械运输继续到安全位置，请重新核对状态。");
                    continue;
                }
                if (owner == null || owner.level() != level || !NervStaffDialogue.authorized(owner)) continue;
                EvaLogisticsDirector.loadControlTarget(level, job.unit);
                var eva = EvaLogisticsDirector.canonicalUnit(level, job.unit);
                if (eva == null) continue;
                if (!eva.getUUID().equals(job.eva))
                {
                    state.jobs.remove(job.unit); state.setDirty();
                    NervStaffDialogue.say(owner, "NERV 回收联络", "机体识别信号与接受任务时不一致，回收已暂停。请确认通信。"); continue;
                }
                var phase = EvaLogisticsDirector.status(level, job.unit).phase();
                if (phase.equals("PARKED"))
                {
                    var pilot = TrainingPilotDirector.existingPilotR45(level, job.unit);
                    if(job.npc&&(pilot==null||job.pilot==null||!job.pilot.equals(pilot.getUUID())))
                    {stage(state,job,"WAIT_ORIGINAL_PILOT");continue;}
                    if (job.npc && !TrainingPilotDirector.atOriginalStandbyR47(level,job.unit))
                    {
                        if (!job.exitRequested && TrainingPilotDirector.stop(level, job.unit) > 0)
                        { job.exitRequested = true; state.setDirty(); }
                        stage(state, job, "PILOT_RETURN"); continue;
                    }
                    var capsule=EntryPlugDirector.canonical(level,job.unit);
                    if (eva.getPilotEntity() != null || capsule!=null&&capsule.getFirstPassenger()!=null)
                    {
                        if(!job.stage.equals("HUMAN_EXIT_WAIT"))NervStaffDialogue.say(owner,"赤木律子 · 回收联络","机体已回到湿舱。驾驶员，请按原流程离栓。");
                        stage(state,job,"HUMAN_EXIT_WAIT");continue;
                    }
                    state.jobs.remove(job.unit); state.setDirty();
                    NervStaffDialogue.say(owner, "赤木律子 · 回收联络", "机体已回到湿舱，驾驶员已离栓。后续出击请重新下达指令。"); continue;
                }
                if (!phase.equals("DEPLOYED")) { stage(state, job, "MECHANICAL_RECOVERY"); continue; }
                if (eva.isFirstBattleActive() || eva.isLaunchSequenceActive() || eva.isBerserk())
                { stage(state, job, "WAIT_SAFE_STATE"); continue; }
                if (NervAirLiftR30.ownsMotion(eva)) { stage(state, job, "AIRLIFT"); continue; }
                if(UndergroundSortieR48.recoveringR48(level,job.unit,eva))
                {stage(state,job,"UNDERGROUND_RECOVERY");continue;}
                if(UndergroundSortieR48.atDeployedPadR48(level,job.unit,eva))
                {
                    var reply=UndergroundSortieR48.requestRecoveryR48(owner,job.unit);
                    boolean firstWait=!job.stage.equals("WAIT_UNDERGROUND_INTERLOCK");
                    stage(state,job,reply.accepted()?"UNDERGROUND_RECOVERY":"WAIT_UNDERGROUND_INTERLOCK");
                    if(!reply.accepted()&&firstWait)NervStaffDialogue.say(owner,"地下回收联络",reply.message());
                    continue;
                }
                boolean atHead = NervAirLiftR30.waitingAtHead(eva)
                        || eva.position().distanceTo(NervAirLiftR30.head(level, job.unit)) < 8;
                if (!atHead)
                {
                    if (NervAirLiftR30.busy(level)) { stage(state, job, "WAIT_AIRCRAFT"); continue; }
                    String reply = NervAirLiftR30.request(owner, job.unit, true, 0, 0);
                    if (NervAirLiftR30.busy(level)) stage(state, job, "AIRLIFT");
                    else { stage(state, job, "AIRLIFT_UNAVAILABLE"); state.jobs.remove(job.unit); state.setDirty(); NervStaffDialogue.say(owner, "NERV 运输联络", reply); }
                    continue;
                }
                var officer = level.getEntity(job.officer);
                if(!(officer instanceof NervStaffEntity))
                {
                    var identities=NervStaffSavedData.get(level).identities();
                    for(var post:NervStaffDirector.roster(level))if(job.officer.equals(identities.get(post.id())))
                    {var chunk=new ChunkPos(post.feet());level.getChunkSource().addRegionTicket(TICKET,chunk,2,chunk);break;}
                    continue;
                }
                if (!(officer instanceof NervStaffEntity npc) || !StaffAuthorityR25.allows(npc, "recover") || npc.busy()) continue;
                var command = StaffCommandBookR24.unitOrder(level, job.unit);
                if (command != null) { stage(state, job, "CONSOLE_RECOVERY"); continue; }
                if(job.consoleRequested)
                {
                    state.jobs.remove(job.unit);state.setDirty();
                    NervStaffDialogue.say(owner,"NERV 回收联络","回收按键没有通过当前联锁。机体与驾驶员保持原位，请核对指挥台提示后再安排。");continue;
                }
                if (!job.consoleRequested && StaffCommandBookR24.request(owner, npc, "recover", job.unit) > 0)
                { job.consoleRequested = true; stage(state, job, "CONSOLE_RECOVERY"); }
            }
        }
    }

    private StaffRecoveryR47() {}
}
