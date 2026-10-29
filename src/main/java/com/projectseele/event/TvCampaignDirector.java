package com.projectseele.event;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.*;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.*;
import net.minecraft.world.BossEvent;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.living.LivingDeathEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class TvCampaignDirector
{
    private static final TicketType<ChunkPos> TICKET = TicketType.create("tv_campaign_r24", Comparator.comparingLong(ChunkPos::toLong), 60);
    private static final Map<ServerLevel, ServerBossEvent> BARS = new WeakHashMap<>();
    private static void clearCombatBar(ServerLevel level)
    {
        ServerBossEvent bar = BARS.remove(level);
        if (bar == null) return;
        bar.removeAllPlayers();
        bar.setVisible(false);
    }
    private static final Map<ServerLevel, Integer> MISSING = new WeakHashMap<>();
    private record Site(Vec3 hero, Vec3 angel, float yaw) {}
    private static final Map<ServerLevel, Optional<Site>> SITES = new WeakHashMap<>();
    private static Vec3 vector(com.google.gson.JsonArray a) { return new Vec3(a.get(0).getAsDouble(), a.get(1).getAsDouble(), a.get(2).getAsDouble()); }
    private static Site site(ServerLevel level)
    {
        if(SurfaceAngelPlanR52.declared(level))
        {
            String active=TvCampaignSavedData.get(level).active;
            return SurfaceAngelPlanR52.site(level,active.equals("shamshel")?active:"sachiel")
                    .map(s->new Site(s.intercept(),s.spawn(),s.yaw())).orElse(null);
        }
        return SITES.computeIfAbsent(level, key -> {
            Path file = level.getServer().getWorldPath(LevelResource.ROOT).resolve("first_battle_site_r10.json");
            if (!Files.isRegularFile(file)) return Optional.empty();
            try
            {
                var json = JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                if (!json.get("dimension").getAsString().equals(level.dimension().location().toString())) return Optional.empty();
                return Optional.of(new Site(vector(json.getAsJsonArray("hero")), vector(json.getAsJsonArray("angel")), json.get("yaw").getAsFloat()));
            }
            catch (Exception error) { ProjectSeele.LOGGER.error("TV campaign site rejected", error); return Optional.empty(); }
        }).orElse(null);
    }
    public static ServerLevel level(ServerPlayer player)
    {for(var level:player.server.getAllLevels())if(SurfaceAngelPlanR52.declared(level))return level;for(var level:player.server.getAllLevels())if(site(level)!=null)return level;return null;}
    public static Vec3 approachPointR30(ServerLevel level)
    {
        var d=TvCampaignSavedData.get(level);
        if(SurfaceAngelPlanR52.handles(level,d.active))return SurfaceAngelPlanR52.routingR52(level,d.active)==SurfaceAngelPlanR52.RoutingR52.SURFACE?SurfaceAngelPlanR52.site(level,d.active).map(SurfaceAngelPlanR52.Site::intercept).orElse(null):null;
        if(TvEncounterRulesR45.handles(d.active))return TvEncounterSitesR45.site(level,d.active).map(TvEncounterSitesR45.Site::hero).orElse(null);
        var configured=site(level);return configured==null?null:configured.hero;
    }
    public static EvaUnit01Entity combatEvaR30(ServerPlayer player)
    {
        var level=level(player);if(level==null)return EvaPilotResolver.controlTarget(player);var data=TvCampaignSavedData.get(level);
        if(data.active.isEmpty())return EvaPilotResolver.controlTarget(player);
        if(TvEncounterRulesR45.handles(data.active))
        {
            var configured=TvEncounterSitesR45.site(level,data.active).orElse(null);
            return configured==null?null:TvSortiesR32.assignedUnit(level,data,configured.primaryUnit());
        }
        Vec3 point=approachPointR30(level);
        return data.sorties.values().stream().filter(entry->TvSortiesR32.readyAssigned(level,entry))
                .map(entry->TvSortiesR32.assignedUnit(level,entry)).min(Comparator.comparingDouble(e->point==null?0:e.distanceToSqr(point))).orElse(null);
    }

    public static String briefing(ServerPlayer player)
    {
        var level = level(player); if (level == null) return "作战联络暂不可用，请返回总部后重试。";
        var data = TvCampaignSavedData.get(level); var chapter = selected(player,data);
        String constraint=SurfaceAngelPlanR52.handles(level,chapter.id())?SurfaceAngelPlanR52.startBlocker(level,chapter.id()):TvEncounterRulesR45.handles(chapter.id())?TvEncounterDirectorR45.startBlocker(level,chapter.id()):CityBattlefieldR29.obstruction(level);
        String activity = data.active.isEmpty() ? "选择任务，安排驾驶员后确认出击。" : switch (data.phase)
        { case "alert" -> "正在确认使徒位置，准备出击。";case "approach" -> "编队出击中，请前往指定阵地。"; case "combat" -> "正在交战。";case "combat_victory" -> "目标已击破，正在安排回收。";case "episode_archived" -> "任务完成。"; case "cancel" -> "正在结束任务并回收机体。";case "failure" -> "任务未完成。选择“结束任务”安排回收。"; default -> "等待出击指令。"; };
        var text=new StringBuilder(chapter.title()).append(" · 目标：").append(chapter.target()).append('\n').append(activity);
        if(!data.sorties.isEmpty())text.append('\n').append(TvSortiesR32.roster(data));
        text.append("\n\n任务目标\n").append(chapter.briefing().replace("东北迎击大道", CityBattlefieldR29.name(level)));
        if(chapter.id().equals("ramiel"))
        {
            var cannon=TvYashimaStationR52.operatorPositionR52(level);
            if(cannon!=null)text.append("\n炮位坐标：").append((int)Math.floor(cannon.x)).append(" / ").append((int)Math.floor(cannon.y+.01)).append(" / ").append((int)Math.floor(cannon.z));
        }
        if(!constraint.isBlank())text.append("\n\n待处理：").append(constraint);
        if(!data.notice.isBlank())text.append("\n\n最新通报：").append(data.notice);
        if(data.active.isEmpty())text.append("\n\n所有已开放任务均可再次出击。");
        else if(Set.of("alert","approach","combat").contains(data.phase))text.append("\n\n需要支援时，可在编队中选择待命机体并确认出击。");
        return text.toString();
    }
    public static int begin(ServerPlayer player)
    {var level=level(player);return beginAssigned(player,1,level!=null&&selected(player,TvCampaignSavedData.get(level)).id().equals("ramiel"),false);}
    public static int beginAssigned(ServerPlayer player,int variant,boolean npc,boolean rifle)
    {return beginAssigned(player,variant,npc,rifle,null);}
    public record CrewR54(int unit,UUID pilot,boolean npc){}
    public static int beginFormationR54(ServerPlayer commander,String mission,List<CrewR54> crew,boolean rifle)
    {
        var level=level(commander);
        if(level==null||commander.level()!=level||!NervStaffDialogue.authorized(commander))return 0;
        if(crew.isEmpty()||crew.size()>3)return message(commander,"请选择出战机体和驾驶员。",false);
        var data=TvCampaignSavedData.get(level);var units=new HashSet<Integer>();var humans=new HashSet<UUID>();
        if(!data.active.isEmpty()&&(Set.of("cancel","failure","combat_victory").contains(data.phase)||data.targetDeathConfirmedR45))
            return message(commander,"本次任务已停止出击。请先选择“结束任务”，待机体和装备回库后再出击。",false);
        if(!data.active.isEmpty()&&!data.active.equals(mission))return message(commander,"请先结束当前作战。",false);
        for(var choice:crew)
        {
            if(choice.unit()<0||choice.unit()>2||!units.add(choice.unit()))return message(commander,"每台机体只能编入一次。",false);
            // An active sortie accepts additions only. A reopened panel can
            // carry local defaults; they must never replace its real pilots.
            if(!data.active.isEmpty()&&data.sorties.containsKey(choice.unit()))continue;
            var pilot=choice.npc()?null:level.getServer().getPlayerList().getPlayer(choice.pilot());
            if(!choice.npc()&&(pilot==null||pilot.level()!=level||!NervStaffDialogue.authorized(pilot)||!humans.add(choice.pilot())))
                return message(commander,"真人驾驶员需在线并位于本作战世界，每人只能驾驶一台机体。",false);
            if(!data.active.isEmpty()&&!choice.npc()&&data.sorties.values().stream().anyMatch(s->s.unit!=choice.unit()&&!s.npc&&s.commander.equals(choice.pilot())))
                return message(commander,"该驾驶员已驾驶另一台出战机体。",false);
            if(StaffRecoveryR47.pending(level,choice.unit())||PilotReturnR39.pending(level,choice.unit()))return message(commander,TvSortiesR32.name(choice.unit())+"仍在回库交接。",false);
            var eva=TvSortiesR32.unit(level,choice.unit());
            if(eva!=null&&(TvMissionEquipmentR45.awaitingPhysicalReturn(eva)||eva.getPilotEntity()!=null
                    &&(choice.npc()?!(eva.getPilotEntity() instanceof TrainingPilotEntity npcPilot&&npcPilot.getAssignedVariant()==choice.unit()):eva.getPilotEntity()!=pilot)))
                return message(commander,TvSortiesR32.name(choice.unit())+"当前驾驶员或装备尚未交接。",false);
            String blocker=TvEncounterRulesR45.formationSlotBlockerR47(level,mission,choice.unit());
            if(!blocker.isEmpty())return message(commander,blocker,false);
        }
        if(!data.active.isEmpty())
        {
            int result=1;
            for(var choice:crew)if(!data.sorties.containsKey(choice.unit()))
                result&=TvSortiesR32.reinforce(choice.npc()?commander:level.getServer().getPlayerList().getPlayer(choice.pilot()),choice.unit(),choice.npc(),rifle);
            if(result!=0)message(commander,"支援编队正在准备出击。",true);
            return result;
        }
        if(mission.equals("ramiel")&&!(units.contains(0)&&units.contains(1)))return message(commander,"屋岛作战需要先选定零号机与初号机的驾驶员。",false);
        if(select(commander,mission)==0)return 0;
        var primary=crew.stream().filter(c->c.unit()==1).findFirst().orElse(crew.get(0));
        return beginAssigned(commander,primary.unit(),primary.npc(),rifle,List.copyOf(crew));
    }
    private static int beginAssigned(ServerPlayer player,int variant,boolean npc,boolean rifle,List<CrewR54> formation)
    {
        if(variant<0||variant>4||npc&&variant>2)return message(player,"NPC 驾驶员对应零号机、初号机、二号机；UN 机体可由玩家加入。",false);
        if (!NervStaffDialogue.authorized(player)) return message(player, "作战下达需要 NERV 通行权限。", false);
        var level = level(player); if (level == null) return message(player, "本世界尚未配置作战区域。", false);
        if(npc&&player.level()!=level)return message(player,"请进入第三新东京市后下达驾驶员出击指令。",false);
        var data = TvCampaignSavedData.get(level); var chapter = selected(player,data);
        String surfaceHold=SurfaceAngelPlanR52.startBlocker(level,chapter.id());if(!surfaceHold.isEmpty())return message(player,surfaceHold,false);
        String preparation=TvCampaignCatalog.preparationBlockerR52(data.active.isEmpty()?chapter.id():data.active);
        if(!preparation.isEmpty())return message(player,preparation,false);
        if(variant<3&&(StaffRecoveryR47.pending(level,variant)||PilotReturnR39.pending(level,variant)))
            return message(player,"这台机体仍在执行回收入库与驾驶员交接。完成后再下达新的出击。",false);
        var acceptedUnit=TvSortiesR32.unit(level,variant);
        if(acceptedUnit!=null&&TvMissionEquipmentR45.awaitingPhysicalReturn(acceptedUnit))
            return message(player,"炮、盾尚未归还，请完成装备回收后再出击。",false);
        if(acceptedUnit!=null&&acceptedUnit.getPilotEntity()!=null
                &&(npc?!(acceptedUnit.getPilotEntity() instanceof TrainingPilotEntity pilot&&pilot.getAssignedVariant()==variant)
                    :!acceptedUnit.getPilotEntity().getUUID().equals(formation==null?player.getUUID():formation.stream().filter(c->c.unit()==variant).findFirst().orElseThrow().pilot())))
            return message(player,"这台机体已有其他驾驶员。请确认当前驾驶员安排后再编入。",false);
        if(Set.of("cancel","failure","combat_victory").contains(data.phase)||data.targetDeathConfirmedR45)
            return message(player,"请先结束当前任务，待机体和装备回库后再出击。",false);
        if (!data.active.isEmpty()) return TvSortiesR32.reinforce(player,variant,npc,rifle);
        if (!chapter.playable()) return message(player, "这场作战仍在制作中。", false);
        if(SurfaceAngelPlanR52.handles(level,chapter.id()))
        {String blocker=SurfaceAngelPlanR52.startBlocker(level,chapter.id());if(!blocker.isEmpty())return message(player,blocker,false);}
        if(chapter.id().equals("ramiel")&&formation==null)
        {String blocker=yashimaDefaultFormationBlocker(level,variant);if(!blocker.isEmpty())return message(player,blocker,false);}
        if(TvEncounterRulesR45.handles(chapter.id()))
        {
            String blocker=TvEncounterDirectorR45.startBlocker(level,chapter.id());if(!blocker.isEmpty())return message(player,blocker,false);
            String slotBlocker=TvEncounterRulesR45.formationSlotBlockerR47(level,chapter.id(),variant);
            if(!slotBlocker.isEmpty())return message(player,slotBlocker,false);
        }
        var replay = FirstBattleSavedData.get(level);
        if (replay.active != null || replay.missionOwner != null) return message(player, "作战区已有任务进行中，请先结束该任务。", false);
        player.getPersistentData().putString("SeeleMissionChoiceR30",chapter.id());
        data.generationR43++;
        data.episodeStateR45="";data.equipmentReturnedR45=false;data.targetDeathConfirmedR45=false;
        data.owner = player.getUUID(); data.active = chapter.id(); data.phase = "alert";data.assignedVariant=variant;data.npcPilot=npc;data.autoArmament=npc&&rifle;data.pilotDispatchRequested=false; data.alertStarted=level.getGameTime();data.alertLine=0;data.notice = "出击编队："+TvSortiesR32.name(variant)+" · "+(npc?TrainingPilotEntity.pilotName(variant):player.getGameProfile().getName()); data.angel = null; data.lastPosition = null; data.setDirty();
        if(formation!=null)for(var choice:formation)data.assign(choice.unit(),choice.npc()?player.getUUID():choice.pilot(),choice.npc(),choice.npc()&&rifle);
        else data.assign(variant,player.getUUID(),npc,npc&&rifle);
        if(chapter.id().equals("ramiel")&&formation==null)
            for(int unit:new int[]{0,1})if(!data.sorties.containsKey(unit))data.assign(unit,player.getUUID(),true,false);
        data.rayPreloadCursorR45=data.missingTicksR45=0;
        data.encounterSiteR45=TvEncounterSitesR45.site(level,chapter.id()).map(TvEncounterSitesR45.Site::id).orElse("");
        data.encounterLayoutR45=TvEncounterSitesR45.site(level,chapter.id()).map(TvEncounterSitesR45.Site::fingerprint).orElse("");
        if(SurfaceAngelPlanR52.handles(level,chapter.id())&&!SurfaceAngelAssaultR52.begun(level,data))
        {data.phase="failure";data.setDirty();return message(player,"目标区暂时无法联络。请结束任务后重试。",false);}
        if(chapter.id().equals("ramiel")&&!TvYashimaDirectorR50.begin(level,data))
        {data.phase="failure";data.setDirty();return message(player,data.notice+" 请结束任务后重试。",false);}
        if(chapter.id().equals("gaghiel"))TvMarineDirectorR50.begin(level,data);
        return message(player, "出击指令已下达。\n" + briefing(player), true);
    }
    private static String yashimaDefaultFormationBlocker(ServerLevel level,int selected)
    {
        for(int unit:new int[]{0,1})if(unit!=selected)
        {
            if(StaffRecoveryR47.pending(level,unit)||PilotReturnR39.pending(level,unit))return TvSortiesR32.name(unit)+"仍在回收，待驾驶员返回后再出击。";
            var eva=TvSortiesR32.unit(level,unit);
            if(eva!=null&&(TvMissionEquipmentR45.awaitingPhysicalReturn(eva)
                    ||eva.getPilotEntity()!=null&&!(eva.getPilotEntity() instanceof TrainingPilotEntity p&&p.getAssignedVariant()==unit)))
                return TvSortiesR32.name(unit)+"尚有装备未归还，或驾驶员与编队安排不符。请先检查整备状态。";
        }
        return "";
    }
    private static TvCampaignCatalog.Chapter selected(ServerPlayer player,TvCampaignSavedData data)
    {
        if(!data.active.isEmpty())return TvCampaignCatalog.find(data.active).orElse(TvCampaignCatalog.at(0));
        return TvCampaignCatalog.find(player.getPersistentData().getString("SeeleMissionChoiceR30"))
                .filter(TvCampaignCatalog.Chapter::playable)
                .or(()->TvCampaignCatalog.find(data.episodeChapterR45).filter(TvCampaignCatalog.Chapter::playable))
                .orElse(TvCampaignCatalog.at(0));
    }
    public static String selectedMissionR54(ServerPlayer player)
    {var level=level(player);return level==null?"sachiel":selected(player,TvCampaignSavedData.get(level)).id();}
    public static int select(ServerPlayer player,String id)
    {
        if(!NervStaffDialogue.authorized(player))return message(player,"需要 NERV 指挥权限。",false);
        var mission=TvCampaignCatalog.find(id).orElse(null);
        if(mission==null||!mission.playable())return message(player,"这份作战尚未开放。",false);
        var level=level(player);if(level==null)return message(player,"作战联络暂不可用，请返回总部后重试。",false);
        if(!TvCampaignSavedData.get(level).active.isEmpty())return message(player,"请先结束或取消正在执行的作战。",false);
        AutoSortieR32.invalidateMission(level);
        player.getPersistentData().putString("SeeleMissionChoiceR30",id);
        return message(player,briefing(player),true);
    }
    public static int cancel(ServerPlayer player)
    {
        var level = level(player); if (level == null) return 0;
        var data = TvCampaignSavedData.get(level);
        if (data.active.isEmpty()) return message(player, "当前没有正在执行的任务。", false);
        if (!player.getUUID().equals(data.owner) && !player.hasPermissions(2)) return message(player, "只能撤销自己的作战指令。", false);
        AutoSortieR32.invalidateMission(level);
        if (data.active.equals("sachiel")) FirstBattleMission.cancel(player);
        TvMissionAlertR30.clear(level);
        TvMissionEquipmentR45.revokeMission(level);
        TvEncounterRulesR45.stopEquipment(level,data);
        if(data.active.equals("gaghiel"))TvMarineDirectorR50.cancel(level,data);
        PilotReturnR39.enqueue(level,java.util.List.copyOf(data.sorties.values()));
        data.phase = "cancel"; data.setDirty();
        clearCombatBar(level);
        return message(player, "正在结束任务并回收机体。装备归还后，可重新选择任务出击。", true);
    }
    private static int message(ServerPlayer player, String text, boolean accepted)
    { player.sendSystemMessage(Component.literal(text)); return accepted ? 1 : 0; }
    public static void firstBattleComplete(ServerLevel level, UUID owner, UUID angel)
    { complete(level, "sachiel", owner, angel); }
    public static void encounterCompleteR45(ServerLevel level,String chapter,UUID owner,UUID angel)
    {complete(level,chapter,owner,angel);}
    public static int retry(ServerPlayer player)
    {
        var l=level(player);if(l==null)return 0;var d=TvCampaignSavedData.get(l);
        String surfaceHold=SurfaceAngelPlanR52.startBlocker(l,d.active);if(!surfaceHold.isEmpty())return message(player,surfaceHold,false);
        String preparation=TvCampaignCatalog.preparationBlockerR52(d.active);
        if(!preparation.isEmpty())return message(player,preparation,false);
        if(!player.getUUID().equals(d.owner)&&!player.hasPermissions(2))return message(player,"只能重试自己受托的作战。",false);
        if(!TvEncounterRulesR45.handles(d.active)||!d.phase.equals("failure"))return message(player,"当前没有等待恢复的遭遇战。",false);
        if(d.targetDeathConfirmedR45)return message(player,"目标已经不在了，不能重试这场战斗。先回收机体，再取消这次行动。",false);
        if(!NervStaffDialogue.authorized(player)||player.level()!=l)return message(player,"请由指挥员回到战区，再下达出击指令。",false);
        if(d.owner==null||d.generationR43<=0||d.sorties.isEmpty())return message(player,"这次出击的联络信息对不上，暂时无法开始。请联系整备部。",false);
        // Failure retry is a new dispatch of the same originals, not an implicit
        // revival of still-deployed units or an equipment-loan status rewrite.
        String recovery=originalRecoveryBlocker(l,d,false);
        if(!recovery.isEmpty())return message(player,recovery,false);
        if(!TvMissionEquipmentR45.missionEquipmentReturned(l,d.owner,d.generationR43,d.active))
            return message(player,"装备还没送回整备库。先完成回收，再重新出击。",false);
        for(var sortie:d.sorties.values())
        {
            var eva=TvSortiesR32.unit(l,sortie.unit);
            // Only restart dispatch of the same recovered original airframe.
            // Never clear IDs or commandeer a still-deployed/riding unit.
            if(sortie.npc&&eva!=null&&sortie.eva!=null&&sortie.eva.equals(eva.getUUID())
                    &&EvaLogisticsDirector.status(l,sortie.unit).phase().equals("PARKED"))
                sortie.dispatchRequested=false;
        }
        d.phase="approach";d.missingTicksR45=0;d.rayPreloadCursorR45=0;d.notice="重新确认目标与机体状态，请保持通信。";d.setDirty();
        if(d.active.equals("ramiel")&&!TvYashimaDirectorR50.begin(l,d))
        {d.phase="failure";d.notice="暂时无法确认拉米尔的位置，请结束任务后重试。";d.setDirty();return message(player,d.notice,false);}
        if(d.active.equals("ramiel"))TvYashimaSavedDataR50.get(l).resetFireControlForRetry(d);
        if(d.active.equals("gaghiel"))TvMarineDirectorR50.retry(l,d);
        return 1;
    }
    public static void firstBattleBound(ServerLevel level, UUID owner, UUID angel)
    {
        var data = TvCampaignSavedData.get(level);
        if (data.active.equals("sachiel") && owner.equals(data.owner) && data.angel == null)
        { data.angel = angel; data.phase = "combat"; data.setDirty(); }
    }
    private static void complete(ServerLevel level, String chapter, UUID owner, UUID angel)
    {
        var data = TvCampaignSavedData.get(level);
        var returning=java.util.List.copyOf(data.sorties.values());
        if(!data.canFinish(chapter,owner,angel))return;
        TvSortiesR32.continuity(level,data);
        TvMissionEquipmentR45.revokeMission(level);
        TvEncounterRulesR45.stopEquipment(level,data);
        if(!data.finish(chapter,owner,angel))return;
        // Combat has ended; recovery/episode handover must never keep the
        // last health sample visible while its own workflow remains active.
        clearCombatBar(level);
        for(var sortie:returning)if(sortie.unit<3)AutoSortieR32.clearAutomatic(level,sortie.unit);
        com.projectseele.world.PilotReturnR39.enqueue(level,returning);
        var player = level.getServer().getPlayerList().getPlayer(owner);
        if (player != null)
        {
            message(player, data.notice, true);
            NervStaffDialogue.say(player, "葛城美里 · 作战通信", "目标已确认消失。先别急着动，检查供电和机体状态，我们准备接你回来。");
        }
        ProjectSeele.LOGGER.info("TV COMBAT VICTORY pending episode handover={} owner={} target={}", chapter, owner, angel);
    }
    private static String originalRecoveryBlocker(ServerLevel level,TvCampaignSavedData data)
    {return originalRecoveryBlocker(level,data,true);}
    /** Retry reads the same original safety conditions without creating victory receipts. */
    private static String originalRecoveryBlocker(ServerLevel level,TvCampaignSavedData data,boolean recordVictory)
    {
        for(var sortie:data.sorties.values())
        {
            var eva=TvSortiesR32.assignedUnit(level,sortie);boolean recovered=false;
            if(eva!=null&&eva.isAlive()&&eva.getPilotEntity()==null&&!eva.isLaunchSequenceActive()&&!EvaAirTransportR31.active(eva))
            {
                if(sortie.unit<3)
                {
                    var fleet=EvaFleetSavedData.get(level.getServer()).entry(sortie.unit).orElse(null);
                    recovered=fleet!=null&&fleet.canonicalId().equals(sortie.eva)&&fleet.phase()==EvaFleetSavedData.Phase.PARKED
                            &&EvaLogisticsDirector.inAssignedHangarR33(level,eva)&&EvaLogisticsDirector.recoveryMotionSettled(eva);
                }
                else recovered=eva.position().distanceToSqr(UNRecoveryR22.home(level,sortie.unit-3))<16&&eva.onGround()
                        &&eva.getDeltaMovement().lengthSqr()<.001;
            }
            if(!recovered)
            {
                if(recordVictory)data.invalidateRecovery(sortie.unit);if(eva==null&&sortie.unit<3)EvaLogisticsDirector.loadControlTarget(level,sortie.unit);
                return TvSortiesR32.name(sortie.unit)+(recordVictory?"还没完成回收。请把机体送回机库，并确认驾驶员安全离栓。":"还没完成回库整备，请先回收机体。");
            }
            if(recordVictory&&data.originalRecoveryRecorded(sortie.unit)&&!sortie.npc)continue;
            if(sortie.pilotR45==null)return "驾驶员联络中断了，暂时无法完成交接。请联系整备部。";
            // Victory skips ordinary sortie continuity. Retain the original rest room too,
            // otherwise a saved, seated pilot outside the player's chunks can never be archived.
            if(sortie.npc&&sortie.unit<3)TrainingPilotDirector.retainOriginalPilotR47(level,sortie.unit);
            var pilot=sortie.npc?level.getEntity(sortie.pilotR45):level.getServer().getPlayerList().getPlayer(sortie.pilotR45);
            if(sortie.npc&&pilot==null)return TvSortiesR32.name(sortie.unit)+"的驾驶员待命区正在加载，稍后自动完成交接。";
            if(pilot==null||!pilot.isAlive()||pilot.level()!=level||sortie.npc&&!(pilot instanceof TrainingPilotEntity npc&&npc.getAssignedVariant()==sortie.unit)||pilot.getVehicle()==eva
                    ||pilot instanceof net.minecraft.world.entity.LivingEntity living&&living.getVehicle() instanceof EntryPlugCarrierEntity plug&&plug.getLinkedEva()==eva)
                return TvSortiesR32.name(sortie.unit)+"的驾驶员还没完成安全交接，请先确认人已离开插入栓。";
            if(sortie.npc&&!TrainingPilotDirector.atOriginalStandbyR47(level,sortie.unit))
                return TvSortiesR32.name(sortie.unit)+"的驾驶员仍在返回待命。稍后再结束本次行动。";
            if(recordVictory&&!data.recordOriginalRecovery(data.owner,data.generationR43,sortie.unit,eva.getUUID(),pilot.getUUID()))return "机体和驾驶员的交接信息对不上，暂时无法结束行动。请联系整备部。";
        }return "";
    }
    private static void episodeHandover(ServerLevel level,TvCampaignSavedData data)
    {
        TvEncounterRulesR45.stopEquipment(level,data);
        for(var sortie:data.sorties.values())if(sortie.unit<3)AutoSortieR32.clearAutomatic(level,sortie.unit);
        String blocked=originalRecoveryBlocker(level,data);
        boolean equipment=TvMissionEquipmentR45.missionEquipmentReturned(level,data.owner,data.generationR43,data.active);
        if(data.equipmentReturnedR45!=equipment){data.equipmentReturnedR45=equipment;data.setDirty();}
        if(blocked.isEmpty()&&!equipment)blocked="炮、盾和借用的装备还没送回整备库。先把它们归还，再结束行动。";
        if(!blocked.isEmpty()){if(!data.notice.equals(blocked)){data.notice=blocked;data.setDirty();}return;}
        UUID owner=data.owner;String chapter=data.active;long generation=data.generationR43;
        if(data.archiveEpisode(chapter,owner,generation))
        {
            var player=level.getServer().getPlayerList().getPlayer(owner);if(player!=null)message(player,data.notice,true);
            ProjectSeele.LOGGER.info("TV EPISODE ARCHIVED={} owner={} generation={}",chapter,owner,generation);
        }
    }
    @SubscribeEvent(priority=net.minecraftforge.eventbus.api.EventPriority.LOWEST)
    public static void death(LivingDeathEvent event)
    {
        if (!(event.getEntity() instanceof ShamshelEntity angel) || !(angel.level() instanceof ServerLevel level)) return;
        var data = TvCampaignSavedData.get(level);
        if (angel.getUUID().equals(data.angel) && angel.getTags().contains("seele_tv_shamshel_r24")) complete(level, "shamshel", data.owner, angel.getUUID());
    }
    private static void load(ServerLevel level, BlockPos pos)
    {
        var chunk = new ChunkPos(pos); level.getChunkSource().addRegionTicket(TICKET, chunk, 2, chunk); level.getChunk(pos);
    }
    private static void pilotContinuity(ServerLevel level,TvCampaignSavedData data)
    {
        TvSortiesR32.continuity(level,data);
    }
    @SubscribeEvent public static void protectReconnectingPilot(net.minecraftforge.event.entity.living.LivingAttackEvent event)
    {
        if(!(event.getEntity() instanceof ServerPlayer player)||!event.getSource().is(net.minecraft.tags.DamageTypeTags.IS_FALL))return;
        var data=TvCampaignSavedData.get(player.serverLevel());
        if(data.sorties.values().stream().anyMatch(s->s.resumePending&&s.wasRiding&&player.getUUID().equals(s.commander)&&s.resumeTicks<=200))event.setCanceled(true);
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        for (var level : event.getServer().getAllLevels())
        {
            var pending=TvCampaignSavedData.get(level);
            if(pending.active.isEmpty()||pending.targetDeathConfirmedR45||pending.phase.equals("combat_victory"))
                clearCombatBar(level);
            if(pending.phase.equals("combat_victory"))
            {if(event.getServer().getTickCount()%10==0)episodeHandover(level,pending);continue;}
            if(pending.targetDeathConfirmedR45&&!pending.phase.equals("cancel"))continue;
            Site site = site(level); if (site == null&&!SurfaceAngelPlanR52.declared(level)) continue;
            var data = TvCampaignSavedData.get(level);
            pilotContinuity(level,data);
            if(SurfaceAngelPlanR52.handles(level,data.active)&&data.phase.equals("failure")){clearCombatBar(level);continue;}
            if(SurfaceAngelPlanR52.handles(level,data.active)&&!data.phase.equals("cancel"))
            {
                var boss=SurfaceAngelAssaultR52.tick(level,data);
                if(boss==null||!boss.isAlive())
                {
                    clearCombatBar(level);
                    if(boss!=null&&data.phase.equals("combat"))complete(level,data.active,data.owner,boss.getUUID());
                    continue;
                }
                if(event.getServer().getTickCount()%10==0)
                {
                    var surfaceBar=BARS.computeIfAbsent(level,key->new ServerBossEvent(Component.literal("地表迎击"),BossEvent.BossBarColor.RED,BossEvent.BossBarOverlay.PROGRESS));
                    surfaceBar.removeAllPlayers();surfaceBar.setVisible(!(boss instanceof SachielEntity s&&s.isFirstBattleActive()));
                    for(var sortie:data.sorties.values()){var p=event.getServer().getPlayerList().getPlayer(sortie.commander);if(p!=null&&p.level()==level)surfaceBar.addPlayer(p);}
                    float field=boss instanceof Angel a?a.getAtField():0,max=data.active.equals("sachiel")?900:700;
                    surfaceBar.setName(Component.literal((data.active.equals("sachiel")?"第3使徒 萨基尔":"第4使徒 夏姆榭尔")+" · "+(data.phase.equals("combat")?"地表交战":data.phase.equals("alert")?"目标已出现，准备迎击":"使徒正在进攻地表装甲井")));
                    surfaceBar.setProgress(Math.max(0,Math.min(1,field>0?field/max:boss.getHealth()/boss.getMaxHealth())));
                }
                continue;
            }
            if(site==null)continue;
            if(event.getServer().getTickCount()%10!=0)continue;
            var bar = BARS.computeIfAbsent(level, key -> new ServerBossEvent(Component.literal("TV 作战"), BossEvent.BossBarColor.RED, BossEvent.BossBarOverlay.PROGRESS));
            bar.removeAllPlayers();
            if (data.active.isEmpty()) continue;
            TvSortiesR32.updateTarget(level,data);
            if(TvEncounterRulesR45.handles(data.active)&&!data.phase.equals("cancel"))
            {
                TvEncounterDirectorR45.tick(level,data,event.getServer().getPlayerList().getPlayer(data.owner),bar);
                continue;
            }
            if(data.phase.equals("alert"))
            {
                var commander=event.getServer().getPlayerList().getPlayer(data.owner);
                if(!TvMissionAlertR30.tick(level,data,commander)||commander==null)continue;
                if(data.active.equals("sachiel")&&!FirstBattleMission.begin(commander)){data.clear("迎击区暂不可用，请确认其他行动已结束后重新下达指令。");continue;}
                data.phase="approach";data.setDirty();
            }
            if (data.phase.equals("cancel"))
            {
                if(TvEncounterRulesR45.handles(data.active)&&data.targetDeathConfirmedR45){data.clear("任务已结束，可重新选择任务。");continue;}
                if (data.angel == null) { data.clear("任务已结束，可重新选择任务。"); continue; }
                load(level, data.lastPosition == null ? BlockPos.containing(site.angel) : data.lastPosition);
                var entity = level.getEntity(data.angel);
                if (entity != null && (entity.getTags().contains("seele_tv_shamshel_r24")
                        ||entity instanceof net.minecraft.world.entity.Mob mob&&TvEncounterDirectorR45.owned(mob,data))) entity.discard();
                if(TvEncounterRulesR45.handles(data.active)&&entity==null)
                {data.notice="正在结束这次行动，请等待战区确认。";continue;}
                if(TvEncounterRulesR45.handles(data.active)&&entity!=null&&!(entity instanceof net.minecraft.world.entity.Mob m&&TvEncounterDirectorR45.owned(m,data)))
                {data.notice="战区联络还没接通，行动暂时保持暂停。";continue;}
                if (entity != null || !data.active.equals("shamshel")) { data.clear("任务已结束，可重新选择任务。"); MISSING.remove(level); }
                else if (MISSING.merge(level, 1, Integer::sum) > 40) { data.clear("任务已结束，本次未完成目标。"); MISSING.remove(level); }
                continue;
            }
            if(TvEncounterRulesR45.handles(data.active))
            {
                TvEncounterDirectorR45.tick(level,data,event.getServer().getPlayerList().getPlayer(data.owner),bar);
                continue;
            }
            if (data.active.equals("sachiel"))
            {
                var first = FirstBattleSavedData.get(level);
                if (data.owner.equals(first.missionOwner))
                {
                    if (first.missionAngel != null && data.angel == null)
                    { data.angel = first.missionAngel; data.phase = "combat"; data.setDirty(); }
                }
                else if (first.active == null) data.clear("迎击已结束，本次任务未完成。");
                continue;
            }
            var player = event.getServer().getPlayerList().getPlayer(data.owner);
            if (player == null || player.level() != level) continue;
            bar.addPlayer(player);
            for(var participant:data.sorties.values()){var p=event.getServer().getPlayerList().getPlayer(participant.commander);if(p!=null&&p.level()==level)bar.addPlayer(p);}
            if (data.angel == null)
            {
                var eva = combatEvaR30(player);
                double distance = (eva == null ? player.position() : eva.position()).distanceTo(site.hero);
                bar.setName(Component.literal("第4使徒迎击 · 前往" + CityBattlefieldR29.name(level) + " / " + Math.round(distance) + " m")); bar.setProgress(1);
                String blocked = CityBattlefieldR29.obstruction(level);
                if (!blocked.isEmpty()) { bar.setName(Component.literal(blocked)); continue; }
                if (!TvSortiesR32.ready(eva) || distance > 90) continue;
                load(level, BlockPos.containing(site.angel));
                if(!level.isPositionEntityTicking(BlockPos.containing(site.angel)))continue;
                if(!level.getEntitiesOfClass(ShamshelEntity.class,new net.minecraft.world.phys.AABB(site.angel,site.angel).inflate(180),
                        q->q.isAlive()&&q.getTags().contains("seele_tv_shamshel_r24")).isEmpty())
                {bar.setName(Component.literal("战区还有上一场作战的目标，请先结束那次行动"));continue;}
                var angel = ModEntities.SHAMSHEL.get().create(level); if (angel == null) continue;
                angel.moveTo(site.angel.x, site.angel.y + 4, site.angel.z, site.yaw + 180, 0);
                angel.yBodyRot = angel.yHeadRot = site.yaw + 180; angel.setPersistenceRequired(); angel.addTag("seele_tv_shamshel_r24"); angel.setTarget(eva);
                if (!level.noCollision(angel, angel.getBoundingBox())) { bar.setName(Component.literal("迎击区域被占用，请清空后继续")); continue; }
                if (!level.addFreshEntity(angel)) continue;
                data.angel = angel.getUUID(); data.lastPosition = angel.blockPosition(); data.phase = "combat"; data.setDirty();
                message(player, "目标确认。光鞭将先蓄势再横扫，注意两侧退路。", true);
            }
            load(level, data.lastPosition == null ? BlockPos.containing(site.angel) : data.lastPosition);
            if (level.getEntity(data.angel) instanceof ShamshelEntity angel)
            {
                if(!angel.isAlive())
                {
                    clearCombatBar(level);
                    if(angel.getTags().contains("seele_tv_shamshel_r24"))complete(level,"shamshel",data.owner,angel.getUUID());
                    continue;
                }
                MISSING.remove(level);
                if (!angel.blockPosition().equals(data.lastPosition)) { data.lastPosition = angel.blockPosition(); data.setDirty(); }
                TvSortiesR32.updateTarget(level,data);
                float field = angel.getAtField();
                bar.setName(Component.literal("第4使徒 夏姆榭尔 · " + (field > 0 ? "AT 力场 " + Math.round(field) : "核心 " + Math.round(100 * angel.getHealth() / angel.getMaxHealth()) + "%")));
                bar.setProgress(Math.max(0, Math.min(1, field > 0 ? field / 700 : angel.getHealth() / angel.getMaxHealth())));
            }
            else
            {
                // An unloaded/unresolved original is not a live health sample
                // and is not proof of a death. Resume its bar only after the
                // same persisted UUID resolves to a living target again.
                clearCombatBar(level);
                if(MISSING.merge(level, 1, Integer::sum) > 40)
                { data.clear("与目标失去联络。请重新选择任务。"); MISSING.remove(level); }
                else if(!data.notice.equals("正在确认目标信号，请保持通信。"))
                { data.notice="正在确认目标信号，请保持通信。";data.setDirty(); }
            }
        }
    }
    @SubscribeEvent
    public static void unloaded(net.minecraftforge.event.level.LevelEvent.Unload event)
    {
        if(!(event.getLevel() instanceof ServerLevel level))return;
        clearCombatBar(level);MISSING.remove(level);SITES.remove(level);SurfaceAngelPlanR52.clear(level);
    }
    @SubscribeEvent public static void commands(RegisterCommandsEvent event)
    {
        event.getDispatcher().register(Commands.literal("seele").then(Commands.literal("tv")
                .then(Commands.literal("collect_equipment").then(Commands.argument("unit",com.mojang.brigadier.arguments.IntegerArgumentType.integer(0,1)).executes(c->{
                    var player=c.getSource().getPlayerOrException();var unit=com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(c,"unit");
                    var eva=TvSortiesR32.unit(player.serverLevel(),unit);
                    boolean collected=eva!=null&&TvMissionEquipmentR45.collectRecoveredCargo(eva,player,net.minecraft.world.InteractionHand.MAIN_HAND);
                    return message(player,collected?"装备已领取，请送回整备库并右键空置的装备架归还。":"请空手站在已回库的机体旁，等待驾驶员离开插入栓后领取待归还装备。",collected);
                })))
                .then(Commands.literal("status").executes(c -> message(c.getSource().getPlayerOrException(), briefing(c.getSource().getPlayerOrException()), true)))
                .then(Commands.literal("begin").executes(c -> begin(c.getSource().getPlayerOrException())))
                .then(Commands.literal("select").then(Commands.literal("sachiel").executes(c->select(c.getSource().getPlayerOrException(),"sachiel"))).then(Commands.literal("shamshel").executes(c->select(c.getSource().getPlayerOrException(),"shamshel")))
                    .then(Commands.literal("ramiel").executes(c->select(c.getSource().getPlayerOrException(),"ramiel"))).then(Commands.literal("gaghiel").executes(c->select(c.getSource().getPlayerOrException(),"gaghiel"))))
                .then(Commands.literal("retry").executes(c->retry(c.getSource().getPlayerOrException())))
                .then(Commands.literal("cancel").executes(c -> cancel(c.getSource().getPlayerOrException())))));
    }
    private TvCampaignDirector() {}
}
